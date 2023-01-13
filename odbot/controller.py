import logging

import pygame

log = logging.getLogger(__name__)


class XboxOneControllerButtons:
    AXIS_LEFT_X = 0
    AXIS_LEFT_Y = 1
    AXIS_RIGHT_X = 2
    AXIS_RIGHT_Y = 3
    AXIS_LEFT_TRIGGER = 4
    AXIS_RIGHT_TRIGGER = 5

    BUTTON_A = 0
    BUTTON_B = 1
    BUTTON_X = 2
    BUTTON_Y = 3
    BUTTON_LEFT_BUMPER = 4
    BUTTON_RIGHT_BUMPER = 5
    BUTTON_BACK = 6
    BUTTON_START = 7
    BUTTON_LEFT_STICK = 8
    BUTTON_RIGHT_STICK = 9


class Controller:

    def __init__(self, index: int = 0):
        pygame.init()
        pygame.joystick.init()

        self.controller = pygame.joystick.Joystick(index)

        self.axis_data = {}
        self.button_data = {}
        self.hat_data = {}
        self.events = []

        # Get the number of axes, buttons, and hats on the controller
        self.axes = self.controller.get_numaxes()
        self.buttons = self.controller.get_numbuttons()
        self.hats = self.controller.get_numhats()

        log.info(f"Controller: {self.controller.get_name()} connected")

    def update(self):
        self.events = pygame.event.get()

        # Update the axis data
        for i in range(self.axes):
            self.axis_data[i] = self.controller.get_axis(i)

        # Update the button data
        for i in range(self.buttons):
            self.button_data[i] = self.controller.get_button(i)

        # Update the hat data
        for i in range(self.hats):
            self.hat_data[i] = self.controller.get_hat(i)

    def get_axis_value(self, axis: int):
        return self.controller.get_axis(axis)

    def get_button_value(self, button: int):
        return self.controller.get_button(button)

    def stop(self):
        self.controller.quit()
        pygame.joystick.quit()
        pygame.quit()
