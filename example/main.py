

from __future__ import annotations

from multiprocessing import Process, cpu_count, current_process
from struct import Struct
from shared_memory_handler import SharedMemoryHandlee
from math import cos, sin, pi
from collections.abc import Iterable
from dataclasses import dataclass
from time import sleep, time
from shutil import get_terminal_size

# Set to False to run it in the main process
USE_MULTI_PROCESSING = True

class Buffer(SharedMemoryHandlee):
    __slots__ = ("width", "height") + SharedMemoryHandlee.__slots__
    def __init__(self, width: int, height: int, struct: Struct | str | int | None):
        if isinstance(struct, int):
            super().__init__(width*height*struct, None)
        else:
            super().__init__(width*height, struct)
        self.width = width
        self.height = height
    def __getstate__(self) -> dict:
        state = super().get_state()
        state["width"] = self.width
        state["height"] = self.height
        return state

    def __setstate__(self, state: dict) -> None:
        super().set_state(state)
        self.width = state["width"]
        self.height = state["height"]


class NormalBuffer(Buffer):
    __slots__ = Buffer.__slots__
    def __init__(self, width, height):
        super().__init__(width, height, "ddd")
    
    def default(self):
        width, height = self.width, self.height
        struct, data = self._smh_struct, self._smh_data
        item_size = struct.size
        for y in range(height):
            y_ =  pi / 2 + (abs(y % 30*2 - 30) - 30*0.5) * 0.1
            # y_ =  pi / 2
            for x in range(width):
                x_ = x*pi/20
                v = (
                    cos(x_)*cos(y_), 
                    sin(x_)*cos(y_),
                    -abs(sin(y_))
                )
                struct.pack_into(data, 
                                 (y*width + x)*item_size, 
                                 *v)

class FrameBuffer(Buffer):
    __slots__ = Buffer.__slots__
    def __init__(self, width, height):
        super().__init__(width, height, 3)
    
    def display(self) -> None:
        data = self.data
        width = self.width
        byte_row_width = width * 3
        format_str = ("\033[48;2;%d;%d;%dm  " * width) + "\033[0m\n"
        str_buff = (
            (format_str % tuple(data[y : y+byte_row_width]))
            for y in range(0, self.height*byte_row_width, byte_row_width)
        )
        print("".join(str_buff), end="")
    
    def default(self) -> None:
        for i in range(0, len(self), 3):
            self[i] = 64
            self[i+1] = 32
            self[i+2] = 24
    
    @classmethod
    def from_normal_buffer(cls, normal_buffer: Buffer) -> FrameBuffer:
        width, height = normal_buffer.width, normal_buffer.height
        frame_buffer = cls(width, height)
        data = frame_buffer._smh_data
        for i, normal in enumerate(normal_buffer):
            data[i*3 + 0] = int((1 - normal[0]) * 255 / 2)
            data[i*3 + 1] = int((1 - normal[1]) * 255 / 2)
            data[i*3 + 2] = int((1 - normal[2]) * 255 / 2)
        return frame_buffer


@dataclass(slots=True)
class Light:
    x: float = 0
    y: float = 0
    z: float = 0
    r: float = 1
    g: float = 1
    b: float = 1

@dataclass(slots=True)
class Camera:
    x: float = 40
    y: float = 15
    z: float = 0

def worker(frame_buffer: FrameBuffer, normal_buffer: NormalBuffer, 
           lights: Iterable[Light], camera: Camera, 
           process_no: int | None = None, process_num: int | None = None):
    width, height = normal_buffer.width, normal_buffer.height
    if process_no is not None and process_num is not None:
        vertical_range = range(height * process_no // process_num, 
                               height * (process_no+1) // process_num)
    else:
        vertical_range = range(height)
    frame_data = frame_buffer._smh_data
    normals_struct = normal_buffer._smh_struct
    normals_item_size = normals_struct.size
    normals_data = normal_buffer._smh_data
    z = 10
    k_d, k_s, shininess = 1.0, 0.2, 1
    for y in vertical_range:
        for x in range(width):
            normal_x, normal_y, normal_z = normals_struct.unpack_from(normals_data, normals_item_size*(y*width + x))
            illuminance_r, illuminance_g, illuminance_b = 0, 0, 0
            for light in lights:
                light_dx = light.x-x
                light_dy = light.y-y
                light_dz = light.z-z
                # fragment to camera distance is disgarded
                dist_sqr = (light_dx*light_dx
                            + light_dy*light_dy
                            + light_dz*light_dz)
                distance = dist_sqr**0.5
                dist_coef = 1 / (1 + 0.1*distance + 0.01*dist_sqr)
                
                inv_distance = 1 / distance
                incident_x = light_dx * inv_distance
                incident_y = light_dy * inv_distance
                incident_z = light_dz * inv_distance

                normal_coef = (2*normal_x*incident_x
                               + 2*normal_y*incident_y
                               + 2*normal_z*incident_z)
                reflection_x = normal_x*normal_coef - incident_x
                reflection_y = normal_y*normal_coef - incident_y
                reflection_z = normal_z*normal_coef - incident_z
                intensity = (
                    k_d * (
                        normal_x*incident_x
                        + normal_y*incident_y
                        + normal_z*incident_z
                    )
                    + k_s * max(
                        (camera.x - x)*reflection_x
                        + (camera.y - y)*reflection_y
                        + (camera.z - z)*reflection_z,
                        0
                    )**shininess
                ) * dist_coef
                if intensity > 0:
                    illuminance_r += intensity * light.r
                    illuminance_g += intensity * light.g
                    illuminance_b += intensity * light.b
            address = (y*width + x)*3
            frame_data[address+0] = r if (r:=round((illuminance_r+0.5)*frame_data[address+0])) < 255 else 255
            frame_data[address+1] = g if (g:=round((illuminance_g+0.5)*frame_data[address+1])) < 255 else 255
            frame_data[address+2] = b if (b:=round((illuminance_b+0.5)*frame_data[address+2])) < 255 else 255

    

if __name__ == "__main__":
    width, height = get_terminal_size().columns // 2, get_terminal_size().lines - 4
    frame_buffer = FrameBuffer(width, height)
    frame_buffer.default()

    normal_buffer = NormalBuffer(width, height)
    normal_buffer.default()
    FrameBuffer.from_normal_buffer(normal_buffer).display()
    t = 0
    print("\033[?25l")
    start = time()
    while True:
        x = abs(t%(width*2) - width) 
        y = x*height/width

        y = abs(t//(width / 3)%(height*2) - height)
        if USE_MULTI_PROCESSING:
            processes = [Process(target=worker, 
                                 args=(frame_buffer, normal_buffer, 
                                       (Light(x, y, 5),), Camera(width//2, height//2), 
                                       i, cpu_count()))
                    for i in range(cpu_count())]
            for process in processes: process.start()
            for process in processes: process.join()
        else:
            worker(frame_buffer, normal_buffer, (Light(x, y, 5),), Camera(width//2, height//2))
        frame_buffer.display()
        print(f"{x=:<4} {y=:<4} {width=:<4} {height=:<4} FPS:{1 / (time() - start):.3f}")
        start = time()
        print("\033[F"*(height+2), end="")

        frame_buffer.default()
        t += 1

