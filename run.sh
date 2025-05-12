#!/bin/bash
# example usage: ./exportplaylits.sh TOKEN DISKNAME
# TOKEN: comes from plex, if you view details on an item, then xml, the last param in the url is the token
# DISKNAME: name of the mounted volume.

set -e
SECONDS=0  # Start the timer

scriptFilePath=$(realpath "$0")
scriptDirectory=$(dirname "$scriptFilePath")
venvPath="$scriptDirectory/venv"

# Check if an argument is provided
if [ -z "$1" ]; then
    echo "No plex token provided. Usage: ./run.sh TOKEN DISKNAME"
    exit 1
fi
token=$1

# Prepare outDir
if [ -z "$2" ]; then
    outdir="$scriptDirectory/out/"
else
    outdir="/run/media/$USER/$2/" # need trailing /
fi

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
fi
source venv/bin/activate

python3 PlexPlaylistSync.py --token $token --out-dir $outdir
echo "Took $SECONDS seconds."
