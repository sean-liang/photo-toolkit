from pathlib import Path
from datetime import datetime
import shutil
from tqdm import tqdm
import piexif
import os
import argparse
import sys

from core.common import get_image_earliest_date, find_files, is_image_file, is_video_file, get_video_earliest_date, get_earliest_file_date
from core.indexer import BaseIndexer

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

def get_new_filename(date, src_path: Path, output_dir: Path, file_hash: str) -> tuple[str, str]:
    """Generate new filename based on date and hash.
    
    Args:
        date: datetime object
        src_path: source file path
        output_dir: output directory path
        file_hash: file hash value
        
    Returns:
        tuple[str, str]: (relative path, absolute path)
    """
    # Create year and month directories
    year_dir = f"{date.year:04d}"
    month_dir = f"{date.month:02d}"
    
    # Keep original file extension
    extension = src_path.suffix.lower()
    
    # Create filename with date and hash
    filename = f"{date.strftime('%Y%m%d%H%M%S')}_{file_hash}{extension}"
    
    # Create relative path
    rel_path = str(Path(year_dir) / month_dir / filename)
    
    # Create absolute path
    abs_path = str(output_dir / rel_path)
    
    return rel_path, abs_path

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

def process_media(input_dir, output_dir, dry_run=False, custom_date=None, index_uri=None, move=False):
    """Process all media files
    
    Args:
        input_dir: str, input directory path
        output_dir: str, output directory path
        dry_run: bool, if True, only show what would be done without actually copying files
        custom_date: datetime, custom date to use for all files
        index_uri: str, URI for the index storage, format: scheme[+hash_algo]://filename
                  e.g. 'dbm+sha256://hash.index' or 'dbm://hash.index'
        move: bool, if True, move files instead of copying them
    """
    # Ensure output directory exists
    if not dry_run:
        os.makedirs(output_dir, exist_ok=True)
        
    # Create indexer
    if index_uri is None:
        index_uri = "dbm+sha256://hash.index"
    
    indexer = BaseIndexer.create(index_uri, output_dir)
    
    try:
        # Find all media files
        media_files = list(find_files(input_dir))
        
        # Initialize counters
        processed_count = 0
        duplicate_count = 0
        
        # Use tqdm to show progress
        with tqdm(total=len(media_files), desc="Processing files") as pbar:
            with indexer:
                for rel_path, full_path in media_files:
                    try:
                        # Get file creation date
                        date = get_media_date(full_path, custom_date)
                        
                        # Calculate hash value
                        file_hash = indexer.hasher.calculate(full_path)

                        if dry_run:
                            # In dry-run mode, just show what would be done
                            action = "move" if move else "copy"
                            tqdm.write(f"Would {action}: {full_path} -> {get_new_filename(date, Path(full_path), Path(output_dir), file_hash)[1]}")
                            pbar.update(1)
                            continue

                        if indexer.exists(file_hash=file_hash):
                            # File already exists in index
                            duplicate_count += 1
                            pbar.set_postfix(processed=processed_count, duplicates=duplicate_count)
                            pbar.update(1)
                            continue

                        # Generate new filename and path
                        new_rel_path, new_path = get_new_filename(date, Path(full_path), Path(output_dir), file_hash)

                        # Create target directory (if not exists)
                        os.makedirs(os.path.dirname(new_path), exist_ok=True)
                        
                        # Copy or move file
                        if move:
                            shutil.move(full_path, new_path)
                        else:
                            shutil.copy2(full_path, new_path)
                        
                        # If it's an image file, try to set EXIF date
                        if custom_date is not None and is_image_file(new_path):
                            set_image_date(new_path, date)

                        # Add file to index with pre-calculated hash
                        indexer.add(new_path, file_hash)
                        
                        # Update processed file count
                        processed_count += 1
                        pbar.set_postfix(processed=processed_count, duplicates=duplicate_count)
                        pbar.update(1)
                    except Exception as e:
                        tqdm.write(f"Error processing {full_path}: {str(e)}")
                
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
    """Main function."""
    parser = argparse.ArgumentParser(description="Import media files to organized storage")
    parser.add_argument("input_directory", help="Input directory path")
    parser.add_argument("output_directory", help="Output directory path")
    parser.add_argument("--dry-run", "-n", action="store_true",
                      help="Show what would be done without actually copying files")
    parser.add_argument("--custom-date",
                      help="Custom date to use for all files (format: YYYY-MM-DD)")
    parser.add_argument("--index-uri",
                      help="URI for the index storage, format: scheme[+hash_algo]://filename")
    parser.add_argument("--move", "-m", action="store_true",
                      help="Move files instead of copying them")
    
    args = parser.parse_args()
    
    # Parse custom date if provided
    custom_date = None
    if args.custom_date:
        try:
            custom_date = datetime.strptime(args.custom_date, "%Y-%m-%d")
        except ValueError:
            print(f"Error: Invalid date format: {args.custom_date}")
            sys.exit(1)
    
    # Process media files
    process_media(
        args.input_directory,
        args.output_directory,
        args.dry_run,
        custom_date,
        args.index_uri,
        args.move
    )

if __name__ == '__main__':
    main()