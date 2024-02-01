#!/usr/bin/python3
import os, time, signal, subprocess, sys, webbrowser
from zipfile import ZipFile
from urllib.request import urlopen
from io import BytesIO

def is_docker_running():
    command = "docker stats --no-stream"
    process = subprocess.Popen(command.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, error = process.communicate()
    if 'error during connect: this error may indicate that the docker daemon is not running' in error.decode() or 'request returned Internal Server Error for API route and version' in error.decode():
        return False
    elif error.decode() == '':
        return True
    else:
        print(f'Unexpected error: {error.decode()}. Output: {output.decode()}')

def signal_handler():
    '''Stops Docker container in event of SIGINT, SIGTERM.'''
    subprocess.run(['docker', 'stop', 'mgucont'])
    sys.exit(0)

def is_docker_installed():
    try:
        subprocess.check_output(['docker', '--version'])
        return True
    except WindowsError:
        return False
    

# Check to see if Docker is installed.
if not is_docker_installed():
    print('Docker is not installed. Please install Docker at https://docs.docker.com/get-docker/ and try again.')
    sys.exit(0)

# Check to see if Docker is running.
if not is_docker_running():
    ''' Start docker if it is not running. '''
    subprocess.Popen(r'C:\Program Files\Docker\Docker\Docker Desktop.exe')
    print('Waiting for Docker to launch...')
    while not is_docker_running():
        print('.', end='', flush=True)
        time.sleep(1)
    print()

# Set directory variables for git clone and volume mount.
HOME_DIR = os.environ['USERPROFILE']
TARGET_DIR = os.path.join(HOME_DIR, 'Documents')
PROJ_DIR = 'microgridup-main'

# Check to see if PROJ_DIR exists in TARGET_DIR. If not, clone repository.
if not os.path.isdir(os.path.join(TARGET_DIR, PROJ_DIR)):
    print('Microgridup folder does not exist, downloading zip...')
    zip_url = 'https://codeload.github.com/dpinney/microgridup/zip/refs/heads/main'
    with urlopen(zip_url) as zip_response:
        with ZipFile(BytesIO(zip_response.read())) as zip_file:
            zip_file.extractall(TARGET_DIR)
else: 
    print('Microgridup folder exists, skipping git clone.')

# Remove previous container.
subprocess.run(['docker','rm','mgucont'])

# Create Docker Compose file as a variable. Must use spaces to indent.
DOCKER_COMPOSE_FILE = f'''
version: "3.9"
services: 
    mguim:
        image: ghcr.io/dpinney/microgridup:main
        container_name: mgucont
        volumes:
            - {os.path.join(TARGET_DIR, PROJ_DIR, 'data', 'projects')}:/data/projects
        ports:
            - "5001:5000"
'''

# Create a subprocess and feed the Compose file string to stdin.
subprocess.run(['docker-compose', '-p', 'mguproj', '-f', '-', 'up','-d'], input=DOCKER_COMPOSE_FILE, text=True)

# Make sure we shut down gracefully in the case of CTRL+C.
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Sleep for 10 seconds to give server time to start.
time.sleep(10)

# Open browser.
webbrowser.open('http://localhost:5001')

print('Server Running at http://localhost:5001. You may stop the container using the stop button in Docker Desktop. Closing this window will not affect the behavior of the server.')