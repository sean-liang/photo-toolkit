import os
from pathlib import Path

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff'}
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv'}
MEDIA_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS

def is_image_file(file_path):
    """判断文件是否为图片"""
    return Path(file_path).suffix.lower() in IMAGE_EXTENSIONS

def is_video_file(file_path):
    """判断文件是否为视频"""
    return Path(file_path).suffix.lower() in VIDEO_EXTENSIONS

def find_media_files(work_dir, exclude_dirs=None):
    """
    遍历目录查找媒体文件
    
    Args:
        work_dir: str, 要搜索的工作目录
        exclude_dirs: list, 要排除的目录名列表，默认为None
    """
    if exclude_dirs is None:
        exclude_dirs = []
        
    for root, dirs, files in os.walk(work_dir):
        # 修改 dirs 列表来排除不需要的目录
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        for file in files:
            if Path(file).suffix.lower() in MEDIA_EXTENSIONS:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, work_dir)
                yield rel_path, full_path
