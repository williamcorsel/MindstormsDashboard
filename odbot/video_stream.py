import logging
from typing import Union

import cv2
import numpy as np
from PySide6 import QtGui
from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel

from odbot.models.yolov5 import YoloV5Model

log = logging.getLogger(__name__)


class VideoWorker(QObject):
    change_pixmap_signal = Signal(np.ndarray)
    stream_stopped_signal = Signal()

    def __init__(self, device: Union[int, str]):
        super().__init__()
        self._device = device
        self._run_flag = True

    def run(self):
        # capture from web cam
        log.debug(f"Starting video thread for device {self._device}")
        cap = cv2.VideoCapture(self._device)

        if cap is None or not cap.isOpened():
            log.debug(f"Stopping video thread for device {self._device}")
            self._run_flag = False
            self.stream_stopped_signal.emit()

        while self._run_flag:
            ret, cv_img = cap.read()
            if ret:
                self.change_pixmap_signal.emit(cv_img)
        # shut down capture system
        cap.release()

    def stop(self):
        """Sets run flag to False and waits for thread to finish"""
        self._run_flag = False

    def is_running(self):
        return self._run_flag


class VideoStream(QObject):
    stream_stopped_signal = Signal()
    od_started_signal = Signal()

    def __init__(self, pixmap_label: QLabel, device: Union[int, str] = 0):
        super().__init__()
        self.label = pixmap_label
        self.display_width, self.display_height = self.label.width(), self.label.height()
        self.worker = VideoWorker(device=device)
        self.worker.change_pixmap_signal.connect(self.update_image)
        self.worker.stream_stopped_signal.connect(self.handle_stream_stopped)
        self.thread = QThread()
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)

        self.od_thread = None
        self.cv_img = None

        log.info(f"Created stream with device {self.label}")

    def start(self):
        self.thread.start()

    def stop(self):
        if self.od_thread is not None:
            self.od_thread.stop()
        self.worker.stop()
        self.thread.terminate()
        self.thread.wait()

    def handle_stream_stopped(self):
        self.stream_stopped_signal.emit()
        self.stop()

    def set_object_detection(self, enabled: bool):
        if enabled:
            self.od_thread = OdThread(video_stream=self)
            self.od_thread.start()
        else:
            self.od_thread.stop()

    @Slot(np.ndarray)
    def update_image(self, cv_img: np.ndarray):
        """Updates the image_label with a new opencv image"""
        self.cv_img = cv_img
        qt_img = self.convert_cv_qt(cv_img)
        self.label.setPixmap(qt_img)

    def get_img(self):
        return self.cv_img

    def _print_detections(self, img: np.ndarray):
        if self.od_thread is None or self.od_thread.predictions is None:
            return img

        for pred in self.od_thread.predictions:
            # convert pred to int
            xmin, ymin, xmax, ymax, conf, object_class = pred
            xmin, ymin, xmax, ymax = int(xmin), int(ymin), int(xmax), int(ymax)
            object_class = self.od_thread.model.names[int(object_class)]

            img = cv2.rectangle(img, (xmin, ymin), (xmax, ymax), (0, 255, 0), 2)
            img = cv2.putText(img, f"{object_class} {conf:.2f}", (xmin, ymin), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0),
                              2)

        return img

    def convert_cv_qt(self, cv_img: np.ndarray):
        """Convert from an opencv image to QPixmap"""
        det_img = self._print_detections(cv_img)
        rgb_image = cv2.cvtColor(det_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        convert_to_Qt_format = QtGui.QImage(rgb_image.data, w, h, bytes_per_line, QtGui.QImage.Format.Format_RGB888)
        p = convert_to_Qt_format.scaled(self.display_width, self.display_height, Qt.AspectRatioMode.KeepAspectRatio)
        return QPixmap.fromImage(p)


class OdThread(QThread):
    initialised = Signal()

    def __init__(self, video_stream: VideoStream, parent=None) -> None:
        super().__init__(parent)
        self.video_stream = video_stream
        self._run_flag = True
        self.predictions = None

    def load_model(self):
        self.model = YoloV5Model()
        self.initialised.emit()

    def run(self):
        self.load_model()
        while self._run_flag:
            img = self.video_stream.get_img()
            if img is None:
                continue

            self.predictions = self.model.get_predictions(img)

    def start(self):
        """Start the thread"""
        self._run_flag = True
        super().start()

    def stop(self):
        """Sets run flag to False and waits for thread to finish"""
        self._run_flag = False
        self.wait()
        self.predictions = None
