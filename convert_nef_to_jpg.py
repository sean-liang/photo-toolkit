import argparse
from pathlib import Path
import rawpy
from PIL import Image
from tqdm import tqdm
import piexif
from core.common import find_files

def filter_exif(exif_dict):
    """Filter EXIF dictionary to keep only essential tags"""
    # Essential EXIF tags to keep
    essential_tags = {
        # Basic image info
        "0th": {
            piexif.ImageIFD.Make,           # Camera manufacturer
            piexif.ImageIFD.Model,          # Camera model
            piexif.ImageIFD.Software,       # Software
            piexif.ImageIFD.DateTime,       # Modification date
        },
        # Detailed photo info
        "Exif": {
            piexif.ExifIFD.DateTimeOriginal,        # Original date
            piexif.ExifIFD.DateTimeDigitized,       # Digitized date
            piexif.ExifIFD.ExposureTime,           # Shutter speed
            piexif.ExifIFD.FNumber,                # Aperture
            piexif.ExifIFD.ExposureProgram,        # Exposure program
            piexif.ExifIFD.ISOSpeedRatings,        # ISO speed
            piexif.ExifIFD.ExposureBiasValue,      # Exposure compensation
            piexif.ExifIFD.MeteringMode,           # Metering mode
            piexif.ExifIFD.FocalLength,            # Focal length
            piexif.ExifIFD.FocalLengthIn35mmFilm,  # 35mm equivalent focal length
            piexif.ExifIFD.LensModel,              # Lens model
        },
        # GPS data (keep all if present)
        "GPS": None,
    }
    
    filtered = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}}
    
    # Copy only essential tags
    for ifd in essential_tags:
        if ifd in exif_dict and exif_dict[ifd]:
            if essential_tags[ifd] is None:
                # Keep all tags for this IFD (e.g., GPS)
                filtered[ifd] = exif_dict[ifd]
            else:
                # Keep only specified tags
                for tag in essential_tags[ifd]:
                    if tag in exif_dict[ifd]:
                        filtered[ifd][tag] = exif_dict[ifd][tag]
    
    return filtered

def convert_nef_to_jpg(input_dir: str, output_dir: str):
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    
    # Create output directory if it doesn't exist
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Find all NEF files
    nef_files = find_files(input_dir, extensions={'.nef'})
    
    # Process each NEF file
    for nef_file in tqdm(nef_files, desc="Converting NEF to JPG"):
        try:
            # Get relative path to maintain directory structure
            rel_path = Path(nef_file).relative_to(input_path)
            # Create output path with jpg extension
            jpg_path = output_path / rel_path.with_suffix('.jpg')
            # Create parent directories if they don't exist
            jpg_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Skip if output file already exists
            if jpg_path.exists():
                tqdm.write(f"Skipping {rel_path} - output file already exists")
                continue
            
            # Try to read EXIF data from NEF file
            try:
                exif_dict = piexif.load(str(nef_file))
                # Filter EXIF data to keep only essential tags
                exif_dict = filter_exif(exif_dict)
            except Exception as e:
                tqdm.write(f"Warning: Could not read EXIF data from {rel_path}: {str(e)}")
                exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}}
            
            # Read and process NEF file
            with rawpy.imread(str(nef_file)) as raw:
                # Process the raw data with default parameters
                rgb = raw.postprocess()

            # Convert to PIL Image
            img = Image.fromarray(rgb)
            
            # Save image with EXIF data
            if any(exif_dict.values()):
                try:
                    exif_bytes = piexif.dump(exif_dict)
                    img.save(jpg_path, quality=95, exif=exif_bytes)
                except Exception as e:
                    tqdm.write(f"Warning: Could not save EXIF data for {rel_path}: {str(e)}")
                    img.save(jpg_path, quality=95)
            else:
                img.save(jpg_path, quality=95)
            
            tqdm.write(f"Converted {rel_path}")
            
        except Exception as e:
            tqdm.write(f"Error processing {nef_file}: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description='Convert NEF files to JPG format')
    parser.add_argument('input_dir', help='Input directory containing NEF files')
    parser.add_argument('output_dir', help='Output directory for JPG files')
    
    args = parser.parse_args()
    convert_nef_to_jpg(args.input_dir, args.output_dir)

if __name__ == '__main__':
    main()