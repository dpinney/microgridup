#!/usr/bin/env python


import sys, traceback, platform, pathlib
from PySide6.QtGui import QIcon
from PySide6.QtCore import QRunnable, Slot, QThreadPool, Signal, QObject, QSize, Qt
from PySide6.QtWidgets import QVBoxLayout, QLabel, QWidget, QMainWindow
import main
import src.python.docker as docker


class LoadingScreen(QMainWindow):
    '''
    Show the user a screen of the Docker container initialization so they don't think the application is slow and broken
    '''

    def __init__(self):
        super().__init__()
        if platform.system() == 'Windows':
            icon = QIcon(str(pathlib.Path(main.root_dir) / 'src' / 'images' / 'NRECA-logo.ico'))
            self.setWindowIcon(icon)
        self.setWindowTitle('Loading MicrogridUp...')
        self.threadpool = QThreadPool()
        self.label = QLabel('Initializing the Docker container...')
        font = self.label.font()
        font.setPointSize(10)
        self.label.setFont(font)
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.label)
        w = QWidget()
        w.setLayout(layout)
        self.setCentralWidget(w)
        self.resize(QSize(1000, 1000))

    def initialize_app(self, success_callback, failure_callback):
        '''
        Launch a worker thread to initialize the Docker container

        :param success_callback: the function to call when the Docker container has successfully initialized
        :type success_callback: function
        :param failure_callback: the function to call when the Docker container fails to initialize
        :type failure_callback: function
        '''
        worker = Worker(self.initialize_docker)
        worker.signals.progress.connect(self.show_progress)
        worker.signals.result.connect(success_callback)
        worker.signals.error.connect(failure_callback)
        self.threadpool.start(worker)

    def initialize_docker(self, progress_signal):
        '''
        This function runs in its own thread so it doesn't block the Qt event loop thread (i.e. it doesn't freeze the GUI)

        :param progress_signal: the function that the Docker instance should call to report on its progress. This argument is automatically passed
            into this function by the Worker instance
        :type progress_callback: PySide6.QtCore.Signal
        :return: the ID of the started container
        :rtype: str
        '''
        d = docker.Docker(progress_signal.emit)
        return d.initialize_docker()

    def show_progress(self, msg):
        '''
        Show the user that the Docker container is initializing when the Worker instance emits the "progress" signal
        '''
        self.label.setText(self.label.text() + '\n' + msg)


class Worker(QRunnable):
    '''
    Subclass the QRunnable class so that we can spawn threads with custom initialization logic, signals, and behavior
    '''

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        # - Always include the "progress" signal as the progress_signal argument to the function which will run in a separate thread
        self.kwargs['progress_signal'] = self.signals.progress

    @Slot()
    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            self.signals.result.emit(result)


class WorkerSignals(QObject):
    '''
    Define custom signals so that the Worker instances can emit signals to the Qt event loop thread
    '''
    progress = Signal(str)
    result = Signal(object)
    error = Signal(tuple)


if __name__ == '__main__':
    pass