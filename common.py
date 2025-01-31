import os
from pathlib import Path

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff'}
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv'}
MEDIA_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS

def is_image_file(file_path):
    """Check if the file is an image"""
    return Path(file_path).suffix.lower() in IMAGE_EXTENSIONS

def is_video_file(file_path):
    """Check if the file is a video"""
    return Path(file_path).suffix.lower() in VIDEO_EXTENSIONS

def find_media_files(work_dir, exclude_dirs=None):
    """
    Traverse directory to find media files
    
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
            if Path(file).suffix.lower() in MEDIA_EXTENSIONS:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, work_dir)
                yield rel_path, full_path
