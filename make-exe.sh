#!/bin/bash

set -e
venvPath="$scriptDirectory/venv"

# ensure venv
if [ ! -d "$venvPath" ]; then
    mkdir venv
    python3 -m venv venv
    source venv/bin/activate
    pip install plexapi
    pip install unidecode
    pip install mutagen
    pip install pillow
    pip install ffmpeg-python
    pip install ffmpeg
    pip install pydub
    pip install audioop-lts
    pip install pyinstaller
fi
source venv/bin/activate
pyinstaller PlexPlaylistSync.py --onefile
