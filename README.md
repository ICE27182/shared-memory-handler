# Shared Memory Handler

`shared-memory-handler` is a simple Python module designed 
to simplify the management of `multiprocessing.shared_memory.SharedMemory` objects. 
It provides an abstraction layer for handling shared memory 
in multiprocessing environments, enabling efficient data sharing
without unnecessary copying.

## Features

- **Automatic Shared Memory Management**: Automatically handles the creation and cleanup of shared memory objects.
- **Simple Data Sharing Without Copying**: Allows passing object as argument while avoiding copying.
- **Structured Data Support**: Supports structured data using Python's `struct` module.
- **Context Manager Interface**: Provides a clean and safe way to manage shared memory objects using `with` statements.
- **Array-like Interface**: Allows intuitive access to shared memory data using the `[]` operator.

## Installation

Clone the repository to your local machine:

```bash
git clone https://github.com/ICE27182/shared-memory-handler.git
cd shared-memory-handler
```

## Usage

### Example: Basic Usage

```python
from shared_memory_handler import SharedMemoryHandlee

# Create a shared memory object with a struct format
class MySharedMemory(SharedMemoryHandlee):
    def __init__(self, length):
        super().__init__(length, struct="i")  # 'i' represents an integer

# Initialize shared memory
shared_memory = MySharedMemory(10)

# Set values
for i in range(10):
    shared_memory[i] = (i,)

# Access values
for i in range(10):
    print(shared_memory[i])

# Cleanup
del shared_memory
```

### Example: Multiprocessing

```python
from multiprocessing import Process
from shared_memory_handler import SharedMemoryHandlee

class MySharedMemory(SharedMemoryHandlee):
    def __init__(self, length):
        super().__init__(length, struct="i")

def worker(shared_memory, start, end):
    for i in range(start, end):
        shared_memory[i] = (i * 2,)

if __name__ == "__main__":
    shared_memory = MySharedMemory(10)

    # Create worker processes
    processes = [
        Process(target=worker, args=(shared_memory, 0, 5)),
        Process(target=worker, args=(shared_memory, 5, 10)),
    ]

    for process in processes:
        process.start()

    for process in processes:
        process.join()

    # Access results
    for i in range(10):
        print(shared_memory[i])

    del shared_memory
```

## Implementation Notes

1. **Memory Management**:
   - All references to (slices of) `.data` **must** be manually deleted using `del` before the object is destroyed to prevent memory leaks.
   - Failure to do so may result in a `BufferError: cannot close exported pointers exist` error when the module attempts to close the internal `SharedMemory` objects.
   - See below for an example

2. **Serialization**:
   - Derived classes must implement `__getstate__` and `__setstate__` to handle their own attributes unless they do not have additional attributes.

3. **Performance**:
   - For performance-critical code, use the `.data` and `.struct` properties directly instead of the `[]` operator.

## Classes and Methods

### `SharedMemoryHandlee`

#### Attributes:
- `_smh_name (str)`: The name of the shared memory object.
- `_smh_length (int)`: The length of the shared memory object.
- `_smh_struct (Struct | None)`: The struct format for the shared memory object.
- `_smh_data (memoryview)`: The memory view of the shared memory object.

#### Methods:
- `data`: Returns the memory view of the shared memory object.
- `struct`: Returns the struct format of the shared memory object.
- `__len__`: Returns the length of the shared memory object.
- `__iter__`: Returns an iterator over the shared memory object.
- `get_at`: Returns the value at a specific index.
- `set_at`: Sets the value at a specific index.
- `__getitem__`: Magic method for getting the value at a specific index.
- `__setitem__`: Magic method for setting the value at a specific index.
- `__enter__`: Context manager entry method.
- `__exit__`: Context manager exit method.
- `__del__`: Destructor method to unlink the shared memory object.
- `get_state`: Returns the state of the shared memory object.
- `set_state`: Sets the state of the shared memory object.
- `__getstate__`: Abstract magic method for serialization.
- `__setstate__`: Abstract magic method for deserialization.

## BufferError: cannot close exported pointers exist
```python
from multiprocessing.shared_memory import SharedMemory
from dataclasses import dataclass
shm = SharedMemory("name", create=True, size=10)

@dataclass
class C: buf: memoryview

c = C(shm.buf[:])
# del c
b = shm.buf[:10]
# del b
a = shm.buf
r_a = a[:10]
# del r_a

# References to SharedMemory.buf not being deleted before closing
# causes 'BufferError: cannot close exported pointers exist'
shm.close()
shm.unlink()
```
