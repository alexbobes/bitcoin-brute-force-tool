#!/usr/bin/env python3
"""
Import Bitcoin addresses from Blockchair dataset.
Usage: python import_blockchair.py <path_to_tsv_gz_file> [batch_size]
"""

import sys
import os
from src.database.db_manager import import_blockchair_tsv, create_tables

def main():
    # Check args
    if len(sys.argv) < 2:
        print("Usage: python import_blockchair.py <path_to_tsv_gz_file> [batch_size]")
        return 1
        
    filepath = sys.argv[1]
    
    # Validate file exists
    if not os.path.exists(filepath):
        print(f"Error: File {filepath} not found")
        return 1
        
    # Optional batch size
    batch_size = 10000
    if len(sys.argv) > 2:
        try:
            batch_size = int(sys.argv[2])
        except ValueError:
            print(f"Warning: Invalid batch size {sys.argv[2]}, using default 10000")
            
    # Ensure database tables exist
    print("Ensuring database tables exist...")
    create_tables()
    
    # Import data
    print(f"Starting import with batch size {batch_size}...")
    import_blockchair_tsv(filepath, batch_size)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())