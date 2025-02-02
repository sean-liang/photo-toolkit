import os
import shutil
import argparse
from core.common import find_all_files, is_image_file, is_video_file
from convert_heic_to_jpg import convert_heic_to_jpeg
from convert_livp_to_mp4 import process_livp_files
from tqdm import tqdm

def classify_media_files(work_dir):
    """
    Traverse media files in the working directory and classify them into Video, Photo and Unknown directories
    
    Args:
        work_dir: str, path to working directory
    """
    # Create Video, Photo and Unknown directories
    video_dir = os.path.join(work_dir, 'Video')
    photo_dir = os.path.join(work_dir, 'Photo')
    unknown_dir = os.path.join(work_dir, 'Unknown')
    os.makedirs(video_dir, exist_ok=True)
    os.makedirs(photo_dir, exist_ok=True)
    os.makedirs(unknown_dir, exist_ok=True)
    
    # Exclude Video, Photo and Unknown directories to avoid reprocessing
    exclude_dirs = ['Video', 'Photo', 'Unknown']
    
    # First collect all files to process
    files_to_process = list(find_all_files(work_dir, exclude_dirs))
    
    # Use tqdm to show progress
    for rel_path, full_path in tqdm(files_to_process, desc="Classifying files"):
        try:
            if is_video_file(full_path):
                target_dir = video_dir
            elif is_image_file(full_path):
                target_dir = photo_dir
            else:
                # For unknown files, create a subdirectory based on extension
                ext = os.path.splitext(full_path)[1].lower().lstrip('.')
                if not ext:
                    ext = 'no_extension'
                ext_dir = os.path.join(unknown_dir, ext)
                os.makedirs(ext_dir, exist_ok=True)
                target_dir = ext_dir
                
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

def remove_empty_dirs(directory):
    """
    Recursively remove empty directories in the given directory
    
    Args:
        directory: str, path to the directory to clean
    """
    for root, dirs, files in os.walk(directory, topdown=False):
        for dir_name in dirs:
            dir_path = os.path.join(root, dir_name)
            try:
                # Check if directory is empty (no files and no subdirectories)
                if not os.listdir(dir_path):
                    os.rmdir(dir_path)
                    tqdm.write(f"Removed empty directory: {dir_path}")
            except Exception as e:
                print(f"Error removing directory {dir_path}: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description='Classify media files into Video, Photo and Unknown directories by type')
    parser.add_argument('work_dir', help='path to working directory')
    args = parser.parse_args()
    
    if not os.path.isdir(args.work_dir):
        print(f"Error: {args.work_dir} is not a valid directory")
        return
    
    classify_media_files(args.work_dir)
    print("Classification completed!")
    
    # Check if there are HEIC files and convert them
    heic_dir = os.path.join(args.work_dir, 'Unknown', 'heic')
    if os.path.exists(heic_dir):
        print("Found HEIC files, converting to JPEG...")
        output_dir = os.path.join(args.work_dir, 'Photo', 'heic_to_jpg')
        convert_heic_to_jpeg(heic_dir, output_dir)
        print("HEIC conversion completed!")
    
    # Check if there are LIVP files and convert them
    livp_dir = os.path.join(args.work_dir, 'Unknown', 'livp')
    if os.path.exists(livp_dir):
        print("Found LIVP files, converting to MP4...")
        output_dir = os.path.join(args.work_dir, 'Video', 'livp_to_mp4')
        process_livp_files(livp_dir, output_dir)
        print("LIVP conversion completed!")
    
    # Remove empty directories
    print("Removing empty directories...")
    remove_empty_dirs(args.work_dir)
    print("Empty directories removed!")

if __name__ == '__main__':
    main()