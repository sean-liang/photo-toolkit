import os
from pathlib import Path
from PIL import Image, ExifTags
from datetime import datetime
import ffmpeg

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff'}
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv'}
MEDIA_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS

def is_image_file(file_path):
    """Check if the file is an image"""
    return Path(file_path).suffix.lower() in IMAGE_EXTENSIONS

def is_video_file(file_path):
    """Check if the file is a video"""
    return Path(file_path).suffix.lower() in VIDEO_EXTENSIONS

def find_files(work_dir, extensions=MEDIA_EXTENSIONS, exclude_dirs=None):
    """
    Traverse directory to find files with specified extensions
    
    Args:
        work_dir: str, working directory to search
        extensions: set, file extensions to search for, defaults to MEDIA_EXTENSIONS
        exclude_dirs: list, list of directory names to exclude, defaults to None
    """
    if exclude_dirs is None:
        exclude_dirs = []
        
    for root, dirs, files in os.walk(work_dir):
        # Modify dirs list to exclude unwanted directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        for file in files:
            if Path(file).suffix.lower() in extensions:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, work_dir)
                yield rel_path, full_path

def find_all_files(work_dir, exclude_dirs=None):
    """
    Traverse directory to find all files
    
    Args:
        work_dir: str, working directory to search
        exclude_dirs: list, list of directory names to exclude, defaults to None
    """
    if exclude_dirs is None:
        exclude_dirs = []
        
    for root, dirs, files in os.walk(work_dir):
        # Modify dirs list to exclude unwanted directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        for file in files:
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, work_dir)
            yield rel_path, full_path

def get_earliest_file_date(file_path):
    """Get the earliest date between file creation and modification dates"""
    try:
        ctime = os.path.getctime(file_path)
        mtime = os.path.getmtime(file_path)
        # Return the earlier date
        return datetime.fromtimestamp(min(ctime, mtime))
    except Exception as e:
        print(f"Warning: Error getting file dates for {file_path}: {str(e)}")
        # If error occurs, return modification time
        return datetime.fromtimestamp(os.path.getmtime(file_path))

def get_image_earliest_date(file_path):
    dates = []
    
    # EXIF dates using PIL
    try:
        with Image.open(file_path) as img:
            exif_data = img._getexif()
            if exif_data:
                exif = {
                    ExifTags.TAGS.get(tag, tag): value
                    for tag, value in exif_data.items()
                }
                date_fields = [
                    'DateTimeOriginal',
                    'DateTimeDigitized',
                    'DateTime',
                    'GPSDateStamp'
                ]
                for field in date_fields:
                    if exif.get(field):
                        try:
                            dt_str = exif[field]
                            if field == 'GPSDateStamp':
                                dt = datetime.strptime(dt_str, '%Y:%m:%d')
                            else:
                                dt = datetime.strptime(dt_str, '%Y:%m:%d %H:%M:%S')
                            dates.append(dt)
                        except (ValueError, TypeError):
                            pass
    except (IOError, SyntaxError, KeyError):
        pass
    
    # File system dates
    stat = os.stat(file_path)
    dates.extend([
        datetime.fromtimestamp(stat.st_ctime),
        datetime.fromtimestamp(stat.st_mtime)
    ])
    
    return min(dates) if dates else None

def get_video_earliest_date(video_path):
    """Get earliest date from video file by checking metadata and file system dates.
    
    Args:
        video_path: Path to the video file
        
    Returns:
        datetime: The earliest date found, or None if no valid date found
    """
    dates = []
    
    # Get dates from video metadata using ffmpeg
    try:
        probe = ffmpeg.probe(str(video_path))
        date_fields = [
            'creation_time',          # Creation time
            'com.apple.quicktime.creationdate',  # QuickTime creation date
            'date',                   # Date
            'DateTimeOriginal',       # Original date time
            'date_time',              # Date time
            'media_create_time',      # Media creation time
        ]
        
        # Check format metadata
        if 'format' in probe and 'tags' in probe['format']:
            tags = probe['format']['tags']
            for field in date_fields:
                if field in tags:
                    date_str = tags[field]
                    try:
                        if 'T' in date_str:
                            # ISO format: 2024-01-30T12:34:56
                            date_str = date_str.split('.')[0]  # Remove possible milliseconds
                            dates.append(datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S'))
                        elif '-' in date_str:
                            # Standard format: 2024-01-30 12:34:56
                            dates.append(datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S'))
                        else:
                            # QuickTime format: 2024:01:30 12:34:56
                            dates.append(datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S'))
                    except ValueError:
                        continue
        
        # Check video stream metadata
        for stream in probe['streams']:
            if 'tags' in stream:
                tags = stream['tags']
                for field in date_fields:
                    if field in tags:
                        date_str = tags[field]
                        try:
                            if 'T' in date_str:
                                date_str = date_str.split('.')[0]
                                dates.append(datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S'))
                            elif '-' in date_str:
                                dates.append(datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S'))
                            else:
                                dates.append(datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S'))
                        except ValueError:
                            continue
    except Exception as e:
        print(f"Warning: Error getting video date from ffmpeg for {video_path}: {str(e)}")
    
    # Add file system dates
    stat = os.stat(video_path)
    dates.extend([
        datetime.fromtimestamp(stat.st_ctime),
        datetime.fromtimestamp(stat.st_mtime)
    ])
    
    return min(dates) if dates else None