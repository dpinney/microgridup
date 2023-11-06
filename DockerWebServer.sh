#!/bin/sh

# First, open docker and wait for it to start.
if (! docker stats --no-stream); then
    open -a Docker
    echo "Waiting for Docker to launch..."
    while [[ -z "$(! docker stats --no-stream 2> /dev/null)" ]];
        do printf ".";
        sleep 1
    done
fi

# Target directory for git clone
TARGET_DIR=~/Documents/
PROJ_DIR=microgridup/

# Check to see if folder 'microgridup' exists in current directory, if not clone.
if [ -d "${TARGET_DIR}${PROJ_DIR}" ]; then
    echo "microgridup folder exists, skipping git clone."
else
    echo "microgridup folder does not exist, cloning repo..."
    cd $TARGET_DIR && git clone --depth=1 https://github.com/dpinney/microgridup.git
fi

# Compose file as a variable. MUST USE SPACES TO INDENT!!!
COMPOSE_FILE=$(cat <<-END
version: "3.9"
services:
    mguim:
        image: ghcr.io/dpinney/microgridup:main
        container_name: mgucont
        volumes:
            - ${TARGET_DIR}${PROJ_DIR}/data/projects:/data/projects
        ports:
            - "5000:5000"
END
)

# Start docker app from variable via compose https://stackoverflow.com/a/53696390
# If images aren't downloaded, this will seamlessly download them!
echo "$COMPOSE_FILE" | docker compose -p mguproj -f /dev/stdin up -d

# Make sure we shut down gracefully in the case of CTRL+C
# NOTE: Doesn't work if parent process dies, e.g. the terminal is closed.
# https://stackoverflow.com/questions/22807714/why-i-am-not-getting-signal-sigkill-on-kill-9-command-in-bash
trap "docker stop mgucont" SIGKILL SIGINT SIGTERM

# Sleep for 10 seconds to give server time to start
sleep 10

# Open browser
# Cross platform switching logic, https://stackoverflow.com/questions/394230/how-to-detect-the-os-from-a-bash-script
case "$OSTYPE" in
    solaris*) xdg-open "http://localhost:5000" ;; 
    darwin*)  open "http://localhost:5000" ;; 
    linux*)   xdg-open "http://localhost:5000" ;; 
    bsd*)     xdg-open "http://localhost:5000" ;; 
    msys*)    start "http://localhost:5000" ;;
    cygwin*)  start "http://localhost:5000" ;;
    *)        echo "unknown: $OSTYPE" ;;
esac

# Stop container on user input
read -n1 -r -p "Server Running at http://localhost:5000. Press any key to stop..." key
echo "Gracefully stopping docker container..."
docker stop mgucont