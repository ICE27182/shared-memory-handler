"""
This file contain an example of references to SharedMemory.buf not being 
deleted causing memory leakage
"""

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
