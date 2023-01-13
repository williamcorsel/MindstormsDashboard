import logging

import pygame
from PySide6.QtCore import Qt, QThread
from PySide6.QtGui import QCloseEvent
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import QMainWindow, QMessageBox, QProgressDialog
from serial.tools import list_ports

from odbot.control_worker import ControlWorker, ControlWorkerSignalValues
from odbot.utils import resource_path
from odbot.video_stream import VideoStream

log = logging.getLogger(__name__)

loader = QUiLoader()


class MainWindow(QMainWindow):

    AUTO_CONNECTION_STR = "USB"
    CONNECTED_STR = "Connected"
    DISCONNECTED_STR = "Disconnected"
    MOTOR_OPTIONS = ["A", "B", "C", "D", "E", "F"]
    DEFAULT_ENGINE = "B"
    DEFAULT_STEERING = "A"
    MAINWINDOW_UI_PATH = resource_path("odbot/ui/main_window.ui")

    def __init__(self) -> None:
        super().__init__()
        self.view = loader.load(self.MAINWINDOW_UI_PATH, self)
        self.video_stream = self._start_video_stream()
        self.control_thread = None
        self.control_worker = None
        self.motor_speed, self.motor_steer = self.DEFAULT_ENGINE, self.DEFAULT_STEERING

        # Setup input fields
        self.view.input_engine_port.addItems(self.MOTOR_OPTIONS)
        self.view.input_engine_port.setCurrentText(self.DEFAULT_ENGINE)
        self.view.input_steering_port.addItems(self.MOTOR_OPTIONS)
        self.view.input_steering_port.setCurrentText(self.DEFAULT_STEERING)
        self.view.input_connect.addItems(self._search_ports())
        self.view.input_controller.addItems(self._search_controllers())

        # Assign button signals
        self.view.button_refresh.clicked.connect(self.button_refresh_clicked)
        self.view.button_controller_refresh.clicked.connect(self.button_controller_refresh_clicked)
        self.view.button_video_connect.clicked.connect(self.button_video_connect_clicked)
        self.view.checkbox_od.stateChanged.connect(self.handle_checkbox_od_changed)
        self.view.button_connect_control.clicked.connect(self.button_connect_control_clicked)
        self.view.button_disconnect_control.clicked.connect(self.button_disconnect_control_clicked)

    """
    Qt functions
    """

    def closeEvent(self, event: QCloseEvent):
        if self.video_stream is not None:
            self.video_stream.stop()
        if self.control_worker is not None:
            self.control_worker.stop()
        if self.control_thread is not None:
            self.control_thread.terminate()
            self.control_thread.wait()
        event.accept()

    """
    Button functions
    """

    def button_refresh_clicked(self):
        log.info("Refreshing ports")
        self.view.input_connect.clear()
        self._search_ports()

    def button_disconnect_control_clicked(self):
        self.control_worker.stop()
        self.control_worker = None
        self.view.button_connect_control.setEnabled(True)
        self.view.button_disconnect_control.setEnabled(False)

    def button_controller_connect_clicked(self):
        controller_index = self.view.input_controller.currentIndex()
        log.info(f"Connecting to controller {controller_index}")
        self.controller = self._connect_controller(controller_index)
        if self.controller is not None:
            self.controller_thread = ControlWorker(self.controller, self.hub, self.motor_speed, self.motor_steer)
            self.controller_thread.controller_stopped_signal.connect(self.handle_controller_stopped)
            self.controller_thread.start()
            self.view.label_controller.setText(self.CONNECTED_STR)

    def button_video_connect_clicked(self):
        if self.video_stream:
            self.video_stream.stop()

        self.video_stream = self._start_video_stream()

    def button_controller_refresh_clicked(self):
        log.info("Refreshing controllers")
        self.view.input_controller.clear()
        self._search_controllers()

    def button_connect_control_clicked(self):
        hub_port = self._get_port()
        motor_speed = self.view.input_engine_port.currentText()
        motor_steer = self.view.input_steering_port.currentText()
        controller_idx = self.view.input_controller.currentIndex()

        self.control_thread = QThread()
        self.control_worker = ControlWorker(hub_port, motor_speed, motor_steer, controller_idx)
        self.control_worker.signals.connection.connect(self.handle_control_connection)
        self.control_worker.moveToThread(self.control_thread)
        self.control_thread.started.connect(self.control_worker.run)
        self.control_thread.start()

        self.dialog = QProgressDialog("Connecting to hub...", None, 0, 0, self)
        self.dialog.show()

        log.debug(f"Starting control thread with {hub_port}, {motor_speed}, {motor_steer}, {controller_idx}")

    """
    Signal handle functions
    """

    def handle_controller_stopped(self):
        if self.controller_thread is not None:
            self.controller_thread.stop()
            self.controller_thread.wait()
            self.controller_thread = None
        self.controller.stop()
        self.controller = None
        self.view.label_controller.setText(self.DISCONNECTED_STR)
        _ = QMessageBox.critical(self, "Error", "Controller Error. Please try again.")

    def handle_hub_error(self):
        log.error("Hub Error")
        self.dialog.reject()
        _ = QMessageBox.critical(self, "Error", "Could not connect to hub. Please try again.")
        self.control_worker.stop()

    def handle_controller_error(self):
        log.error("Controller Error")
        _ = QMessageBox.warning(
            self,
            "Warning",
            "Could not connect to controller. You can use the onscreen controls.",
        )

    def handle_control_connect_success(self):
        log.info("Control Connected")
        self.dialog.close()
        self.view.button_connect_control.setEnabled(False)
        self.view.button_disconnect_control.setEnabled(True)

    def handle_control_connection(self, ret):
        if ret == ControlWorkerSignalValues.HUB_CONNECTION_ERROR:
            self.handle_hub_error()
        elif ret == ControlWorkerSignalValues.CONTROLLER_CONNECTION_ERROR:
            self.handle_controller_error()
        elif ret == ControlWorkerSignalValues.CONNECTED:
            self.handle_control_connect_success()

    def handle_video_stream_stopped(self):
        self.view.label_video.setText(self.DISCONNECTED_STR)
        _ = QMessageBox.critical(self, "Error", "Video Stream Error. Please try again.")

    def handle_checkbox_od_changed(self, state: int):
        state = Qt.CheckState(state)
        log.info(f"Checkbox state changed to {state}")
        if state == Qt.Checked:
            self.od_dialog = QProgressDialog("Starting object detection...", None, 0, 0, self)
            self.od_dialog.show()

            self.video_stream.set_object_detection(True)
            self.video_stream.od_thread.initialised.connect(self.od_dialog.accept)
        elif state == Qt.Unchecked:
            self.video_stream.set_object_detection(False)

    """
    Helper functions
    """

    def _parse_video_input(self):
        video_label = str(self.view.input_video.text())
        try:
            video_label = int(video_label)
        except ValueError:
            pass
        return video_label

    def _start_video_stream(self):
        video_label = self._parse_video_input()
        try:
            video_stream = VideoStream(self.view.image_label, video_label)
            video_stream.stream_stopped_signal.connect(self.handle_video_stream_stopped)
            video_stream.start()
            self.view.label_video.setText(self.CONNECTED_STR)
        except ValueError:
            log.error(f"Could not connect to video stream {video_label}")
            self.view.label_video.setText(self.DISCONNECTED_STR)

        return video_stream

    def _search_ports(self):
        # list all available ports in string format
        ports = list_ports.comports()
        items = [self.AUTO_CONNECTION_STR] + [port.device for port in ports]
        return items

    def _get_port(self):
        port = self.view.input_connect.currentText()
        port = None if port == self.AUTO_CONNECTION_STR else port
        return port

    def _search_controllers(self):
        # list all available ports in string format
        pygame.joystick.init()
        no_controllers = pygame.joystick.get_count()
        items = [pygame.joystick.Joystick(i).get_name() for i in range(no_controllers)]
        return items
