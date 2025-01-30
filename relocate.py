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
    """获取文件的创建日期和修改日期中的最早日期"""
    try:
        ctime = os.path.getctime(file_path)
        mtime = os.path.getmtime(file_path)
        # 返回较早的日期
        return datetime.fromtimestamp(min(ctime, mtime))
    except Exception as e:
        print(f"Warning: Error getting file dates for {file_path}: {str(e)}")
        # 如果出错，返回修改时间
        return datetime.fromtimestamp(os.path.getmtime(file_path))

def get_image_date(image_path, custom_date=None):
    """获取图片的创建日期，如果提供了自定义日期则使用自定义日期"""
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
    
    # 如果无法从EXIF获取日期，使用文件最早的日期
    return get_earliest_file_date(image_path)

def get_video_date(video_path):
    """获取视频文件的创建日期"""
    try:
        # 使用 ffmpeg 获取视频元数据
        probe = ffmpeg.probe(str(video_path))
        
        # 检查格式元数据
        if 'format' in probe and 'tags' in probe['format']:
            tags = probe['format']['tags']
            
            # 按优先级尝试不同的日期字段
            date_fields = [
                'creation_time',          # 创建时间
                'com.apple.quicktime.creationdate',  # QuickTime 创建日期
                'date',                   # 日期
                'DateTimeOriginal',       # 原始日期时间
                'date_time',              # 日期时间
                'media_create_time',      # 媒体创建时间
            ]
            
            for field in date_fields:
                if field in tags:
                    date_str = tags[field]
                    try:
                        # 处理不同的日期格式
                        if 'T' in date_str:
                            # ISO 格式: 2024-01-30T12:34:56
                            date_str = date_str.split('.')[0]  # 移除可能的毫秒
                            return datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S')
                        elif '-' in date_str:
                            # 标准格式: 2024-01-30 12:34:56
                            return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                        else:
                            # QuickTime 格式: 2024:01:30 12:34:56
                            return datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S')
                    except ValueError:
                        continue
        
        # 检查视频流元数据
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
    
    # 如果无法从元数据获取日期，使用文件最早的日期
    return get_earliest_file_date(video_path)

def get_media_date(file_path, custom_date=None):
    """获取媒体文件（图片或视频）的创建日期"""
    if custom_date:
        return custom_date

    if is_image_file(file_path):
        return get_image_date(file_path)
    elif is_video_file(file_path):
        return get_video_date(file_path)
    else:
        return get_earliest_file_date(file_path)

def get_max_id_for_timestamp(target_dir, timestamp):
    """获取指定时间戳在目标目录中已存在的最大ID"""
    if not target_dir.exists():
        return 0
        
    # 正则表达式匹配文件名格式：YYYYMMDDHHMMSS_NNNNN.ext
    pattern = re.compile(rf"{timestamp}_(\d{{5}})\..*$")
    max_id = 0
    
    # 检查目标目录中的所有文件
    for file in target_dir.iterdir():
        if file.is_file():
            match = pattern.search(file.name)
            if match:
                file_id = int(match.group(1))
                max_id = max(max_id, file_id)
    
    return max_id

def get_new_filename(date, original_path, target_dir):
    """
    生成新的文件名和路径，格式：YYYY/MM/YYYYMMDDHHMMSS_ID.ext
    
    Args:
        date: datetime, 文件的日期
        original_path: Path, 原始文件路径
        target_dir: Path, 目标根目录
    
    Returns:
        tuple: (相对路径, 完整路径)
    """
    # 获取年月信息
    year = date.strftime('%Y')
    month = date.strftime('%m')
    
    # 构建目标子目录路径
    sub_dir = os.path.join(year, month)
    full_dir = os.path.join(target_dir, sub_dir)
    
    # 获取时间戳字符串
    timestamp = date.strftime('%Y%m%d%H%M%S')
    
    # 获取当前时间戳在目标目录中的最大ID
    max_id = get_max_id_for_timestamp(Path(full_dir), timestamp)
    
    # 新ID为最大ID + 1
    new_id = max_id + 1
    
    # 保持原始文件扩展名
    ext = original_path.suffix.lower()
    
    # 生成新文件名
    filename = f"{timestamp}_{new_id:05d}{ext}"
    
    # 返回相对路径和完整路径
    rel_path = os.path.join(sub_dir, filename)
    full_path = os.path.join(target_dir, rel_path)
    
    return rel_path, full_path

def set_image_date(image_path, target_date):
    """设置图片的EXIF日期信息"""
    try:
        # 转换日期为EXIF格式的字符串
        date_str = target_date.strftime('%Y:%m:%d %H:%M:%S')
        
        # 读取现有的EXIF数据
        try:
            exif_dict = piexif.load(str(image_path))
        except:
            # 如果没有EXIF数据，创建一个新的
            exif_dict = {'0th': {}, 'Exif': {}, 'GPS': {}, '1st': {}, 'thumbnail': None}
        
        # 设置DateTime (306)在0th IFD中
        exif_dict['0th'][piexif.ImageIFD.DateTime] = date_str
        # 设置DateTimeOriginal (36867)在Exif IFD中
        exif_dict['Exif'][piexif.ExifIFD.DateTimeOriginal] = date_str
        # 设置DateTimeDigitized (36868)在Exif IFD中
        exif_dict['Exif'][piexif.ExifIFD.DateTimeDigitized] = date_str
        
        # 将EXIF数据转换为bytes
        exif_bytes = piexif.dump(exif_dict)
        
        # 保存EXIF数据到图片
        piexif.insert(exif_bytes, str(image_path))
    except Exception as e:
        print(f"警告：无法修改图片 {image_path} 的EXIF信息：{str(e)}")

def process_media(input_dir, output_dir, dry_run=False, custom_date=None):
    """处理所有媒体文件"""
    # 确保输出目录存在
    if not dry_run:
        os.makedirs(output_dir, exist_ok=True)
        
    # 打开或创建哈希索引数据库
    db_path = os.path.join(output_dir, "hash.index")
    db = dbm.open(db_path, 'c')
    
    try:
        # 查找所有媒体文件
        media_files = list(find_media_files(input_dir))
        
        # 初始化计数器
        copied_count = 0
        duplicate_count = 0
        
        # 使用tqdm显示进度
        pbar = tqdm(media_files, desc="Processing files")
        for rel_path, full_path in pbar:
            try:
                # 获取文件创建日期
                date = get_media_date(full_path, custom_date)
                
                # 生成新的文件名和路径
                new_rel_path, new_path = get_new_filename(date, Path(full_path), Path(output_dir))
                
                if not dry_run:
                    # 先计算文件哈希并检查是否重复
                    file_hash = calculate_file_hash(full_path)
                    is_duplicate, original_path, _ = check_file_duplicate(full_path, db, file_hash)
                    
                    if is_duplicate:
                        # 更新重复文件计数
                        duplicate_count += 1
                        pbar.set_postfix(copied=copied_count, duplicates=duplicate_count)
                        continue
                    
                    # 创建目标目录（如果不存在）
                    os.makedirs(os.path.dirname(new_path), exist_ok=True)
                    
                    # 复制文件
                    shutil.copy2(full_path, new_path)
                    
                    # 将文件信息添加到索引中
                    db[f"f:{new_rel_path}".encode()] = file_hash.encode()
                    db[f"h:{file_hash}".encode()] = new_rel_path.encode()
                    
                    # 如果是图片文件，尝试设置EXIF日期
                    if custom_date is not None and is_image_file(new_path):
                        set_image_date(new_path, date)
                    
                    # 更新已复制文件计数
                    copied_count += 1
                    pbar.set_postfix(copied=copied_count, duplicates=duplicate_count)
                
            except Exception as e:
                print(f"Error processing {full_path}: {str(e)}")
                
        # 在进度条完成后显示最终统计信息
        print(f"\n处理完成：已复制 {copied_count} 个文件，跳过 {duplicate_count} 个重复文件")
    finally:
        db.close()

def main():
    parser = argparse.ArgumentParser(description="按日期整理照片到指定目录")
    parser.add_argument('input_dir', help="输入目录路径")
    parser.add_argument('output_dir', help="输出目录路径")
    parser.add_argument('--dry-run', action='store_true', help="仅显示将创建的目录结构，不实际复制文件")
    parser.add_argument('--date', help="指定日期时间，格式：YYYY-MM-DD HH:MM:SS，如果不指定则从EXIF中读取")
    
    args = parser.parse_args()
    
    # 验证输入目录存在
    if not os.path.isdir(args.input_dir):
        print(f"错误：输入目录 '{args.input_dir}' 不存在")
        return
    
    # 解析自定义日期
    custom_date = None
    if args.date:
        try:
            custom_date = datetime.strptime(args.date, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            print("错误：日期格式不正确，请使用 YYYY-MM-DD HH:MM:SS 格式")
            return
    
    # 处理媒体文件
    process_media(args.input_dir, args.output_dir, args.dry_run, custom_date)

if __name__ == '__main__':
    main()