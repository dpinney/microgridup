#!/usr/bin/env python


import pathlib, os, time
from PySide6.QtWidgets import QApplication
import src.python.browser as browser
import src.python.docker as docker
import src.python.startup as startup


# - Perform ALL pathing relative to this variable
root_dir = pathlib.Path(__file__).parent


'''
- pyinstaller packaging to create .app or .exe
    - macOS:    $ pyinstaller --windowed -n MicrogridUp --icon ./src/images/NRECA-logo.icns --add-data="src:src" main.py
    - Windows:  $ pyinstaller --windowed -n MicrogridUp --icon ./src/images/NRECA-logo.ico --add-data="src:src" main.py
    - Linux:
- Installer creation
    - macOS: run $ ./build-dmg
    - Windows: use InstallForge (https://installforge.net/) with the provided MicrogridUp-InstallerForgeProfileExample.ifp file. The InstallForge
      configuration will need to be modified to work on your computer. See
      (https://www.pythonguis.com/tutorials/packaging-pyside6-applications-windows-pyinstaller-installforge/#hiding-the-console-window)
    - Linux:
'''


def main():
    '''
    The browser window should only be shown to the user if the Docker container successfully initializes
    '''
    # - Set the Windows taskbar icon
    try:
        from ctypes import windll  # Only exists on Windows.
        myappid = 'nreca.microgridup.desktop_app.1'
        windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except ImportError:
        pass
    app = QApplication()
    web_browser = browser.Browser()
    loading_screen = startup.LoadingScreen()
    container_id = {}

    def success(id):
        # - Refresh the browser before showing it so it shows the MicrogridUp home hpage
        web_browser.home_button.click()
        time.sleep(1)
        web_browser.show()
        loading_screen.close()
        container_id['id'] = id

    def failure(e):
        loading_screen.show_progress('The MicrogridUp app failed to start.')
        exctype, value, traceback = e
        loading_screen.show_progress(traceback)

    loading_screen.initialize_app(success, failure)
    loading_screen.show()
    app.exec()
    d = docker.Docker()
    d.stop_docker(container_id.get('id'))
    # - Force exit without clean-up instead of hanging
    os._exit(0)


if __name__ == '__main__':
    main()