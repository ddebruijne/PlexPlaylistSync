import time
import requests
import plexapi
import shutil
import os
import concurrent.futures
from utils import *
from plexapi.server import PlexServer
from mutagen.mp3 import MP3
from mutagen.flac import FLAC
from mutagen.mp4 import MP4
from mutagen.id3 import ID3, APIC
from mutagen.mp4 import MP4Cover

class PlaylistItem:
    def __init__(self, 
        title: str,
        duration: int,
        plexPath: str,
        fsPath: str,
        outPath: str,
        playlistRelPath: str,
        playlistAbsPath: str
    ):
        # title is also used as filename, filter some characters
        # why title = filename? Because some players display the filename instead of reading the id3 tag...
        self.title = title.replace(':', '_').replace('/', '_').replace('?', '')
        self.duration = duration / 1000 # conv to seconds
        self.plexPath = plexPath    # Path to music dir as known to plex, on your server, could be in docker or smth
        self.fsPath = fsPath    # Path to music dir as known to the filesystem, this could be different from plex.
        self.outPath = rename_filename_keep_extension(outPath, self.title)  # Path to music dir where the music should be copied to.
        self.playlistRelPath = playlistRelPath # from the perspective of the playlist, path to the music dir
        self.playlistAbsPath = playlistAbsPath  # from the root dir, path to the music dirs

MUSIC_FOLDER_OUT_DIR = "Music"
REL_PATH_FOR_PLAYLIST = "../" + MUSIC_FOLDER_OUT_DIR
ABS_PATH_FOR_PLAYLIST = "/" + MUSIC_FOLDER_OUT_DIR

# Get all audio playlists on the plex server of the user
def get_playlists(plex: PlexServer, filtered_playlists):
    print('Searching for playlists... ', end='')
    playlists = plex.playlists()

    result = []
    for item in playlists:
        if (item.playlistType == 'audio' and item.title not in filtered_playlists):
            result.append(item.title)

    print('Found %d' % len(result))
    return result

# Ge tall the items in a playlist, in a trimmed down format
def get_playlist_items(plex: PlexServer, name: str, plexMusicRoot: str, fsMusicRoot: str, outDir: str):
    try:
        playlist = plex.playlist(name)
    except (plexapi.exceptions.NotFound):
        return None

    items = playlist.items()
    parsed_items = []
    for item in items:
        plexFile = item.media[0].parts[0].file
        parsed_items.append(
            PlaylistItem(
                item.title,
                item.duration,
                plexFile,
                plexFile.replace(plexMusicRoot, fsMusicRoot),
                plexFile.replace(plexMusicRoot, os.path.join(outDir, MUSIC_FOLDER_OUT_DIR)),
                plexFile.replace(plexMusicRoot, REL_PATH_FOR_PLAYLIST),
                plexFile.replace(plexMusicRoot, ABS_PATH_FOR_PLAYLIST),
            )
        )

    return parsed_items

# Create a simple m3u playlist with the absolute path to the files
# Peugeot infotainment systems want these, and Rockbox ignores them. winwin?
def create_m3u_simple_abstract(
    playlistTitle: str, 
    playlistItems: list[PlaylistItem],
    playlistDir: str,
):
    playlistPath = "%s/%s.m3u" % (playlistDir, playlistTitle)
    if not os.path.exists(playlistDir):
        os.makedirs(playlistDir)

    m3u = open(playlistPath, 'w', encoding="utf-8")
    for item in playlistItems:
        fs_path = rename_filename_keep_extension(item.playlistAbsPath, item.title)
        m3u.write("%s\n" % fs_path)

    m3u.close()

# Create an m3u8 playlist with the relative path to the files and extended info.
# Main format for most players, like RockBox and Mazda Connect.
def create_m3u8_extended_relative(
    playlistTitle: str, 
    playlistItems: list[PlaylistItem],
    playlistDir: str,   
):
    playlistPath = "%s/%s.m3u8" % (playlistDir, playlistTitle)
    if not os.path.exists(playlistDir):
        os.makedirs(playlistDir)

    m3u = open(playlistPath, 'w', encoding="utf-8")
    m3u.write('#EXTM3U\n')
    m3u.write('#PLAYLIST:%s\n' % playlistTitle)
    m3u.write('\n')

    for item in playlistItems:
        fs_path = rename_filename_keep_extension(item.playlistRelPath, item.title)
        m3u.write('#EXTINF:%s,%s\n' % (int(item.duration), item.title))
        m3u.write("%s\n" % fs_path)
        m3u.write("\n")

    m3u.close()

# Copies all playlist files, using fsPath and outPath for each PlaylistItem
def copy_files(playlistItems: list[PlaylistItem], warnLossy: False):
    errors = []

    for i, value in enumerate(playlistItems):
        bit_depth = get_bit_depth(value.fsPath)
        index = "[%i/%i][%sbit] %s..." % (i+1, len(playlistItems), bit_depth, value.title)
        if bit_depth is None and warnLossy is True:
            errors.append('Could not determine bit depth (could be lossy mp3/m4a/ogg?) File: %s' % value.fsPath);

        try:
            if should_copy_file_if_newer(value.fsPath, value.outPath): 
                if bit_depth is not None and bit_depth > 16:
                    print(index, end='', flush=True)
                    convert_to_16bit(value.fsPath, value.outPath)
                    if get_bit_depth(value.outPath) != 16:
                        print(' Copied but could not convert.')
                        errors.append('Failed to convert to 16bit: %s'  % value.fsPath)
                    else:
                        print(' Converted & Copied')
                else:
                    print(index, end='', flush=True)
                    copy_file_if_newer(value.fsPath, value.outPath)
                    print(' Copied')
        except Exception as e:
            print('%s Error: %s' % (index, e))
            errors.append(e)
            continue
    
    return errors

# Process an audio file and update album art if necessary
def parse_album_art_audiofile(filepath):
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".mp3":
        audio = MP3(filepath, ID3=ID3)
        if audio.tags and "APIC:" in audio.tags:
            apic = audio.tags["APIC:"]
            new_art = convert_album_art_image_baseline_jpeg(apic.data, filepath)
            if new_art != apic.data:
                audio.tags["APIC:"] = APIC(
                    encoding=3, mime="image/jpeg", type=3, desc="Cover", data=new_art
                )
                audio.save()
        else:
            print(f"- {os.path.basename(filepath)}... No album art.")
    elif ext == ".flac":
        audio = FLAC(filepath)
        if audio.pictures:
            new_art = convert_album_art_image_baseline_jpeg(audio.pictures[0].data, filepath)
            if new_art != audio.pictures[0].data:
                audio.pictures[0].data = new_art
                audio.pictures[0].mime = "image/jpeg"
                audio.save()
        else:
            print(f"- {os.path.basename(filepath)}... No album art.")
    elif ext == ".m4a":
        audio = MP4(filepath)
        if "covr" in audio.tags:
            new_art = convert_album_art_image_baseline_jpeg(audio.tags["covr"][0], filepath)
            if new_art != audio.tags["covr"][0]:
                audio.tags["covr"] = [MP4Cover(new_art, imageformat=MP4Cover.FORMAT_JPEG)]
                audio.save()
        else:
            print(f"- {os.path.basename(filepath)}... No album art.")
    elif ext == ".wav":
        print(f"- {os.path.basename(filepath)}... Skipping WAV file (no standard embedded artwork support)")

# Process all album art of audio files in a directory tree, making them baseline jpegs
def parse_album_art(root_folder):
    files_to_process = []
    errors = []

    for root, _, files in os.walk(root_folder):
        for file in files:
            if os.path.splitext(file)[1].lower() in {".flac", ".m4a", ".mp3", ".wav"}:
                filepath = os.path.join(root, file)
                files_to_process.append(filepath)

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(parse_album_art_audiofile, filepath): filepath for filepath in files_to_process}
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception as e:
                log = f"Could not process album art of {futures[future]}: {e}"
                print(log)
                errors.append(log)
    
    return errors

def main():
    start_time = time.time()

    args = parse_args()
    config, config_path = load_config(args.out_dir)
    update_config(config_path, config, args)

    print('Checking folder paths...')
    ensure_access_to_folder(args.out_dir)
    ensure_access_to_folder(config.fs_music_root)

    print('Connecting to Plex...', end='')
    try:
        plex = PlexServer(config.host, config.token)
    except (plexapi.exceptions.Unauthorized, requests.exceptions.ConnectionError) as err:
        print(' failed. Check your token and/or host')
        print(err)
        return
    print(' Success')

    music_dir = os.path.join(args.out_dir, MUSIC_FOLDER_OUT_DIR)
    if not os.path.exists(music_dir):
        os.makedirs(music_dir)
    
    simpleAbsDir = os.path.join(args.out_dir, "Playlists_SimpleAbstract")
    if os.path.exists(simpleAbsDir):
        shutil.rmtree(simpleAbsDir)

    playlistDir = os.path.join(args.out_dir, "Playlists")
    if os.path.exists(playlistDir):
        shutil.rmtree(playlistDir)

    print('')
    playlist_titles = get_playlists(plex, config.ignore_playlists or DEFAULT_CONFIG.ignore_playlists)
    all_songs = []
    for playlist_name in playlist_titles:
        print('Converting %s...' % playlist_name, end='', flush=True)

        playlist_items = get_playlist_items(
            plex,
            playlist_name,
            config.plex_music_root,
            config.fs_music_root,
            args.out_dir,
        )
        if playlist_items is None:
            print(' Failed to get playlist')
            continue
        if not playlist_items:
            print(' Playlist is empty')
            continue
        print('.', end='', flush=True)
        
        if config.sync_simple_abstract: 
            create_m3u_simple_abstract(
                playlist_name,
                playlist_items,
                simpleAbsDir,
            )
            print('.', end='', flush=True)

        if config.sync_extended_relative:
            create_m3u8_extended_relative(
                playlist_name,
                playlist_items,
                playlistDir,
            )
            print('.', end='', flush=True)

        print(' Done')

        for item in playlist_items:
            all_songs.append(item)

    print('')
    print('Syncing files')
    errors = []
    errors.extend(copy_files(all_songs, config.warn_lossy_format))
    
    if not config.skip_album_art_checks:
        print('')
        print("Checking album art")
        errors.extend(parse_album_art(music_dir));
    
    print('')
    print("Job's done")
    print('Elapsed time: %i minutes and %i seconds' % divmod(time.time() - start_time, 60))
    if len(errors) > 0:
        print("The following errors happened during sync:")
        for error in errors:
            print('- ', end='')
            print(error)

if __name__ == "__main__":
    main()
