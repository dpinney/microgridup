#!/usr/bin/env python


import platform, subprocess, sys, time


if platform.system() == 'Darwin':
    docker_desktop_cmd = 'open -a Docker'
    docker_cli_cmd = '/usr/local/bin/docker'
elif platform.system() == 'Linux':
    docker_desktop_cmd = None
    docker_cli_cmd = None
elif platform.system() == 'Windows':
    docker_desktop_cmd = '"C:/Program Files/Docker/Docker/Docker Desktop.exe"'
    docker_cli_cmd = '"C:/Program Files/Docker/Docker/resources/bin/docker.exe"'
else:
    print('The MicrogridUp app could not determine the operating system.')
    sys.exit()


def initialize_docker():
    '''
    - x
    '''
    # - Start Docker Desktop
    #   - If Docker is already running, this command won't do anything
    #   - Installing Docker Desktop makes the $ docker $ command available, but ONLY after Docker Desktop has been opened and configured by the user
    try:
        subprocess.run(f'{docker_desktop_cmd}', shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError as e:
        print(f'The MicrogridUp app could not start the Docker Desktop application via the cmd command $ {docker_desktop_cmd}. ' +
            'If Docker is not installed, please install and configure Docker from https://docs.docker.com/desktop/. Otherwise start the Docker Desktop application manually.')
        sys.exit()
    # - Pull the image
    try:
        print('Pulling the latest MicrogridUp image. This could take some time...')
        subprocess.run(f'{docker_cli_cmd} pull ghcr.io/dpinney/microgridup:main', shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError as e:
        print('The MicrogridUp app could not pull the ghcr.io/dpinney/microgridup:main Docker image. Please pull the image manually.')
        sys.exit()
    # - Check if the Docker volume already exists
    #   - If it does exist, we don't need to do anything
    try:
        subprocess.run(f'{docker_cli_cmd} volume inspect mgu-volume', shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError as e:
        # - If the volume does not exist, create it and pre-populate it with data
        try:
            subprocess.run(f'{docker_cli_cmd} volume create mgu-volume', shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError as e:
            print('The MicrogridUp app could not create a persistent volume for the container. Please manually create a volume called "mgu-volume".')
            sys.exit()
        try:
            subprocess.run(
                f'{docker_cli_cmd} run --rm --mount type=volume,src="mgu-volume",dst="/mgu-volume" --entrypoint bash ghcr.io/dpinney/microgridup:main "-c" "cp -r /data/projects/* /mgu-volume/"',
                shell=True,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError as e:
            print('The MicrogridUp app could not copy data from the Docker image at data/projects into the persistent volume mounted at data/projects.')
            sys.exit()
    # - Start the container in detached mode with the persistent volume
    start_container_cmd = f'{docker_cli_cmd} run -d --rm -p 5000:5000 --name mgu-container --mount type=volume,source="mgu-volume",target="/data/projects" ghcr.io/dpinney/microgridup:main'
    try:
        p = subprocess.run(start_container_cmd, shell=True, check=True, capture_output=True, encoding='utf-8')
        container_id = p.stdout
    except subprocess.CalledProcessError as e:
        # - If there was an error, try the following:
        try:
            # - Check if the container is still running from a previous run and shut it down
            subprocess.run(f'{docker_cli_cmd} stop mgu-container', shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(10)
            # - Try to start it again
            p = subprocess.run(start_container_cmd, shell=True, check=True, capture_output=True, encoding='utf-8')
            container_id = p.stdout
        except subprocess.CalledProcessError as e:
            # - If we still failed, then port 5000 probably isn't available
            print('The MicrogridUp app could not start the Docker container and bind the web server on port 5000. Please check that port 5000 is open on your local machine.')
            sys.exit()
    # - Wait for the web server to start
    time.sleep(20)
    return container_id


def stop_docker(container_id):
    try:
        subprocess.run(f'{docker_cli_cmd} stop {container_id}', shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError as e:
        print('The MicrogridUp app could not stop the Docker container.')
        sys.exit()


if __name__ == '__main__':
    pass