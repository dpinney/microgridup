#!/usr/bin/env python


import pathlib
from main import root_dir
from PySide6.QtCore import QUrl, Qt, QSize
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QMainWindow, QWidget, QPushButton, QHBoxLayout, QVBoxLayout
from PySide6.QtWebEngineCore import QWebEnginePage
from PySide6.QtWebEngineWidgets import QWebEngineView


class Browser(QMainWindow):
    '''
    - The Browser class encapsulates a PySide6 window with a web view
    '''

    def __init__(self):
        super().__init__()
        with (pathlib.Path(root_dir) / 'src' / 'styles' / 'main.qss').open() as f:
            self.setStyleSheet(f.read())
        self.setWindowTitle('MicrogridUp')
        # - Set up the web view
        self.browser = QWebEngineView()
        self.browser.setPage(CustomWebEnginePage(parent=self))
        self.browser.setUrl(QUrl('http://localhost:5000'))
        # - Set up button(s) by the web view
        self.refresh_button = QPushButton()
        icon = QPixmap(str(pathlib.Path(root_dir) / 'src' / 'images' / 'refresh-icon.svg'))
        self.refresh_button.setIcon(icon)
        self.refresh_button.setIconSize(QSize(24, 24))
        self.refresh_button.clicked.connect(self.browser.reload)
        self.home_button = QPushButton()
        icon = QPixmap(str(pathlib.Path(root_dir) / 'src' / 'images' / 'home-icon.svg'))
        self.home_button.setIcon(icon)
        self.home_button.setIconSize(QSize(30, 30))
        self.home_button.clicked.connect(self.go_home)
        self.help_button = QPushButton()
        icon = QPixmap(str(pathlib.Path(root_dir) / 'src' / 'images' / 'help-icon.svg'))
        self.help_button.setIcon(icon)
        self.help_button.setIconSize(QSize(29, 29))
        self.help_button.clicked.connect(self.go_help)
        # - Set up layout        
        self.horizontal_layout = QHBoxLayout()
        self.button_column = QVBoxLayout()
        self.button_column.addWidget(self.home_button)
        self.button_column.addWidget(self.refresh_button)
        self.button_column.addWidget(self.help_button)
        self.button_column.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.horizontal_layout.addLayout(self.button_column)
        self.browser_column = QVBoxLayout()
        self.browser_column.addWidget(self.browser)
        self.horizontal_layout.addLayout(self.browser_column)
        self.container = QWidget()
        self.container.setLayout(self.horizontal_layout)
        # - Set initial size
        self.resize(QSize(1000, 1000))
        self.setCentralWidget(self.container)

    def go_home(self):
        self.browser.load(QUrl('http://localhost:5000/'))

    def go_help(self):
        self.browser.load(QUrl('http://localhost:5000/doc'))


class CustomWebEnginePage(QWebEnginePage):

    def acceptNavigationRequest(self, url, type_, isMainFrame):
        '''
        - Override this method so that we block access to any websites outside of localhost
        '''
        if url.host() == 'localhost':
            return super().acceptNavigationRequest(url, type_, isMainFrame)

    def createWindow(self, type_):
        '''
        - Override this method so that anchor links with target="_blank" will open in the current tab
        '''
        return self