import os
import io
import shutil
import argparse
from PIL import Image

def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--fs-music-root',
        type = str,
        help = "The root of the filesystem music library location, for instance '/music'",
        default = '/Volumes/Media/Music/Lidarr'
    )
    parser.add_argument(
        '--plex-music-root',
        type = str,
        help = "The root of the plex music library location, for instance '/music'",
        default = '/media/Music/Lidarr'
    )
    parser.add_argument(
        '--out-dir',
        type = str,
        help = "Root dir for the output files, eg your flash drive",
        default = 'out/'
    )
    parser.add_argument(
        '--host',
        type = str,
        help = "The URL to the Plex Server, i.e.: http://192.168.0.100:32400",
        default = 'http://plex.jn:32400'
    )
    parser.add_argument(
        '--token',
        type = str,
        help = "The Token used to authenticate with the Plex Server",
        default = None,
        required = True
    )
    return parser.parse_args()

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
    return os.path.join(directory, new_name + extension)

def get_minute_rounded_mtime(filepath):
    """Get the file modification time rounded to the nearest minute."""
    return int(os.path.getmtime(filepath) // 60)  # Round down to minute precision

def copy_file_if_newer(src, dst):
    if not os.path.exists(src):
        raise FileNotFoundError(f"Source file does not exist: {src}")
    
    if os.path.exists(dst):
        src_mtime = get_minute_rounded_mtime(src)
        dst_mtime = get_minute_rounded_mtime(dst)

        if src_mtime <= dst_mtime:
            return False  # No need to copy

    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)  # Copies metadata including timestamps
    return True  # File was copied

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
        print(f"- {os.path.basename(filepath)}... OK!")
        return image_data  # Skip processing if already within limits and baseline JPEG
    
    with Image.open(io.BytesIO(image_data)) as img:
        img = img.convert("RGB")
        img.thumbnail((MAX_SIZE, MAX_SIZE))
        output = io.BytesIO()
        img.save(output, format="JPEG", quality=85, progressive=False)
        print(f"- {os.path.basename(filepath)}... Converted.")
        return output.getvalue()
