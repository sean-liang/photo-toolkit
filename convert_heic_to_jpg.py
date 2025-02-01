import os
import argparse
from pathlib import Path
from pillow_heif import register_heif_opener
from PIL import Image
from tqdm import tqdm

def convert_heic_to_jpeg(input_dir: str, output_dir: str = None):
    # Register HEIF file opener
    register_heif_opener()
    
    if output_dir is None:
        parent_dir = os.path.dirname(input_dir)
        output_dir = os.path.join(parent_dir, f'{os.path.basename(input_dir)}_heic_to_jpg')
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
    else:
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
    
    # Collect all HEIC files
    heic_files = []
    for root, _, files in os.walk(input_dir):
        for file in files:
            if file.lower().endswith(('.heic', '.heif')):
                heic_files.append((root, file))
    
    # Use tqdm to show progress
    for root, file in tqdm(heic_files, desc="Converting HEIC to JPEG"):
        input_path = os.path.join(root, file)
        output_filename = os.path.splitext(file)[0] + '.jpg'
        output_path = os.path.join(output_dir, output_filename)
        
        try:
            # Open HEIC file
            image = Image.open(input_path)
            
            # Get original image EXIF data
            exif = image.getexif()
            
            # Convert to RGB mode (if needed)
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Convert and save as JPEG, preserving EXIF data
            image.save(output_path, 'JPEG', quality=95, exif=exif)
        except Exception as e:
            tqdm.write(f'Conversion failed for {input_path}: {str(e)}')

def main():
    parser = argparse.ArgumentParser(description='Convert HEIC files to JPEG format')
    parser.add_argument('input_dir', help='Input directory path (containing HEIC files)')
    parser.add_argument('output_dir', nargs='?', help='Output directory path (for saving JPEG files)')
    
    args = parser.parse_args()
    convert_heic_to_jpeg(args.input_dir, args.output_dir)

if __name__ == '__main__':
    main()