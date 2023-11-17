#!/bin/sh

export PATH="$PATH:/usr/local/bin"

# Get local path of Application
FILEPATH=$(dirname $0)
echo $FILEPATH

"$FILEPATH/MicrogridUP_venv/bin/python" $FILEPATH/DockerWebServer.py "$@"