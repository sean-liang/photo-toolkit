import os
import shutil
import argparse
from common import find_media_files, is_image_file, is_video_file
from tqdm import tqdm

def classify_media_files(work_dir):
    """
    Traverse media files in the working directory and classify them into Video and Photo directories
    
    Args:
        work_dir: str, path to working directory
    """
    # Create Video and Photo directories
    video_dir = os.path.join(work_dir, 'Video')
    photo_dir = os.path.join(work_dir, 'Photo')
    os.makedirs(video_dir, exist_ok=True)
    os.makedirs(photo_dir, exist_ok=True)
    
    # Exclude Video and Photo directories to avoid reprocessing
    exclude_dirs = ['Video', 'Photo']
    
    # First collect all files to process
    files_to_process = list(find_media_files(work_dir, exclude_dirs))
    
    # Use tqdm to show progress
    for rel_path, full_path in tqdm(files_to_process, desc="Classifying files"):
        try:
            if is_video_file(full_path):
                target_dir = video_dir
            elif is_image_file(full_path):
                target_dir = photo_dir
            else:
                continue
                
            # Build target path, maintaining original directory structure
            target_path = os.path.join(target_dir, rel_path)
            target_parent = os.path.dirname(target_path)
            
            # Ensure target parent directory exists
            os.makedirs(target_parent, exist_ok=True)
            
            # If target file exists, add numeric suffix to new filename
            if os.path.exists(target_path):
                base, ext = os.path.splitext(target_path)
                counter = 1
                while os.path.exists(f"{base}_{counter}{ext}"):
                    counter += 1
                target_path = f"{base}_{counter}{ext}"
            
            # Move file
            shutil.move(full_path, target_path)
            
        except Exception as e:
            print(f"Error processing file {rel_path}: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description='Classify media files into Video and Photo directories by type')
    parser.add_argument('work_dir', help='path to working directory')
    args = parser.parse_args()
    
    if not os.path.isdir(args.work_dir):
        print(f"Error: {args.work_dir} is not a valid directory")
        return
    
    classify_media_files(args.work_dir)
    print("Classification completed!")

if __name__ == '__main__':
    main()