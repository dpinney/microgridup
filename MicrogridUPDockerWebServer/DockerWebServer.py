import docker, os, time, signal, subprocess, webbrowser

def is_docker_running():
    '''Returns True if Docker daemon is running, otherwise False.'''
    try:
        client = docker.from_env()
        return True
    except docker.errors.DockerException:
        return False
    
def signal_handler():
    '''Stops Docker container in event of SIGINT, SIGTERM.'''
    client.containers.get('mgucont').stop()
    exit(0)

# Check to see if Docker is running.
if not is_docker_running():
    subprocess.run(['open', '-a', 'Docker'])
    print('Waiting for Docker to launch...')
    while not is_docker_running():
        print('.', end='', flush=True)
        time.sleep(1)
    print()

# Set directory variables for git clone and volume mount.
HOME_DIR = os.path.expanduser('~')
TARGET_DIR = os.path.join(HOME_DIR, 'Documents')
PROJ_DIR = 'microgridup'

# Check to see if PROJ_DIR exists in TARGET_DIR. If not, clone repository.
if not os.path.isdir(os.path.join(TARGET_DIR, PROJ_DIR)):
    print('Microgridup folder does not exist, cloning repo...')
    os.chdir(TARGET_DIR)
    subprocess.run(['git','clone','--depth=1','https://github.com/dpinney/microgridup.git'])
else: 
    print('Microgridup folder exists, skipping git clone.')

# Create Docker Compose file as a variable. Must use spaces to indent.
DOCKER_COMPOSE_FILE = f'''
version: "3.9"
services: 
    mguim:
        image: ghcr.io/dpinney/microgridup:main
        container_name: mgucont
        volumes:
            - {os.path.join(TARGET_DIR, PROJ_DIR)}/data/projects:/data/projects
        ports:
            - "5000:5000"
'''

# Initialize Docker client.
client = docker.from_env()

# Create a subprocess and feed the Compose file string to stdin.
subprocess.run(['docker-compose', '-p', 'mguproj', '-f', '-', 'up','-d'], input=DOCKER_COMPOSE_FILE, text=True)

# Make sure we shut down gracefully in the case of CTRL+C.
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Sleep for 10 seconds to give server time to start.
time.sleep(10)

# Open browser.
webbrowser.open('http://localhost:5000')

# Stop container on user input. 
subprocess.run(['read', '-n1', '-r', '-p', 'Server Running at http://localhost:5000. Press any key to stop...', 'key'])
# subprocess.run(['docker', 'stop', 'mgucont'])
print('Gracefully stopping docker container...')
client.containers.get('mgucont').stop()