import json
import os
import io
import re
import shutil
import argparse
import socket
import subprocess
from PIL import Image

class Config(dict):
    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError:
            raise AttributeError(f"'Config' object has no attribute '{item}'")

    def __setattr__(self, key, value):
        self[key] = value

DEFAULT_CONFIG = Config({
    "fs_music_root": "/run/user/1000/gvfs/smb-share:server=192.168.103.7,share=media/Music/Lidarr",
    "plex_music_root": "/media/Music/Lidarr",
    "host": "http://plex.jn:32400",
    "sync_extended_relative": True,
    "sync_simple_abstract": False,
    "token": None,
})

def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--out-dir',
        type = str,
        help = "Root dir for the output files, eg your flash drive (/run/media/$USER/FLASHDRIVENAME)",
        default = "out",
    )
    parser.add_argument(
        '--fs-music-root',
        type = str,
        help = "The root of the filesystem music library location, for instance '/smb-mounts/media/music'",
    )
    parser.add_argument(
        '--plex-music-root',
        type = str,
        help = "The root of the plex music library location, for instance '/music'",
    )
    parser.add_argument(
        '--host',
        type = str,
        help = "The URL to the Plex Server, i.e.: http://192.168.0.100:32400",
    )
    parser.add_argument(
        '--token',
        type = str,
        help = "The Token used to authenticate with the Plex Server",
    )
    parser.add_argument(
        '--sync-extended-relative',
        type = bool,
        help = "Whether to sync playlist files with relative paths and extended information, as .m3u8. Recommended for Rockbox, Mazda Connect",
    )
    parser.add_argument(
        '--sync-simple-abstract',
        type = bool,
        help = "Whether to sync playlist files with abstract paths (root = out-dir) and no information, as .m3u. Recommended for Peugeot infotainment system (e-208)",
    )
    return parser.parse_args()

def get_machine_name():
    return socket.gethostname()

def load_config(output_dir):
    machine_name = get_machine_name()
    config_filename = f"config_{machine_name}.json"
    config_path = os.path.join(output_dir, config_filename)

    # Check if the config file exists
    if not os.path.exists(config_path):
        print(f"Config file not found. Creating default at {config_path}.")
        os.makedirs(output_dir, exist_ok=True)
        with open(config_path, 'w') as file:
            json.dump(DEFAULT_CONFIG, file, indent=4)

    # Load the configuration
    with open(config_path, 'r') as file:
        data = json.load(file)
        config = Config(data)
        return config, config_path


def update_config(config_path, config, args):
    new_values = {k: v for k, v in vars(args).items() if v is not None and k != "out_dir"}
    if not new_values:
        return

    config.update(new_values)
    with open(config_path, 'w') as file:
        json.dump(config, file, indent=4)
    print(f"Updated configuration saved to {config_path}")


def rename_file_keep_extension(file_path, new_name):
    directory, old_filename = os.path.split(file_path)
    name, extension = os.path.splitext(old_filename)
    new_filename = new_name + extension
    new_path = os.path.join(directory, new_filename)
    
    os.rename(file_path, new_path)
    return new_path

def rename_filename_keep_extension(file_path, new_name):
    directory, old_filename = os.path.split(file_path)
    _, extension = os.path.splitext(old_filename)
    result = os.path.join(directory, new_name + extension)
    return result

def get_minute_rounded_mtime(filepath):
    """Get the file modification time rounded to the nearest minute."""
    return int(os.path.getmtime(filepath) // 60)  # Round down to minute precision

def copy_file_if_newer(src, dst):
    copy = should_copy_file_if_newer(src, dst)
    if copy:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)  # Copies metadata including timestamps

    return copy

def should_copy_file_if_newer(src, dst):
    if not os.path.exists(src):
        raise FileNotFoundError(f"Source file does not exist: {src}")
    
    if os.path.exists(dst):
        src_mtime = get_minute_rounded_mtime(src)
        dst_mtime = get_minute_rounded_mtime(dst)

        if src_mtime <= dst_mtime:
            return False  # No need to copy

    return True # file should be copied

def copy_modification_time(src, dst):
    mod_time = get_minute_rounded_mtime(src)
    os.utime(dst, (mod_time, mod_time))

def get_image_dimensions_format_and_progressive(image_data):
    """Extract image dimensions, format, and check if JPEG is progressive."""
    with Image.open(io.BytesIO(image_data)) as img:
        is_progressive = "progressive" in img.info
        return img.size, img.format, is_progressive

MAX_SIZE = 512
def convert_album_art_image_baseline_jpeg(image_data, filepath):
    (width, height), img_format, is_progressive = get_image_dimensions_format_and_progressive(image_data)
    
    if max(width, height) <= MAX_SIZE and img_format == "JPEG" and not is_progressive:
        # print(f"- {os.path.basename(filepath)}... OK!")
        return image_data  # Skip processing if already within limits and baseline JPEG
    
    with Image.open(io.BytesIO(image_data)) as img:
        img = img.convert("RGB")
        img.thumbnail((MAX_SIZE, MAX_SIZE))
        output = io.BytesIO()
        img.save(output, format="JPEG", quality=85, progressive=False)
        print(f"- {os.path.basename(filepath)}... Converted.")
        return output.getvalue()

def is_gvfs_smb_share(path):
    """Check if the path is a GVfs-mounted SMB share."""
    gvfs_base = f"/run/user/{os.getuid()}/gvfs/"
    
    # Ensure the path starts with the GVfs base directory
    if not path.startswith(gvfs_base):
        return False, None, None, None

    # Extract the GVfs share path
    relative_path = path[len(gvfs_base):]

    # Regex to detect the GVfs SMB share pattern (with optional subdirectories)
    gvfs_smb_pattern = r"^smb-share:server=([^,]+),share=([^/]+)(/.*)?"
    match = re.match(gvfs_smb_pattern, relative_path)
    
    if match:
        server, share, subdirs = match.groups()
        subdirs = subdirs if subdirs else ""
        # print(f"Detected GVfs SMB share: server={server}, share={share}, subdirs={subdirs}")
        return True, server, share, subdirs
    
    # print("Not a GVfs SMB share")
    return False, None, None, None

def mount_gvfs_share(server, share):
    """Attempt to mount the GVfs SMB share."""
    try:
        share_url = f"smb://{server}/{share}"
        result = subprocess.run(
            ["gio", "mount", share_url],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print(f"Successfully mounted {share_url}")
            return True
        print(f"Mount failed: {result.stderr}")
    except Exception as e:
        print(f"Error during mounting: {e}")
    return False

def ensure_access_to_folder(path):
    is_smb, server, share, subdirs = is_gvfs_smb_share(path)

    if is_smb:
        mount_point = f"/run/user/{os.getuid()}/gvfs/smb-share:server={server},share={share}"
        if not (os.path.exists(mount_point) and os.listdir(mount_point)):
            print(f"Attempting to mount {mount_point}...")
            if not mount_gvfs_share(server, share): # logs out result
                return False
            else:
                return True
        else:
            return True # no log, already mounted
    else:
        return True # no log, not a gvfs share

def get_bit_depth(file_path):
    cmd = [
        'ffprobe', '-v', 'error',
        '-select_streams', 'a:0',
        '-show_entries', 'stream=bits_per_raw_sample',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        file_path
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode == 0:
        output = result.stdout.strip()
        if output:
            return int(output)
    return None

def convert_to_16bit(input_path, output_path):
    # print(f"Converting to 16-bit: {input_path} → {output_path}")
    
    # Ensure the output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    cmd = [
        'ffmpeg',
        '-y',   # This tells FFmpeg: "yes, overwrite existing files"
        '-i', input_path,
        '-sample_fmt', 's16',  # Set sample format to 16-bit
        output_path
    ]

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    # if result.returncode != 0:
    #     print(f"FFmpeg error converting {input_path}:\n{result.stderr}")
    # else:
    #     print(f"Successfully converted {input_path} to 16-bit")
