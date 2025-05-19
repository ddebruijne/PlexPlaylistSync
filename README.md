# PlexPlaylistSync
To sync plex audio playlists to flash drives.
It will iterate all your playlists (non-generated), and export them to two types of m3u. It will then also copy all music files so you have correct relative directories in the playlist.
It checks file modification data so only not existing or changed files are copied

For Mazda Connect infotainment systems, it will also parse all album art and changes them to baseline jpeg, for some reason it needs that?

Note, it may not work for everyone, im focusing on Rockbox, Mazda Connect and Peugeot infotainment systems, but it could be nice for you with some small tweaks.

## Usage
run `PlexPlaylistSync --help` for all params. 
The only required parameter is `--out-dir`, the rest is optional.
All optional parameters will be saved to a `config_<your-system-name>.json` file in the out dir. You can either use the parameters to update the settings, or modify the json file.

Different configs per system because your `fs-music-root` may be different.

| Parameter | Notes |
| --------- | ----- |
| out-dir         | Your testing folder, but ideally the mount point of your flash drive / iPod |
| fs-music-root   | The music library as accessible by your computer. If it is a Samba share and you use Gnome Desktop, it will automatically be mounted if not already. I kept forgetting 😅 |
| plex-music-root | The music library as accessible by Plex. This should be the same folder as `fs-music-root` but it likely is a different path for your Plex Server. |
| host            | Direct URL of the Plex server, including port. |
| token           | You can get a token with [these](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/) instructions. |
| sync-extended-relative | Default playlist type. `.m3u8` with relative file paths and extended information about the song. Works well for me with Rockbox and Mazda Connect. |
| sync-simple-abstract   | `.m3u` with abstract file paths (where the root is `out-dir`) and no extended information. Peugeot e-208 infotainment system seems to only be able to work with these. |


## Building
Run `make-exe.sh`, it will do:
- create a venv
- install all dependencies
- enable venv
- run pyinstaller one file mode

Then in `dist/`, you can find the binary.
