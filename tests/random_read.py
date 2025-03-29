
from shared_memory_handler import SharedMemoryHandlee
from dataclasses import dataclass
from random import sample, seed, randint, random
from math import sin, cos, pi
from timeit import timeit
seed(0)
N = 8192
M = 10_000
order = sample(range(N), N)
order = range(N)
forloop_overhead = timeit("for i in order: pass", number=10_000, globals=globals()) * M / 10_000
print(f"{forloop_overhead=}\n{'-'*80}")
###############################################################
# Frame Buffers 24 with bytes
###############################################################
seed(0)
builtin_bytearray = bytearray(randint(0, 255) for _ in range(N * 3))

class MySharedMemoryBytes(SharedMemoryHandlee): pass
shm_bytes = MySharedMemoryBytes(N * 3)
shm_bytes_data = shm_bytes.data
shm_bytes_data[:N*3] = builtin_bytearray
###############################################################
print(
    "builtin_bytearray",
    timeit(
        "for i in order:\n"
        " address = i*3\n"
        " r = builtin_bytearray[address]\n"
        " g = builtin_bytearray[address+1]\n"
        " b = builtin_bytearray[address+2]",
        number=M,
        globals=globals(),
    ) - forloop_overhead,
)
print(
    "shm_bytes",
    timeit(
        "for i in order:\n"
        " address = i*3\n"
        " r = shm_bytes_data[address]\n"
        " g = shm_bytes_data[address+1]\n"
        " b = shm_bytes_data[address+2]\n",
        number=M,
        globals=globals(),
    ) - forloop_overhead,
)

###############################################################
# Frame Buffers 24 with class
###############################################################
@dataclass(slots=True)
class Color24:
    r: int
    g: int
    b: int
seed(0)
builtin_tuple_color24 = tuple(Color24(randint(0, 255), 
                             randint(0, 255), 
                             randint(0, 255)) 
                     for _ in range(N))

class MySharedMemoryStructBBB(SharedMemoryHandlee):
    def __init__(self, length):
        super().__init__(length, "BBB")
shm_bbb = MySharedMemoryStructBBB(N)
for i in range(N):
    shm_bbb[i] = builtin_tuple_color24[0].r, builtin_tuple_color24[0].g, builtin_tuple_color24[0].b
shm_bbb_data = shm_bbb.data
shm_bbb_struct = shm_bbb.struct
shm_bbb_struct_size = shm_bbb_struct.size
###############################################################
print(
    "builtin_tuple_color24",
    timeit(
        "for i in order:\n"
        " color = builtin_tuple_color24[i]\n"
        " r = color.r\n"
        " g = color.g\n"
        " b = color.b\n",
        number=M,
        globals=globals(),
    ) - forloop_overhead,
)
print(
    "shm_bbb",
    timeit(
        "for i in order:\n"
        " r, g, b = shm_bbb_struct.unpack_from(shm_bbb_data, shm_bbb_struct_size * i)\n",
        number=M,
        globals=globals(),
    ) - forloop_overhead,
)

###############################################################
# Normal fff
###############################################################
@dataclass(slots=True)
class Normal:
    x: float
    y: float
    z: float
seed(0)
builtin_tuple_normal = tuple(Normal(cos(a)*cos(b),
                             sin(b),
                             sin(a)*cos(b))
                      for _ in range(N)
                      if (a := random()*2*pi) and (b :=random()*2*pi))

class MySharedMemoryStructFFF(SharedMemoryHandlee):
    def __init__(self, length):
        super().__init__(length, "fff")
shm_fff = MySharedMemoryStructFFF(N)
for i in range(N):
    shm_fff[i] = builtin_tuple_normal[0].x, builtin_tuple_normal[0].y, builtin_tuple_normal[0].z
shm_fff_data = shm_fff.data
shm_fff_struct = shm_fff.struct
shm_fff_struct_size = shm_fff_struct.size
###############################################################
print(
    "builtin_tuple_normal",
    timeit(
        "for i in order:\n"
        " normal = builtin_tuple_normal[i]\n"
        " x = normal.x\n"
        " y = normal.y\n"
        " z = normal.z\n",
        number=M,
        globals=globals(),
    ) - forloop_overhead,
)
print(
    "shm_fff",
    timeit(
        "for i in order:\n"
        " x, y, z = shm_fff_struct.unpack_from(shm_fff_data, shm_fff_struct_size * i)\n",
        number=M,
        globals=globals(),
    ) - forloop_overhead,
)
