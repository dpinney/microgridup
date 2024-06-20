#!/usr/bin/env python


import pathlib, sys
from PySide6.QtWidgets import QApplication
import src.python.browser as browser
import src.python.docker as docker


# - Perform ALL pathing relative to this variable
root_dir = pathlib.Path(__file__).parent


'''
- Packaging
    - macOS: $ pyinstaller --windowed -n microgridup --add-data="src:src" main.py
    - Windows:
    - Linux:
'''


def main():
    container_id = docker.initialize_docker()
    app = QApplication(sys.argv)
    window = browser.Browser()
    window.show()
    app.exec()
    docker.stop_docker(container_id)


if __name__ == '__main__':
    main()