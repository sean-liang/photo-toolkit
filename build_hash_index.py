import os
import sys
import hashlib
import dbm
import argparse
import shutil
from tqdm import tqdm
from common import find_media_files

def calculate_file_hash(file_path):
    """Calculate SHA-256 hash value of the file"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def process_duplicate_file(file_path, original_path, dups_path):
    """
    Process duplicate file by moving it to duplicates directory and create a text file recording the original path
    
    Args:
        file_path: str, full path of the duplicate file
        original_path: str, path of the original file
        dups_path: str, path to the duplicates directory
    
    Returns:
        str: path of the moved file
    """
    # Ensure duplicates directory exists
    os.makedirs(dups_path, exist_ok=True)
    
    # Get filename
    file_name = os.path.basename(file_path)
    dup_file_path = os.path.join(dups_path, file_name)
    
    # If duplicate file exists, ensure unique filename
    base_name, ext = os.path.splitext(file_name)
    counter = 1
    while os.path.exists(dup_file_path):
        dup_file_path = os.path.join(dups_path, f"{base_name}_{counter}{ext}")
        counter += 1
    
    # Move duplicate file to dups directory
    shutil.move(file_path, dup_file_path)
    
    # Create txt file with same name to record original file path
    txt_path = os.path.splitext(dup_file_path)[0] + '.txt'
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(original_path)
    
    return dup_file_path

def check_file_duplicate(file_path, db, hash_key=None):
    """
    Check if file is a duplicate
    
    Args:
        file_path: str, path of the file to check
        db: dbm.open, opened database connection
        hash_key: str, optional, file hash value, will be calculated if not provided
    
    Returns:
        tuple: (is_duplicate, original_path, file_hash)
        - is_duplicate: bool, whether the file is a duplicate
        - original_path: str, path of original file if duplicate, None otherwise
        - file_hash: str, hash value of the file
    """
    if hash_key is None:
        file_hash = calculate_file_hash(file_path)
    else:
        file_hash = hash_key
        
    # Check if duplicate file exists
    hash_key = f"h:{file_hash}".encode()
    try:
        # If path can be retrieved, it's a duplicate file
        original_path = db[hash_key].decode()
        return True, original_path, file_hash
    except KeyError:
        return False, None, file_hash

def build_hash_index(work_dir, rebuild=False, dups_dir="dups"):
    """
    Build hash index for media files in specified directory
    
    Args:
        work_dir: str, path to working directory
        rebuild: bool, whether to rebuild index, defaults to False
        dups_dir: str, directory for storing duplicates, defaults to "dups"
    """
    # Create or open database
    db_path = os.path.join(work_dir, "hash.index")
    
    # In rebuild mode, delete old index if exists
    if rebuild and os.path.exists(db_path):
        try:
            os.remove(db_path)
            os.remove(db_path + '.db')  # dbm may create additional files
        except OSError:
            pass
        print("Old index file deleted")
    elif not os.path.exists(db_path):
        rebuild = True
        print("Index file not found, rebuilding")

    # Create duplicates directory
    dups_path = os.path.join(work_dir, dups_dir)
    os.makedirs(dups_path, exist_ok=True)

    # Open database, 'c' means create if not exists
    db = dbm.open(db_path, 'c')

    try:
        # Iterate over all media files, excluding dups directory
        media_files = list(find_media_files(work_dir, exclude_dirs=[dups_dir]))
        
        # Initialize counters
        processed_count = 0
        duplicate_count = 0
        
        # Use tqdm to display progress
        pbar = tqdm(media_files, desc="Building index")
        for rel_path, full_path in pbar:
            # If not rebuilding, check if file is already in index
            if not rebuild:
                try:
                    existing_hash = db[f"f:{rel_path}".encode()]
                    processed_count += 1
                    pbar.set_postfix(processed=processed_count, duplicates=duplicate_count)
                    continue
                except KeyError:
                    pass
            
            # Check if file is a duplicate
            is_duplicate, original_path, file_hash = check_file_duplicate(full_path, db)
            
            if is_duplicate:
                # Process duplicate file
                process_duplicate_file(full_path, original_path, dups_path)
                duplicate_count += 1
            else:
                # Store file path to hash mapping
                db[f"f:{rel_path}".encode()] = file_hash.encode()
                # Store hash to file path mapping
                db[f"h:{file_hash}".encode()] = rel_path.encode()
                processed_count += 1
            
            pbar.set_postfix(processed=processed_count, duplicates=duplicate_count)
            
        # Display final statistics after progress bar
        print(f"\nIndex built: {processed_count} files processed, {duplicate_count} duplicates found")
            
    finally:
        db.close()

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Build hash index for media files")
    parser.add_argument("work_directory", help="Path to working directory")
    parser.add_argument("--rebuild", action="store_true", default=False,
                      help="Rebuild index (delete existing index and recreate)")
    parser.add_argument("--dups-dir", default="dups",
                      help="Directory for storing duplicates (default: dups)")
    args = parser.parse_args()

    # Validate working directory
    work_dir = os.path.abspath(args.work_directory)
    if not os.path.isdir(work_dir):
        print(f"Error: {work_dir} is not a valid directory")
        sys.exit(1)

    # Build index
    build_hash_index(work_dir, args.rebuild, args.dups_dir)

if __name__ == "__main__":
    main()