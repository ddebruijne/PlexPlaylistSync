# PlexPlaylistSync
To sync plex audio playlists to flash drives.
It will iterate all your playlists (non-generated), and export them to two types of m3u. It will then also copy all music files so you have correct relative directories in the playlist.
It checks file modification data so only not existing or changed files are copied

As extra feature, for Mazda Connect infotainment systems, it will also parse all album art and changes them to baseline jpeg, for some reason it needs that?

Note, it may not work for everyone, im focusing on Rockbox, Mazda Connect and Peugeot infotainment systems, but it could be nice for you with some small tweaks.

## Building
Run `make-exe.sh`, it will do:
- create a venv
- install all dependencies
- enable venv
- run pyinstaller one file mode

Then in `dist/`, you can find the binary.

## Usage
run `PlexPlaylistSync --help` for all params. 
By default, only `--token` and `--host` is required, you can get a token with [these](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/) instructions.

By default, a folder called `out` will be created where you execute the script so you can check everything works correctly, but ideally you should set `--out-dir` to the mount point of your flash drive, mp3 player or otherwise.

`--fs-music-root` should be the path your music directory is reachable by your computer.

`--plex-music-root` should point to that same folder, but by the folder that its known to your plex server. It could be different, eg if your plex server runs in a docker container
