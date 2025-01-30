import os
import sys
import hashlib
import dbm
import argparse
import shutil
from tqdm import tqdm
from common import find_media_files

def calculate_file_hash(file_path):
    """计算文件的 SHA-256 哈希值"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def process_duplicate_file(file_path, original_path, dups_path):
    """
    处理重复文件，将其移动到重复文件目录并创建对应的文本文件记录原始路径
    
    Args:
        file_path: str, 重复文件的完整路径
        original_path: str, 原始文件的路径
        dups_path: str, 重复文件存储目录的路径
    
    Returns:
        str: 移动后的文件路径
    """
    # 确保重复文件目录存在
    os.makedirs(dups_path, exist_ok=True)
    
    # 获取文件名
    file_name = os.path.basename(file_path)
    dup_file_path = os.path.join(dups_path, file_name)
    
    # 如果重复文件已存在，确保文件名唯一
    base_name, ext = os.path.splitext(file_name)
    counter = 1
    while os.path.exists(dup_file_path):
        dup_file_path = os.path.join(dups_path, f"{base_name}_{counter}{ext}")
        counter += 1
    
    # 移动重复文件到dups目录
    shutil.move(file_path, dup_file_path)
    
    # 创建同名的txt文件，记录原始文件路径
    txt_path = os.path.splitext(dup_file_path)[0] + '.txt'
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(original_path)
    
    return dup_file_path

def check_file_duplicate(file_path, db, hash_key=None):
    """
    检查文件是否重复
    
    Args:
        file_path: str, 要检查的文件路径
        db: dbm.open, 打开的数据库连接
        hash_key: str, 可选，文件的哈希值，如果不提供则会计算
    
    Returns:
        tuple: (is_duplicate, original_path, file_hash)
        - is_duplicate: bool, 是否是重复文件
        - original_path: str, 如果是重复文件，返回原始文件路径，否则为None
        - file_hash: str, 文件的哈希值
    """
    if hash_key is None:
        file_hash = calculate_file_hash(file_path)
    else:
        file_hash = hash_key
        
    # 检查是否存在重复文件
    hash_key = f"h:{file_hash}".encode()
    try:
        # 如果能获取到路径，说明是重复文件
        original_path = db[hash_key].decode()
        return True, original_path, file_hash
    except KeyError:
        return False, None, file_hash

def build_hash_index(work_dir, rebuild=False, dups_dir="dups"):
    """
    为指定目录下的媒体文件建立哈希索引
    
    Args:
        work_dir: str, 工作目录的路径
        rebuild: bool, 是否重建索引，默认为False
        dups_dir: str, 重复文件存储目录，默认为"dups"
    """
    # 创建或打开数据库
    db_path = os.path.join(work_dir, "hash.index")
    
    # 如果是重建模式且索引存在，则删除旧索引
    if rebuild and os.path.exists(db_path):
        try:
            os.remove(db_path)
            os.remove(db_path + '.db')  # dbm可能会创建的额外文件
        except OSError:
            pass
        print("已删除旧索引文件")
    elif not os.path.exists(db_path):
        rebuild = True
        print("未找到索引文件，将重新构建")

    # 创建重复文件目录
    dups_path = os.path.join(work_dir, dups_dir)
    os.makedirs(dups_path, exist_ok=True)

    # 打开数据库，'c'表示如果不存在则创建
    db = dbm.open(db_path, 'c')

    try:
        # 遍历所有媒体文件，排除 dups 目录
        media_files = list(find_media_files(work_dir, exclude_dirs=[dups_dir]))
        
        # 初始化计数器
        processed_count = 0
        duplicate_count = 0
        
        # 使用tqdm显示进度
        pbar = tqdm(media_files, desc="Building index")
        for rel_path, full_path in pbar:
            # 如果不是重建模式，检查文件是否已经在索引中
            if not rebuild:
                try:
                    existing_hash = db[f"f:{rel_path}".encode()]
                    processed_count += 1
                    pbar.set_postfix(processed=processed_count, duplicates=duplicate_count)
                    continue
                except KeyError:
                    pass
            
            # 检查文件是否重复
            is_duplicate, original_path, file_hash = check_file_duplicate(full_path, db)
            
            if is_duplicate:
                # 处理重复文件
                process_duplicate_file(full_path, original_path, dups_path)
                duplicate_count += 1
            else:
                # 存储文件路径到哈希的映射
                db[f"f:{rel_path}".encode()] = file_hash.encode()
                # 存储哈希到文件路径的映射
                db[f"h:{file_hash}".encode()] = rel_path.encode()
                processed_count += 1
            
            pbar.set_postfix(processed=processed_count, duplicates=duplicate_count)
            
        # 在进度条完成后显示最终统计信息
        print(f"\n索引构建完成：已处理 {processed_count} 个文件，发现 {duplicate_count} 个重复文件")
            
    finally:
        db.close()

def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="为媒体文件创建哈希索引")
    parser.add_argument("work_directory", help="工作目录路径")
    parser.add_argument("--rebuild", action="store_true", default=False,
                      help="重建索引（删除现有索引并重新创建）")
    parser.add_argument("--dups-dir", default="dups",
                      help="重复文件存储目录（默认: dups）")
    args = parser.parse_args()

    # 验证工作目录
    work_dir = os.path.abspath(args.work_directory)
    if not os.path.isdir(work_dir):
        print(f"错误：{work_dir} 不是一个有效的目录")
        sys.exit(1)

    # 执行索引构建
    build_hash_index(work_dir, args.rebuild, args.dups_dir)

if __name__ == "__main__":
    main()