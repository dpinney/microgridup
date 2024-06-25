#!/usr/bin/env python


import pathlib, os
from PySide6.QtWidgets import QApplication
import src.python.browser as browser
import src.python.docker as docker
import src.python.startup as startup


# - Perform ALL pathing relative to this variable
root_dir = pathlib.Path(__file__).parent


'''
- Packaging
    - macOS: $ pyinstaller --windowed -n microgridup --add-data="src:src" main.py
    - Windows:
    - Linux:
'''


def main():
    '''
    - The browser window should only be shown to the user when the LoadingScreen calls the finished_callback() function.
    '''
    app = QApplication()
    web_browser = browser.Browser()
    loading_screen = startup.LoadingScreen(finished_callback=lambda: show_browser(web_browser))
    app.exec()
    d = docker.Docker()
    d.stop_docker(loading_screen.container_id)
    # - Force exit without clean-up instead of hanging
    os._exit(0)


def show_browser(web_browser):
    '''
    - Click on the home button to make the browser refresh before showing it to the user
    '''
    web_browser.home_button.click()
    web_browser.show()


if __name__ == '__main__':
    main()