#!/usr/bin/env python3
"""
Simple script to import Bitcoin addresses directly into the wallets table.
"""

import sys
import os
import gzip
import psycopg2
import logging
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables
load_dotenv()

def import_addresses(filepath, batch_size=10000):
    """Import Bitcoin addresses from TSV file into wallets table."""
    
    # Validate file exists
    if not os.path.exists(filepath):
        logging.error(f"File not found: {filepath}")
        return False
    
    # Database connection params from environment
    db_params = {
        "host": os.getenv("DB_HOST"),
        "dbname": os.getenv("DB_NAME"),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD")
    }
    
    conn = None
    try:
        # Connect to the database
        logging.info(f"Connecting to database {db_params['dbname']} on {db_params['host']}")
        conn = psycopg2.connect(**db_params)
        
        # First make sure the wallets table exists
        with conn.cursor() as cur:
            cur.execute('''
            CREATE TABLE IF NOT EXISTS wallets (
                address TEXT PRIMARY KEY
            );
            ''')
            conn.commit()
        
        # Open the input file
        logging.info(f"Opening file: {filepath}")
        
        # Count total addresses (quick estimate)
        total_addresses = 0
        with gzip.open(filepath, 'rt') as f:
            for i, _ in enumerate(f):
                if i == 0:  # Skip header row
                    continue
                if i % 1000000 == 0:
                    logging.info(f"Counted {i:,} lines...")
                if i > 10000000:  # Stop count at 10M to save time
                    break
                total_addresses = i
        
        logging.info(f"Estimated {total_addresses:,} addresses in file")
        
        # Begin import
        address_batch = []
        processed = 0
        batch_num = 0
        
        with gzip.open(filepath, 'rt') as f:
            # Skip header
            next(f)
            
            # Process each line
            for line in f:
                parts = line.strip().split('\t')
                if parts and len(parts) >= 1:
                    address = parts[0].strip()
                    if address:
                        address_batch.append((address,))
                
                # When batch is full, insert to database
                if len(address_batch) >= batch_size:
                    with conn.cursor() as cur:
                        cur.executemany(
                            "INSERT INTO wallets (address) VALUES (%s) ON CONFLICT (address) DO NOTHING",
                            address_batch
                        )
                        conn.commit()
                    
                    processed += len(address_batch)
                    batch_num += 1
                    address_batch = []
                    
                    # Log progress
                    if batch_num % 10 == 0:
                        percent = (processed / total_addresses) * 100 if total_addresses > 0 else 0
                        logging.info(f"Imported {processed:,} addresses ({percent:.2f}%) - Batch #{batch_num}")
            
            # Insert any remaining addresses
            if address_batch:
                with conn.cursor() as cur:
                    cur.executemany(
                        "INSERT INTO wallets (address) VALUES (%s) ON CONFLICT (address) DO NOTHING",
                        address_batch
                    )
                    conn.commit()
                processed += len(address_batch)
        
        # Create index if needed
        with conn.cursor() as cur:
            cur.execute("CREATE INDEX IF NOT EXISTS wallets_address_idx ON wallets (address);")
            conn.commit()
        
        logging.info(f"Import complete. Processed {processed:,} addresses.")
        return True
        
    except Exception as e:
        logging.error(f"Error during import: {e}")
        if conn:
            conn.rollback()
        return False
        
    finally:
        if conn:
            conn.close()

def main():
    if len(sys.argv) < 2:
        print("Usage: python import_wallets.py <tsv_gz_file> [batch_size]")
        return 1
    
    filepath = sys.argv[1]
    
    batch_size = 10000
    if len(sys.argv) > 2:
        try:
            batch_size = int(sys.argv[2])
        except ValueError:
            logging.warning(f"Invalid batch size: {sys.argv[2]}, using default: 10000")
    
    success = import_addresses(filepath, batch_size)
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())