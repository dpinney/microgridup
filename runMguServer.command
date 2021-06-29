#!/bin/sh
# Command to start up the MicrogridUP web server locally. Works on Unix, macOS.
script_dir=$(dirname "$0")
cd "$script_dir"
python microgridup_gui.py
read -n1 -r -p "Server stopped. Press space to continue..." key