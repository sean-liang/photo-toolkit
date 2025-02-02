#!/usr/bin/env python3

import os
import sys
import argparse
from pathlib import Path

from core.indexer import BaseIndexer


def view_index(work_dir: str, index_uri: str = "dbm+sha256://hash.index", n: int = 10):
    """View index content.
    
    Args:
        work_dir: Working directory path
        index_uri: URI for the index storage, format: scheme[+hash_algo]://filename
        n: Number of items to show
    """
    try:
        # Create indexer
        indexer = BaseIndexer.create(index_uri, work_dir)
        
        with indexer:
            # Get top N items
            items = indexer.list(n)

            # Show items
            print(f"First {len(items)} items:")
            print("-" * 80)
            for hash_value, path in items:
                print(f"Hash: {hash_value}")
                print(f"Path: {path}")
                print("-" * 80)
                
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="View index content")
    parser.add_argument("work_directory", help="Working directory path")
    parser.add_argument("--index-uri", default="dbm+sha256://hash.index",
                      help="URI for the index storage, format: scheme[+hash_algo]://filename (default: dbm+sha256://hash.index)")
    parser.add_argument("-n", type=int, default=10,
                      help="Number of items to show (default: 10)")
    
    args = parser.parse_args()
    
    # Convert to absolute path
    work_dir = os.path.abspath(args.work_directory)
    
    # Check if directory exists
    if not os.path.isdir(work_dir):
        print(f"Error: Directory not found: {work_dir}")
        sys.exit(1)
    
    # View index
    view_index(work_dir, args.index_uri, args.n)


if __name__ == "__main__":
    main()