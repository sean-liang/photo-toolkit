import os
import sys
import argparse
from tqdm import tqdm
import shutil

from core.common import find_files
from core.indexer import BaseIndexer, HashLibHasher


def build_hash_index(work_dir, dups_dir="dups", index_uri=None, verbose=False, dry_run=False):
    """
    Build hash index for media files.
    
    Args:
        work_dir: Working directory path
        dups_dir: Directory for storing duplicates
        index_uri: URI for the index storage, format: scheme[+hash_algo]://filename
                  e.g. 'dbm+sha256://hash.index' or 'dbm://hash.index'
        verbose: Whether to print detailed logs
        dry_run: Whether to run in dry-run mode
    """
    # If index URI is not specified, use default
    if index_uri is None:
        index_uri = "dbm+sha256://hash.index"
    
    # Create indexer
    indexer = BaseIndexer.create(index_uri, work_dir)
    
    # Create duplicates directory
    dups_path = os.path.join(work_dir, dups_dir)
    if not dry_run:
        os.makedirs(dups_path, exist_ok=True)
    
    try:
        # Find all media files
        media_files = list(find_files(work_dir, exclude_dirs=[dups_dir]))
        total_files = len(media_files)
        
        print(f"Found {total_files} files to process")
        if dry_run:
            print("Running in dry-run mode, no files will be moved")
        
        # Use tqdm to display progress
        with tqdm(total=total_files, desc="Building index") as pbar:
            new_files = 0
            dups = 0

            with indexer:
                for rel_path, full_path in media_files:
                    added, _ = indexer.add_if_absent(full_path)
                    if added:
                        new_files += 1
                        if verbose:
                            tqdm.write(f"\033[92m+ {rel_path}\033[0m")
                    else:
                        # Move duplicate file to duplicates directory
                        rel_path = indexer.get(full_path)
                        if rel_path is not None:
                            dup_path = os.path.join(dups_path, os.path.basename(full_path))
                            # Rename if file already exists in duplicates directory
                            if os.path.exists(dup_path):
                                base, ext = os.path.splitext(dup_path)
                                counter = 1
                                while os.path.exists(f"{base}_{counter}{ext}"):
                                    counter += 1
                                dup_path = f"{base}_{counter}{ext}"
                            if verbose:
                                if dry_run:
                                    tqdm.write(f"\033[93m! Would move: {full_path} -> {dup_path}\033[0m")
                                else:
                                    tqdm.write(f"\033[91m- {dup_path}\033[0m")
                            if not dry_run:
                                shutil.move(full_path, dup_path)
                            dups += 1
                    
                    pbar.update(1)
                    pbar.set_postfix(new=new_files, dups=dups)
        
        # Display final statistics
        print(f"\nIndex built successfully:")
        if dry_run:
            print(f"- Would add {new_files} new files")
            print(f"- Would move {dups} duplicates to {dups_dir}")
        else:
            print(f"- {new_files} new files added")
            print(f"- {dups} duplicates moved to {dups_dir}")
            
    except Exception as e:
        print(f"Error: {str(e)}")
        raise


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Build hash index for media files")
    parser.add_argument("work_directory", help="Path to working directory")
    parser.add_argument("--dups-dir", default="dups",
                      help="Directory for storing duplicates (default: dups)")
    parser.add_argument("--index-uri", 
                      help="URI for the index storage, format: scheme[+hash_algo]://filename")
    parser.add_argument("--verbose", "-v", action="store_true",
                      help="Print detailed logs")
    parser.add_argument("--dry-run", "-n", action="store_true",
                      help="Show what would be done without actually moving files")
    
    args = parser.parse_args()
    
    # Get absolute path for work directory
    work_dir = os.path.abspath(args.work_directory)
    if not os.path.isdir(work_dir):
        print(f"Error: {work_dir} is not a directory")
        sys.exit(1)

    # Build index
    build_hash_index(work_dir, args.dups_dir, args.index_uri, args.verbose, args.dry_run)


if __name__ == "__main__":
    main()