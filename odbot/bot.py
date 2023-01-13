import logging

from mindstorms import Hub
from PySide6.QtCore import QThread

log = logging.getLogger(__name__)


class Bot:

    def __init__(self, serial_port: str, motor_speed_port: str, motor_steer_port: str) -> None:
        self.serial_port = serial_port
        self.motor_speed_port = motor_speed_port
        self.motor_steer_port = motor_steer_port

        self.connect_hub()

    def connect_hub(self):
        self.hub = Hub(device=self.serial_port)
        self.motor_speed = eval(f"self.hub.port.{self.motor_speed_port}.motor")
        self.motor_steer = eval(f"self.hub.port.{self.motor_steer_port}.motor")

        QThread.msleep(700)

        self.motor_steer.mode([(1, 0), (2, 0), (3, 0), (0, 0)])
        self.play_sound('/extra_files/Hello')

    def steer(self, position: int):
        log.debug(f"Steering to {position}")
        self.motor_steer.run_to_position(position)

    def accelerate(self, speed: int):
        self.motor_speed.run_at_speed(speed)

    def get_steer_position(self, relative: bool = True, absolute: bool = False):
        _, relative_value, absolute_value, _ = self.motor_steer.get()

        ret = [relative_value, absolute_value
               ] if relative and absolute else relative_value if relative else absolute_value
        return ret

    def set_steer_middle(self, value: int):
        log.debug(f"Setting steering middle to {value}")
        self.motor_steer.preset(value)

    def disconnect_hub(self):
        self.hub.close()

    def play_sound(self, path: str):
        self.hub.sound.play(path)
