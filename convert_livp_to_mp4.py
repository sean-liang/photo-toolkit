#!/usr/bin/env python3
import shutil
from pathlib import Path
import zipfile
from tqdm import tqdm
import piexif
import json
from core.common import find_files

LIVP_EXTENSIONS = {'.livp'}

def extract_livp(livp_path, output_path):
    """Extract MOV file and EXIF information from LIVP file"""
    try:
        with zipfile.ZipFile(livp_path, 'r') as zip_ref:
            # Find .MOV file and EXIF information
            mov_files = [f for f in zip_ref.namelist() if f.lower().endswith('.mov')]
            json_files = [f for f in zip_ref.namelist() if f.lower().endswith('.json')]
            
            if not mov_files:
                return False
            
            # Extract MOV file
            mov_file = mov_files[0]
            with zip_ref.open(mov_file) as source, open(output_path, 'wb') as target:
                shutil.copyfileobj(source, target)
            
            # Extract and process EXIF information
            if json_files:
                try:
                    with zip_ref.open(json_files[0]) as f:
                        exif_data = json.load(f)
                        # Create basic EXIF data structure
                        exif_dict = {
                            "0th": {},
                            "Exif": {},
                            "GPS": {},
                            "1st": {},
                            "thumbnail": None
                        }
                        
                        # Convert key EXIF information
                        if 'date' in exif_data:
                            exif_dict["0th"][piexif.ImageIFD.DateTime] = exif_data['date'].encode('utf-8')
                        if 'location' in exif_data:
                            loc = exif_data['location']
                            if 'latitude' in loc and 'longitude' in loc:
                                lat = float(loc['latitude'])
                                lon = float(loc['longitude'])
                                exif_dict["GPS"][piexif.GPSIFD.GPSLatitude] = piexif.GPSHelper.deg_to_dms(abs(lat))
                                exif_dict["GPS"][piexif.GPSIFD.GPSLongitude] = piexif.GPSHelper.deg_to_dms(abs(lon))
                                exif_dict["GPS"][piexif.GPSIFD.GPSLatitudeRef] = 'N' if lat >= 0 else 'S'
                                exif_dict["GPS"][piexif.GPSIFD.GPSLongitudeRef] = 'E' if lon >= 0 else 'W'
                        
                        # Write EXIF information to file
                        try:
                            exif_bytes = piexif.dump(exif_dict)
                            piexif.insert(exif_bytes, str(output_path))
                        except Exception as e:
                            tqdm.write(f"Failed to write EXIF information: {e}")
                except Exception as e:
                    tqdm.write(f"Failed to process EXIF information: {e}")
            
            return True
    except Exception as e:
        tqdm.write(f"Failed to process file: {e}")
        return False

def process_livp_files(input_dir, output_dir):
    """Process all LIVP files in the specified directory"""
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Get all LIVP files
    livp_files = find_files(input_dir, extensions=LIVP_EXTENSIONS)
    
    if not livp_files:
        print("No LIVP files found")
        return

    for livp_file in tqdm(livp_files, desc="Extracting MOV files"):
        # Build output file path, maintaining relative path structure
        relative_path = Path(livp_file).relative_to(input_path)
        output_file = output_path / relative_path.with_suffix('.mov')
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Extract file
        if extract_livp(livp_file, str(output_file)):
            tqdm.write(f"Successfully extracted: {relative_path}")
        else:
            tqdm.write(f"Failed to extract: {relative_path}")

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Extract MOV videos from LIVP files')
    parser.add_argument('input_dir', help='Input directory path')
    parser.add_argument('output_dir', help='Output directory path')
    args = parser.parse_args()

    process_livp_files(args.input_dir, args.output_dir)

if __name__ == '__main__':
    main()