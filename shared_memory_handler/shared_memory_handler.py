from __future__ import annotations
from collections.abc import Iterator
from typing import Final
from multiprocessing.shared_memory import SharedMemory
from multiprocessing import current_process
from struct import Struct
from uuid import uuid4
from atexit import register
from signal import signal, SIGINT, SIGTERM, SIGHUP, SIGQUIT, SIGABRT
from abc import ABC

MAX_NAME_LENGTH: Final = 30

# SharedMemory created in other processes.
global_shared_memory_objects: dict[str, SharedMemory] = {}
# SharedMemory created in the current process. 
# They will be unlinked once the current process ends.
local_shared_memory_objects: dict[str, SharedMemory] = {}

def _cleanup() -> None:
    """Clean up shared memory objects."""
    for shared_memory in global_shared_memory_objects.values():
        try:
            if shared_memory:
                shared_memory.close()
        except FileNotFoundError:
            pass
        except Exception as e:
            print("Error closing shared memory created outside the current "
                  f"process '{current_process().name}': {e}")
    for shared_memory in local_shared_memory_objects.values():
        try:
            if shared_memory:
                shared_memory.close()
                shared_memory.unlink()
        except FileNotFoundError:
            pass
        except Exception as e:
            print("Error closing shared memory created within the current "
                  f"process '{current_process().name}': {e}")

def _signal_handler(signum, frame) -> None:
    """Handle signals for cleanup."""
    _cleanup()
    exit()

register(_cleanup)
signal(SIGINT, _signal_handler)
signal(SIGTERM, _signal_handler)
signal(SIGHUP, _signal_handler)
signal(SIGQUIT, _signal_handler)
signal(SIGABRT, _signal_handler)


def _random_name() -> str:
    LOOKUP = "0123456789_ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcdefghijklmnopqrstuvwxyz"
    process_name = current_process().name
    rest_length = MAX_NAME_LENGTH - len(process_name)
    n = uuid4().int
    random_part = [None] * (rest_length)
    for i in range(rest_length):
        n, r = divmod(n, 64)
        random_part[i] = LOOKUP[r]
    return f"{process_name}{"".join(random_part)}"


def add_shared_memory(size: int, name: str | None = None) -> str:
    """
    Add a new shared memory object. 
    
    This object will not out-live the process it is created in.

    Do not specify name unless you are very sure there won't be a collision.
    By default, the name is generated with uuid.uuid4.
    """
    if size <= 0:
        raise ValueError("Size must be positive")
    process_name = current_process().name
    name = _random_name()
    # It is extremely rare, but we can easily solve the problem cause by such
    # name collision
    while name in global_shared_memory_objects or name in local_shared_memory_objects:
        name = _random_name()

    try:
        shm = SharedMemory(name, create=True, size=size, track=False)
        local_shared_memory_objects[name] = shm
        return shm.name
    # Two possible causes:
    # 1. A shared memory object created before was not cleaned up when the 
    #    program terminated, and it happens that they have the same name,
    #    which is extremely rare.
    #    It is totally safe to overwrite it.
    #
    # 2. A shared memory object created by another process has not been used
    #    in the current process, which can happen from time to time, and it 
    #    happens that they have the same name, which is extremely rare.
    #    It is very bad but the chance is "from time to time * extremely rare"
    #    so i guess we can just live with it
    except FileExistsError:
        shm = SharedMemory(name, create=False, track=False)
        shm.close()
        shm.unlink()
        add_shared_memory(size, name)
    except Exception as e:
        try:
            if shm:
                shm.close()
                shm.unlink()
        except Exception as se:
            raise Exception(f"Failed to cleanup shared memory: {se}") from e
        raise e

def get_memory_view(name: str) -> memoryview:
    """
    Get a memory view of a shared memory object.
    
    Remember to manually delete all reference with keyword `del` to the 
    (slices of) returned value if there is any. If they are not manually 
    deleted, "BufferError: cannot close exported pointers exist" will be risen
    when closing the SharedMemory, and there will be a memoryleak.

    An example is shown as below:
    ```
    from multiprocessing.shared_memory import SharedMemory
    from dataclasses import dataclass
    shm = SharedMemory("name", create=True, size=10)

    @dataclass
    class C: 
        buf: memoryview

    c = C(shm.buf[:10])

    shm.close()
    shm.unlink()
    ```
    """
    if name in local_shared_memory_objects:
        return local_shared_memory_objects[name].buf
    elif name in global_shared_memory_objects:
        return global_shared_memory_objects[name].buf
    else:
        # The SharedMemory is not created within the current process
        # because all SharedMemory created in the current process are in
        # `local_shared_memory_objects`
        try:
            shm = SharedMemory(name, create=False, track=False)
            global_shared_memory_objects[name] = shm
            return shm.buf
        except FileNotFoundError as e:
            raise FileNotFoundError(
                f"SharedMemory with name {name} has not been created"
                f" or has already been destroyed.\n{e}"
            )

def _get_shared_memory(name: str) -> SharedMemory:
    """
    Get a shared memory object.
    
    Prefer using `get_memory_view` than this function to access the data.

    Raise FileNotFoundError if the shared memory object is not created or has
    been unlinked
    """
    if name in local_shared_memory_objects:
        return local_shared_memory_objects[name]
    elif name in global_shared_memory_objects:
        return global_shared_memory_objects[name]
    else:
        # The SharedMemory is not created within the current process
        # because all SharedMemory created in the current process are in
        # `local_shared_memory_objects`
        try:
            shm = SharedMemory(name, create=False, track=False)
            global_shared_memory_objects[name] = shm
            return shm
        except FileNotFoundError as e:
            raise FileNotFoundError(
                f"SharedMemory with name {name} has not been created"
                f" or has already been destroyed.\n{e}"
            )


class SharedMemoryHandlee(ABC):
    """
    Base class for handling shared memory objects in a multiprocessing
    environment.

    Features:
        - Automatic shared memory management (creation, cleanup)
        - Data sharing without copy across processes
        - Structured data support through struct module
        - Context manager interface
        - Array-like interface with [] operator

    Implementation Notes:
        1. ALL references to (slices of) .data MUST be manually deleted with 
           `del` before the object is destroyed to prevent memory leaks.
           (You may encounter
            'BufferError: cannot close exported pointers exist',
            when the module is trying to close the internal SharedMemory 
            objects.)
        2. Derived classes must implement __getstate__ and __setstate__ 
           to handle their own attributes unless they do not have their own
           attributes.
        3. For performance-critical code, use .data and .struct properties directly
           instead of [] operators.

    Example:
        TODO add example
        ```python
        
        ```

    Attributes:
        _smh_name (str): The name of the shared memory object.
        _smh_length (int): The length of the shared memory object.
        _smh_struct (Struct | None): The struct format for the shared memory object.
        _smh_data (memoryview): The memory view of the shared memory object.

    Methods:
        data: Returns the memory view of the shared memory object.
        struct: Returns the struct format of the shared memory object.
        __len__: Returns the length of the shared memory object.
        __iter__: Returns an iterator over the shared memory object.
        get_at: Returns the value at a specific index.
        set_at: Sets the value at a specific index.
        __getitem__: Magic method for getting the value at a specific index.
        __setitem__: Magic method for setting the value at a specific index.
        __enter__: Context manager entry method.
        __exit__: Context manager exit method.
        __del__: Destructor method to unlink the shared memory object.
        get_state: Returns the state of the shared memory object.
        set_state: Sets the state of the shared memory object.
        __getstate__: Abstract magic method
        __setstate__: Abstract magic method
    """
    __slots__ = ("_smh_name", "_smh_length", "_smh_struct", "_smh_data")
    def __init__(self, length: int, struct: str | Struct | None = None):
        """
        Initiate a multiprocessing friendly object.

        If no name is provided, a random name in hex with a length of 30 will
        be generated with uuid.uuid4.

        When `struct` is left as None, it will behave more like a simple 
        memoryview.

        Use self.data and self.struct explicitly instead of [ ] in performance
        critical scenarios.
        """
        if length <= 0:
            raise ValueError(f"Length must be positive. Got '{length}'.")
        self._smh_struct = (Struct(struct) if isinstance(struct, str) 
                            else struct)
        size = self._smh_struct.size*length if self._smh_struct else length
        self._smh_name = add_shared_memory(size=size)
        self._smh_length = length
        self._smh_data = get_memory_view(self._smh_name)
    
    @property
    def data(self) -> memoryview:
        return self._smh_data
    
    @property
    def struct(self) -> Struct | None:
        return self._smh_struct
    
    @property
    def size(self) -> int:
        return self._smh_struct.size * self._smh_length

    def __len__(self) -> int:
        return self._smh_length
    
    def __iter__(self) -> Iterator:
        struct = self._smh_struct
        data = self._smh_data
        if struct:
            # This method uses a reference to a slice of _smh_data, which can
            # cause a BufferError if the program terminates before the
            # iterator is deleted.
            # return struct.iter_unpack(
            #     self._smh_data[:struct.size * self._smh_length]
            # )
            item_size = struct.size
            size = self._smh_length * item_size
            return (struct.unpack(data[i:i+item_size])
                    for i in range(0, size, item_size))
        else:
            return (self._smh_data[i] for i in range(self._smh_length))
    
    def get_at(self, index: int):
        """
        Non-magic method alternative to __getitem__

        It performances index range check and support negative indexing.

        Use self.data and self.struct explicitly if performance is critical.
        """
        length = self._smh_length
        if index < 0:
            index = length - index
        if not (0 < index < length):
            raise IndexError(f"Index out of range.")
        
        struct = self._smh_struct
        if struct:
            return (struct.unpack_from(self._smh_data, struct.size*index)
                    if struct else self._smh_data[index])
        else:
            return self._smh_data[index]
    
    def set_at(self, index: int, values):
        """
        Non-magic method alternative to __setitem__

        It performances index range check and support negative indexing.
        
        Use self.data and self.struct explicitly if performance is critical.
        """
        length = self._smh_length
        if index < 0:
            index = length - index
        if not (0 <= index < length):
            raise IndexError(f"Index out of range.")
        
        struct = self._smh_struct
        if struct:
            struct.pack_into(self._smh_data, struct.size*index, *values)
        else:
            self._smh_data[index] = values

    def __getitem__(self, index) -> tuple | bytes:
        return self.get_at(index)
    
    def __setitem__(self, index, *values) -> None:
        self.set_at(index, *values)

    def __enter__(self) -> SharedMemoryHandlee:
        return self
    
    def __exit__(self, exc_type, exc_value, traceback) -> None:
        name = self._smh_name
        shm = _get_shared_memory(name)
        shm.close()
        shm.unlink()
        del local_shared_memory_objects[name]
    
    def __del__(self) -> None:
        # FIXME
        # Somehow in debug mode, close will become None sometimes which leads
        # to an ignored Error: 'TypeError: 'NoneType' object is not callable'
        shm = _get_shared_memory(self._smh_name)
        shm.close()
    
    def get_state(self) -> dict:
        return {
            "name": self._smh_name,
            "length": self._smh_length,
            "struct": self._smh_struct.format if self._smh_struct else None,
        }
    
    def set_state(self, state: dict) -> dict:
        self._smh_name = state["name"]
        self._smh_length = state["length"]
        self._smh_struct = Struct(state["struct"]) if state["struct"] else None
        self._smh_data = get_memory_view(self._smh_name)
    
    def __getstate__(self) -> dict:
        return self.get_state()
    
    def __setstate__(self, state: dict) -> None:
        self.set_state(state)

