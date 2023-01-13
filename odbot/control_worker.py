import logging

import pygame
from mindstorms import Hub
from PySide6.QtCore import QObject, QThread, Signal

from odbot.bot import Bot
from odbot.controller import Controller, XboxOneControllerButtons

log = logging.getLogger(__name__)

LEFT_STEER_VALUE = 60
RIGHT_STEER_VALUE = -60


class ControlWorkerSignalValues:
    CONNECTED = 0
    HUB_CONNECTION_ERROR = 1
    CONTROLLER_CONNECTION_ERROR = 2


class ControlWorkerSignals(QObject):
    events = Signal(list)
    controller_stopped_signal = Signal()
    connection = Signal(int)


class ControlWorker(QObject):

    signals = ControlWorkerSignals()

    LOOP_DELAY_MS = 200
    STEER_BUFFER = 15  # Degrees to buffer the steering

    def __init__(self, hub_port: str, motor_speed: str, motor_steer: str, controller_idx: int):
        super().__init__()
        self.motor_speed_str = motor_speed
        self.motor_steer_str = motor_steer
        self.controller_idx = controller_idx
        self.hub_port = hub_port
        self.running = True

        self.bot = None
        self.controller = None

        self.left_steer_value = LEFT_STEER_VALUE
        self.right_steer_value = RIGHT_STEER_VALUE
        self.middle_steer_value = None
        self.total_angle = None

    def _calculate_steering_middle(self, left: int, right: int):
        middle = int((left + right) / 2)
        total_angle = int(abs(left) + abs(right))
        return middle, total_angle

    def _map_steering(self, value: float):
        return self.middle_steer_value + int(value * (self.middle_steer_value -
                                                      (self.total_angle // 2 - self.STEER_BUFFER)))

    def _calibrate_steering(self):
        self.bot.steer(-180)
        QThread.msleep(1000)
        left_steer_value = self.bot.get_steer_position()
        self.bot.steer(180)
        QThread.msleep(1000)
        right_steer_value = self.bot.get_steer_position()
        middle, total_angle = self._calculate_steering_middle(left_steer_value, right_steer_value)
        self.bot.steer(middle)
        QThread.msleep(1000)
        # middle_abs = self.bot.get_steer_position(absolute=True, relative=False)
        # self.bot.set_steer_middle(middle_abs)
        # QThread.msleep(1000)

        log.info(f"Calibrated steering: left={left_steer_value}, right={right_steer_value}, middle={middle}")
        return left_steer_value, right_steer_value, middle, total_angle

    def init_bot(self):
        log.debug("Initializing bot")
        try:
            self.bot = Bot(self.hub_port, self.motor_speed_str, self.motor_steer_str)
        except Exception as e:
            log.error(f"Error initializing bot: {e}")
            self.signals.connection.emit(ControlWorkerSignalValues.HUB_CONNECTION_ERROR)
            return False

        return True

    def init_controller(self):
        log.debug("Initializing controller")
        try:
            self.controller = Controller(index=self.controller_idx)
        except Exception as e:
            log.error(f"Error initializing controller: {e}")
            self.controller = None
            self.signals.connection.emit(ControlWorkerSignalValues.CONTROLLER_CONNECTION_ERROR)

    def run(self):
        log.debug("Starting control worker")
        if not self.init_bot():
            self.stop()
            return

        self.init_controller()
        self.signals.connection.emit(ControlWorkerSignalValues.CONNECTED)

        self.left_steer_value, self.right_steer_value, self.middle_steer_value, self.total_angle = self._calibrate_steering(
        )

        while self.running:

            if self.controller is not None:
                trigger_right, trigger_left, right_x = self.check_control_events()
                speed = trigger_right + trigger_left

                if self.bot is not None:
                    try:
                        self.bot.accelerate(speed)
                        if abs(right_x) > 0:
                            self.bot.steer(right_x)
                        else:
                            self.bot.steer(self.middle_steer_value)
                    except Exception as e:
                        log.error(f"Error controlling bot: {e}")

            if self.bot is not None:
                bot_pos = self.bot.get_steer_position(absolute=True)
                log.info(f"Bot position: relative {bot_pos[0]}, absolute {bot_pos[1]}")

            QThread.msleep(self.LOOP_DELAY_MS)

    def check_control_events(self):
        if self.controller is None:
            return None, None, None
        self.controller.update()
        # self.signals.events.emit(self.controller.events)

        for event in self.controller.events:
            if event.type == pygame.JOYBUTTONDOWN:
                if event.button == XboxOneControllerButtons.BUTTON_A:
                    log.info("A pressed")
                    self.bot.play_sound('/extra_files/Hi')

            if event.type == pygame.JOYDEVICEREMOVED:
                log.warning("Controller disconnected")
                self.signals.controller_stopped_signal.emit()
                self.stop()

        trigger_right = self.controller.axis_data[XboxOneControllerButtons.AXIS_RIGHT_TRIGGER]
        trigger_right = 0 if trigger_right == 0 else int((trigger_right + 1) / 2 * -100)

        trigger_left = self.controller.axis_data[XboxOneControllerButtons.AXIS_LEFT_TRIGGER]
        trigger_left = 0 if trigger_left == 0 else int((trigger_left + 1) / 2 * 100)

        right_x = self.controller.axis_data[XboxOneControllerButtons.AXIS_LEFT_X]
        right_x = 0 if abs(right_x) <= 0.1 else self._map_steering(right_x)

        return trigger_right, trigger_left, right_x

    def stop(self):
        if self.bot is not None:
            self.bot.disconnect_hub()
        self.running = False
