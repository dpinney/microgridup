#!/usr/bin/env python


import sys, traceback
from PySide6.QtCore import QRunnable, Slot, QThreadPool, Signal, QObject, QSize, Qt
from PySide6.QtWidgets import QVBoxLayout, QLabel, QWidget, QMainWindow
import src.python.docker as docker


class LoadingScreen(QMainWindow):
    '''
    Show the user a screen of the Docker container initialization so they don't think the application is slow and broken
    '''

    def __init__(self, finished_callback):
        '''
        :param finished_callback: the function to call when the Docker container has finished initializing
        :type finished_callback: function
        '''
        super().__init__()
        self.setWindowTitle('Loading MicrogridUp...')
        self.container_id = 'mgu-container'
        self.finished_callback = finished_callback
        self.label = QLabel('Initializing the Docker container...')
        font = self.label.font()
        font.setPointSize(15)
        self.label.setFont(font)
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.label)
        w = QWidget()
        w.setLayout(layout)
        self.setCentralWidget(w)
        self.resize(QSize(1000, 1000))
        self.show()
        self.threadpool = QThreadPool()
        self.spawn_docker_with_external_thread()

    def spawn_docker_with_external_thread(self):
        worker = Worker(self.initialize_docker)
        worker.signals.result.connect(self.set_container_id)
        worker.signals.finished.connect(self.display_finished_message)
        worker.signals.finished.connect(self.finished_callback)
        worker.signals.progress.connect(self.show_progress)
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

    def set_container_id(self, id):
        '''
        Store the ID of the container that was just started when the Worker instance emits the "result" signal

        :param id: the ID of the container
        :type id: str
        '''
        self.container_id = id

    def display_finished_message(self):
        '''
        Show the user that the Docker container has started when the Worker instance emits the "finished" signal
        '''
        self.label.setText(self.label.text() + '\n' + 'The Docker container has started!')
        self.close()

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
        # - Always include the "progress" signal as the progress_siganl argument to the function which will run in a separate thread
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
        finally:
            self.signals.finished.emit()


class WorkerSignals(QObject):
    '''
    Define custom signals so that the Worker instances can emit signals to the Qt event loop thread
    '''
    finished = Signal()
    error = Signal(tuple)
    result = Signal(object)
    progress = Signal(str)


if __name__ == '__main__':
    pass