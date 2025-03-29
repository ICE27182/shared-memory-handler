from shared_memory_handler import *

# Simple Demo
from multiprocessing import Process, cpu_count

class MySharedData(SharedMemoryHandlee):
    def __init__(self, values: list[float], 
                    extra: str = "some local data"):
        length = len(values)
        super().__init__(length, struct='d')
        struct = self._smh_struct # or simple self.struct
        item_size = struct.size
        # self._smh_data can also be self.data
        for index, value in zip(range(0, length*item_size, item_size), 
                                values):
            struct.pack_into(self._smh_data, index, value) 
        self.extra = extra
    
    def __getstate__(self):
        state = super().get_state()
        state['extra'] = self.extra
        return state
    
    def __setstate__(self, state):
        super().set_state(state)
        self.extra = state['extra']

def increment(msd: MySharedData) -> None:
        # There exists a little extra property lookup overhead comparing to 
        # directly using self._smh_data and self._smh_struct
        data = msd.data
        struct = msd.struct
        item_size = struct.size
        for i, num in enumerate(msd):
            struct.pack_into(data, i*item_size, num[0] + 1)
        # Manually deleting all references to data/_smh_data and its slices
        del data

if __name__ == "__main__":
    
    msd = MySharedData([1.1*i for i in range(9)])
    print([num for num in msd])

    processes = [Process(target=increment, args=(msd,))
                 for _ in range(cpu_count())]
    
    for process in processes: process.start()
    for process in processes: process.join()

    print([num for num in msd])