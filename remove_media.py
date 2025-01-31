import os
import sys
import dbm
import argparse
from pathlib import Path
from common import find_media_files, VIDEO_EXTENSIONS, MEDIA_EXTENSIONS, IMAGE_EXTENSIONS
from build_hash_index import calculate_file_hash

def remove_media_files(work_dir, media_type):
    """
    Remove media files of specified type
    
    Args:
        work_dir: str, working directory
        media_type: str, media type ('video' or 'photo')
    """
    # Determine target file extensions
    if media_type == 'video':
        target_extensions = VIDEO_EXTENSIONS
    elif media_type == 'photo':
        target_extensions = IMAGE_EXTENSIONS
    else:
        print(f"Unsupported media type: {media_type}")
        sys.exit(1)
        
    # Open hash index database
    db_path = os.path.join(work_dir, "hash.index")
    if not os.path.exists(db_path):
        print("Error: Hash index file not found")
        sys.exit(1)
        
    found_files = []
    # Find all target type files
    for rel_path, full_path in find_media_files(work_dir):
        if Path(full_path).suffix.lower() in target_extensions:
            found_files.append((rel_path, full_path))
    
    if not found_files:
        print(f"No {media_type} files found")
        return
        
    print(f"Found {len(found_files)} {media_type} files:")
    for rel_path, _ in found_files:
        print(f"  - {rel_path}")
        
    # Confirm deletion
    confirm = input("\nAre you sure you want to delete these files? (y/N): ")
    if confirm.lower() != 'y':
        print("Operation cancelled")
        return
        
    # Execute deletion
    with dbm.open(db_path, 'c') as db:
        for rel_path, full_path in found_files:
            try:
                # Calculate file hash for index removal
                file_hash = calculate_file_hash(full_path)
                hash_key = f"h:{file_hash}".encode()
                
                # Remove from index
                if hash_key in db:
                    del db[hash_key]
                    
                # Delete file
                os.remove(full_path)
                print(f"Deleted: {rel_path}")
            except Exception as e:
                print(f"Failed to delete {rel_path}: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description="Remove media files of specified type")
    parser.add_argument("work_dir", help="Working directory path")
    parser.add_argument("media_type", choices=['video', 'photo'], help="Media type to delete")
    
    args = parser.parse_args()
    remove_media_files(args.work_dir, args.media_type)

if __name__ == "__main__":
    main()