from pathlib import Path
from datetime import datetime
import shutil
from tqdm import tqdm
import piexif
import os
import argparse

from core.common import get_image_earliest_date, find_files, is_image_file, is_video_file, get_video_earliest_date, get_earliest_file_date
from core.indexer import BaseIndexer, HashLibHasher

def get_media_date(file_path, custom_date=None):
    """Get media file creation date"""
    if custom_date:
        return custom_date

    if is_image_file(file_path):
        return get_image_earliest_date(file_path)
    elif is_video_file(file_path):
        return get_video_earliest_date(file_path)
    else:
        return get_earliest_file_date(file_path)

def get_new_filename(date, original_path, target_dir, file_hash):
    """
    Generate new filename and path in format: YYYY/MM/YYYYMMDDHHMMSS_HASH.ext
    
    Args:
        date: datetime, file date
        original_path: Path, original file path
        target_dir: Path, target root directory
        file_hash: str, hash of the file
    
    Returns:
        tuple: (relative path, full path)
    """
    # Get year and month info
    year = date.strftime('%Y')
    month = date.strftime('%m')
    
    # Build target subdirectory path
    sub_dir = os.path.join(year, month)
    
    # Get timestamp string
    timestamp = date.strftime('%Y%m%d%H%M%S')
    
    # Keep original file extension
    ext = original_path.suffix.lower()
    
    # Generate new filename using timestamp and hash
    filename = f"{timestamp}_{file_hash}{ext}"
    
    # Return relative path and full path
    rel_path = os.path.join(sub_dir, filename)
    full_path = os.path.join(target_dir, rel_path)
    
    return rel_path, full_path

def set_image_date(image_path, target_date):
    """Set image EXIF date information"""
    try:
        # Convert date to EXIF format string
        date_str = target_date.strftime('%Y:%m:%d %H:%M:%S')
        
        # Read existing EXIF data
        try:
            exif_dict = piexif.load(str(image_path))
        except:
            # If no EXIF data exists, create new one
            exif_dict = {'0th': {}, 'Exif': {}, 'GPS': {}, '1st': {}, 'thumbnail': None}
        
        # Set DateTime (306) in 0th IFD
        exif_dict['0th'][piexif.ImageIFD.DateTime] = date_str
        # Set DateTimeOriginal (36867) in Exif IFD
        exif_dict['Exif'][piexif.ExifIFD.DateTimeOriginal] = date_str
        # Set DateTimeDigitized (36868) in Exif IFD
        exif_dict['Exif'][piexif.ExifIFD.DateTimeDigitized] = date_str
        
        # Convert EXIF data to bytes
        exif_bytes = piexif.dump(exif_dict)
        
        # Save EXIF data to image
        piexif.insert(exif_bytes, str(image_path))
    except Exception as e:
        print(f"Warning: Unable to modify EXIF information for {image_path}: {str(e)}")

def process_media(input_dir, output_dir, dry_run=False, custom_date=None, hash_algo="sha256", index_uri=None, move=False):
    """Process all media files
    
    Args:
        input_dir: str, input directory path
        output_dir: str, output directory path
        dry_run: bool, if True, only show what would be done without actually copying files
        custom_date: datetime, custom date to use for all files
        hash_algo: str, hash algorithm to use
        index_uri: str, URI for the index storage
        move: bool, if True, move files instead of copying them
    """
    # Ensure output directory exists
    if not dry_run:
        os.makedirs(output_dir, exist_ok=True)
        
    # Create indexer
    if index_uri is None:
        index_uri = f"dbm://{os.path.join(output_dir, 'hash.index')}"
    hasher = HashLibHasher(hash_algo)
    indexer = BaseIndexer.create(index_uri, hasher)
    
    try:
        # Find all media files
        media_files = list(find_files(input_dir))
        
        # Initialize counters
        processed_count = 0
        duplicate_count = 0
        
        # Use tqdm to show progress
        with tqdm(total=len(media_files), desc="Processing files") as pbar:
            with indexer:
                for file in media_files:
                    try:
                        # Get file creation date
                        date = get_media_date(file, custom_date)
                        
                        # Generate new filename and path
                        new_rel_path, new_path = get_new_filename(date, Path(file), Path(output_dir), hasher.hash_file(file))
                        
                        if not dry_run:
                            # Check for duplicates first
                            added, _ = indexer.add_if_absent(file)
                            
                            if not added:
                                # File is a duplicate
                                duplicate_count += 1
                                pbar.set_postfix(processed=processed_count, duplicates=duplicate_count)
                                pbar.update(1)
                                continue
                            
                            # Create target directory (if not exists)
                            os.makedirs(os.path.dirname(new_path), exist_ok=True)
                            
                            # Copy or move file
                            if move:
                                shutil.move(file, new_path)
                            else:
                                shutil.copy2(file, new_path)
                            
                            # If it's an image file, try to set EXIF date
                            if custom_date is not None and is_image_file(new_path):
                                set_image_date(new_path, date)
                            
                            # Update processed file count
                            processed_count += 1
                            pbar.set_postfix(processed=processed_count, duplicates=duplicate_count)
                        else:
                            # In dry-run mode, just show what would be done
                            action = "move" if move else "copy"
                            tqdm.write(f"Would {action}: {file} -> {new_path}")
                        
                        pbar.update(1)
                        
                    except Exception as e:
                        tqdm.write(f"Error processing {file}: {str(e)}")
                
        # Show final statistics after progress bar completion
        print(f"\nProcessing complete:")
        if dry_run:
            action = "move" if move else "copy"
            print(f"- Would {action} {len(media_files)} files")
        else:
            action = "moved" if move else "copied"
            print(f"- {processed_count} files {action}")
            print(f"- {duplicate_count} duplicate files skipped")
    finally:
        indexer.close()

def main():
    parser = argparse.ArgumentParser(description="Organize photos into specified directory by date")
    parser.add_argument('input_dir', help="Input directory path")
    parser.add_argument('output_dir', help="Output directory path")
    parser.add_argument('--dry-run', action='store_true', help="Only show what would be done without actually copying files")
    parser.add_argument('--date', help="Specify date time in format: YYYY-MM-DD HH:MM:SS, if not specified will read from EXIF")
    parser.add_argument('--hash-algo', default="sha256", choices=['md5', 'sha1', 'sha256', 'sha512'],
                      help="Hash algorithm to use (default: sha256)")
    parser.add_argument('--index-uri', help="URI for the index storage")
    parser.add_argument('--move', action='store_true', help="Move files instead of copying them")
    
    args = parser.parse_args()
    
    # Validate input directory exists
    if not os.path.isdir(args.input_dir):
        print(f"Error: Input directory '{args.input_dir}' does not exist")
        return
    
    # Parse custom date
    custom_date = None
    if args.date:
        try:
            custom_date = datetime.strptime(args.date, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            print("Error: Invalid date format, please use YYYY-MM-DD HH:MM:SS format")
            return
    
    # Process media files
    process_media(args.input_dir, args.output_dir, args.dry_run, custom_date, 
                 args.hash_algo, args.index_uri, args.move)

if __name__ == '__main__':
    main()