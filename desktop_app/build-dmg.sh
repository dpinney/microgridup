#!/bin/sh

# - https://www.pythonguis.com/tutorials/packaging-pyqt5-applications-pyinstaller-macos-dmg/

# - Script to create a .dmg on macOS
#   - First, $ brew install create-dmg

# - Run pyinstaller
pyinstaller --windowed -n MicrogridUp --icon ./src/images/NRECA-logo.icns --add-data="src:src" main.py
# - Create a folder to prepare our .dmg
mkdir -p dist/dmg
# - Empty the dmg/ folder
rm -r dist/dmg/*
# - Copy the app bundle to the dmg/ folder
cp -R "dist/MicrogridUp.app" dist/dmg
# If the .dmg already exists, delete it
test -f "dist/MicrogridUp.dmg" && rm "dist/MicrogridUp.dmg"

create-dmg \
  --volname "MicrogridUp Installer" \
  --volicon "./src/images/NRECA-logo.icns" \
  --window-pos 200 120 \
  --window-size 600 300 \
  --icon-size 100 \
  --icon "MicrogridUp.app" 175 120 \
  --hide-extension "MicrogridUp.app" \
  --app-drop-link 425 120 \
  "dist/MicrogridUp.dmg" \
  "dist/dmg/" \
  --filesystem APFS