import os
from pathlib import Path
import pillow_heif
from PIL import Image
from tqdm import tqdm
from core.common import find_files

HEIC_EXTENSIONS = {'.heic'}

def convert_heic_to_jpeg(input_dir: str, output_dir: str = None):
    # Register HEIF file opener
    pillow_heif.register_heif_opener()
    
    if output_dir is None:
        parent_dir = os.path.dirname(input_dir)
        output_dir = os.path.join(parent_dir, f'{os.path.basename(input_dir)}_heic_to_jpg')
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
    else:
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
    
    # Find all HEIC files
    heic_files = list(find_files(input_dir, extensions=HEIC_EXTENSIONS))
    
    if not heic_files:
        print("No HEIC files found")
        return
    
    # Use tqdm to show progress
    for file in tqdm(heic_files, desc="Converting HEIC to JPEG"):
        try:
            # Open HEIC file
            with Image.open(file) as img:
                # Create output filename
                output_filename = os.path.splitext(os.path.basename(file))[0] + '.jpg'
                output_path = os.path.join(output_dir, output_filename)
                
                # Get original image EXIF data
                exif = img.getexif()
                
                # Convert to RGB mode (if needed)
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Save as JPEG, preserving EXIF data
                img.save(output_path, 'JPEG', quality=95, exif=exif)
                
        except Exception as e:
            tqdm.write(f'Conversion failed for {file}: {str(e)}')

def main():
    parser = argparse.ArgumentParser(description='Convert HEIC files to JPEG format')
    parser.add_argument('input_dir', help='Input directory path (containing HEIC files)')
    parser.add_argument('output_dir', nargs='?', help='Output directory path (for saving JPEG files)')
    
    args = parser.parse_args()
    convert_heic_to_jpeg(args.input_dir, args.output_dir)

if __name__ == '__main__':
    main()