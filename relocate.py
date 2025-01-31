import os
import argparse
from pathlib import Path
from datetime import datetime
from PIL import Image
from PIL.ExifTags import TAGS
import shutil
from tqdm import tqdm
import re
import piexif
import ffmpeg
import json
import dbm
from build_hash_index import calculate_file_hash, check_file_duplicate, process_duplicate_file
from common import MEDIA_EXTENSIONS, find_media_files, is_image_file, is_video_file

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

def get_image_date(image_path, custom_date=None):
    """Get image creation date, use custom date if provided"""
    if custom_date:
        return custom_date
    try:
        img = Image.open(image_path)
        exif = img._getexif()
        if exif:
            for tag_id in exif:
                tag = TAGS.get(tag_id, tag_id)
                data = exif[tag_id]
                if tag == 'DateTimeOriginal':
                    return datetime.strptime(data, '%Y:%m:%d %H:%M:%S')
    except Exception:
        pass
    
    # If unable to get date from EXIF, use earliest file date
    return get_earliest_file_date(image_path)

def get_video_date(video_path):
    """Get video file creation date"""
    try:
        # Use ffmpeg to get video metadata
        probe = ffmpeg.probe(str(video_path))
        
        # Check format metadata
        if 'format' in probe and 'tags' in probe['format']:
            tags = probe['format']['tags']
            
            # Try different date fields in order of priority
            date_fields = [
                'creation_time',          # Creation time
                'com.apple.quicktime.creationdate',  # QuickTime creation date
                'date',                   # Date
                'DateTimeOriginal',       # Original date time
                'date_time',              # Date time
                'media_create_time',      # Media creation time
            ]
            
            for field in date_fields:
                if field in tags:
                    date_str = tags[field]
                    try:
                        # Handle different date formats
                        if 'T' in date_str:
                            # ISO format: 2024-01-30T12:34:56
                            date_str = date_str.split('.')[0]  # Remove possible milliseconds
                            return datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S')
                        elif '-' in date_str:
                            # Standard format: 2024-01-30 12:34:56
                            return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                        else:
                            # QuickTime format: 2024:01:30 12:34:56
                            return datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S')
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
                                return datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S')
                            elif '-' in date_str:
                                return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                            else:
                                return datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S')
                        except ValueError:
                            continue
    
    except Exception as e:
        print(f"Warning: Error getting video date from ffmpeg for {video_path}: {str(e)}")
    
    # If unable to get date from metadata, use earliest file date
    return get_earliest_file_date(video_path)

def get_media_date(file_path, custom_date=None):
    """Get media file creation date"""
    if custom_date:
        return custom_date

    if is_image_file(file_path):
        return get_image_date(file_path)
    elif is_video_file(file_path):
        return get_video_date(file_path)
    else:
        return get_earliest_file_date(file_path)

def get_max_id_for_timestamp(target_dir, timestamp):
    """Get maximum ID for current timestamp in target directory"""
    if not target_dir.exists():
        return 0
        
    # Regular expression to match filename format: YYYYMMDDHHMMSS_NNNNN.ext
    pattern = re.compile(rf"{timestamp}_(\d{{5}})\..*$")
    max_id = 0
    
    # Check all files in target directory
    for file in target_dir.iterdir():
        if file.is_file():
            match = pattern.search(file.name)
            if match:
                file_id = int(match.group(1))
                max_id = max(max_id, file_id)
    
    return max_id

def get_new_filename(date, original_path, target_dir):
    """
    Generate new filename and path in format: YYYY/MM/YYYYMMDDHHMMSS_ID.ext
    
    Args:
        date: datetime, file date
        original_path: Path, original file path
        target_dir: Path, target root directory
    
    Returns:
        tuple: (relative path, full path)
    """
    # Get year and month info
    year = date.strftime('%Y')
    month = date.strftime('%m')
    
    # Build target subdirectory path
    sub_dir = os.path.join(year, month)
    full_dir = os.path.join(target_dir, sub_dir)
    
    # Get timestamp string
    timestamp = date.strftime('%Y%m%d%H%M%S')
    
    # Get maximum ID for current timestamp in target directory
    max_id = get_max_id_for_timestamp(Path(full_dir), timestamp)
    
    # New ID is max ID + 1
    new_id = max_id + 1
    
    # Keep original file extension
    ext = original_path.suffix.lower()
    
    # Generate new filename
    filename = f"{timestamp}_{new_id:05d}{ext}"
    
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

def process_media(input_dir, output_dir, dry_run=False, custom_date=None):
    """Process all media files"""
    # Ensure output directory exists
    if not dry_run:
        os.makedirs(output_dir, exist_ok=True)
        
    # Open or create hash index database
    db_path = os.path.join(output_dir, "hash.index")
    db = dbm.open(db_path, 'c')
    
    try:
        # Find all media files
        media_files = list(find_media_files(input_dir))
        
        # Initialize counters
        copied_count = 0
        duplicate_count = 0
        
        # Use tqdm to show progress
        pbar = tqdm(media_files, desc="Processing files")
        for rel_path, full_path in pbar:
            try:
                # Get file creation date
                date = get_media_date(full_path, custom_date)
                
                # Generate new filename and path
                new_rel_path, new_path = get_new_filename(date, Path(full_path), Path(output_dir))
                
                if not dry_run:
                    # Calculate file hash and check for duplicates first
                    file_hash = calculate_file_hash(full_path)
                    is_duplicate, original_path, _ = check_file_duplicate(full_path, db, file_hash)
                    
                    if is_duplicate:
                        # Update duplicate file count
                        duplicate_count += 1
                        pbar.set_postfix(copied=copied_count, duplicates=duplicate_count)
                        continue
                    
                    # Create target directory (if not exists)
                    os.makedirs(os.path.dirname(new_path), exist_ok=True)
                    
                    # Copy file
                    shutil.copy2(full_path, new_path)
                    
                    # Add file information to index
                    db[f"f:{new_rel_path}".encode()] = file_hash.encode()
                    db[f"h:{file_hash}".encode()] = new_rel_path.encode()
                    
                    # If it's an image file, try to set EXIF date
                    if custom_date is not None and is_image_file(new_path):
                        set_image_date(new_path, date)
                    
                    # Update copied file count
                    copied_count += 1
                    pbar.set_postfix(copied=copied_count, duplicates=duplicate_count)
                
            except Exception as e:
                print(f"Error processing {full_path}: {str(e)}")
                
        # Show final statistics after progress bar completion
        print(f"\nProcessing complete: {copied_count} files copied, {duplicate_count} duplicate files skipped")
    finally:
        db.close()

def main():
    parser = argparse.ArgumentParser(description="Organize photos into specified directory by date")
    parser.add_argument('input_dir', help="Input directory path")
    parser.add_argument('output_dir', help="Output directory path")
    parser.add_argument('--dry-run', action='store_true', help="Only show directory structure to be created, without actually copying files")
    parser.add_argument('--date', help="Specify date time in format: YYYY-MM-DD HH:MM:SS, if not specified will read from EXIF")
    
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
    process_media(args.input_dir, args.output_dir, args.dry_run, custom_date)

if __name__ == '__main__':
    main()