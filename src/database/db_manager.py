import logging
import os
import time
from bit import Key
from dotenv import load_dotenv
import psycopg2
from psycopg2 import pool
import logging

load_dotenv()

db_config = {
  "host": os.getenv("DB_HOST"),
  "user": os.getenv("DB_USER"),
  "password": os.getenv("DB_PASSWORD"),
  "dbname": os.getenv("DB_NAME"),
  "sslmode": os.getenv("DB_SSLMODE", "prefer")  # SSL mode: prefer (default), verify-ca, verify-full, disable
}
db_pool = None

def initialize_pool():
    global db_pool
    try:
        # Increase connection pool size for better performance but reduce from 50 to 20
        # to avoid connection issues
        db_pool = pool.ThreadedConnectionPool(minconn=5, maxconn=20, **db_config)
        
        # Set connection parameters for better performance
        conn = db_pool.getconn()
        try:
            # Create a cursor and enable autocommit mode to avoid transaction issues
            conn.autocommit = True
            cur = conn.cursor()
            
            # Apply performance settings but with more conservative values
            cur.execute("SET synchronous_commit TO OFF;")
            cur.execute("SET work_mem TO '16MB';")
            
            # Close cursor
            cur.close()
        finally:
            # Return connection to the pool
            db_pool.putconn(conn)
            
        logging.info("PostgreSQL pool initialized successfully with optimized settings.")
    except psycopg2.Error as e:
        logging.error(f"Error initializing PostgreSQL pool: {e}")
        db_pool = None

initialize_pool()

def get_db_connection():
    global db_pool
    
    # If no pool, try to initialize
    if not db_pool:
        logging.warning("DB pool not initialized. Initializing now...")
        initialize_pool()
        
        # If still no pool after initialization, try with direct connection
        if not db_pool:
            logging.warning("Pool initialization failed, trying direct connection...")
            try:
                # Create a direct connection as fallback
                conn = psycopg2.connect(**db_config)
                conn.autocommit = True
                return conn
            except psycopg2.Error as e:
                logging.error(f"Direct connection failed: {e}")
                return None
    
    # Try to get connection from pool
    try:
        conn = db_pool.getconn()
        
        if conn is None:
            logging.error("Received None connection from the pool!")
            raise psycopg2.pool.PoolError("Received None connection from the pool!")
            
        # Test connection by executing a simple query
        try:
            # Create a cursor and test if connection is alive
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.close()
        except psycopg2.Error as e:
            # Connection is dead, close it and try again
            logging.warning(f"Dead connection received: {e}. Reconnecting...")
            try:
                db_pool.putconn(conn, close=True)  # Return to pool and mark for closing
                conn = db_pool.getconn()  # Get a fresh connection
            except psycopg2.Error as reconnect_error:
                logging.error(f"Error during reconnection: {reconnect_error}")
                return None
                
        return conn
    except psycopg2.Error as e:
        logging.error(f"Error while trying to get a connection: {e}")
        return None

def retry_on_db_fail(max_retries=5, delay=2):
    """A decorator to retry a function if it fails due to database connection issues."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (psycopg2.pool.PoolError, AttributeError, TypeError, psycopg2.InterfaceError, 
                       psycopg2.OperationalError) as e:
                    # Catch more error types for more robust error handling
                    error_msg = str(e).lower()
                    if ('pool is full' in error_msg or 
                        'nonetype' in error_msg or 
                        'connection' in error_msg or
                        'closed' in error_msg):
                        # Exponential backoff - wait longer between each retry
                        wait_time = delay * (2 ** attempt)
                        logging.warning(f"DB Error: {e}. Attempt {attempt+1}/{max_retries}. "
                                       f"Retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
                    else:
                        logging.error(f"Unhandled database error: {e}")
                        raise
                except Exception as e:
                    # Log any other unexpected errors
                    logging.error(f"Unexpected error in database operation: {e}")
                    if attempt == max_retries - 1:  # Last attempt
                        raise
                    time.sleep(delay)
                    
            logging.error(f"Failed after {max_retries} attempts.")
            return None  # Return None instead of raising to allow graceful fallback
        return wrapper
    return decorator

@retry_on_db_fail()
def store_wallets_in_db():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            with open('wallets.txt', 'r') as file:
                for line in file:
                    wallet_address = line.strip()
                    if wallet_address:
                        cur.execute(
                            "INSERT INTO wallets (address) VALUES (%s) ON CONFLICT (address) DO NOTHING", 
                            (wallet_address,)
                        )
        conn.commit()
    finally:
        db_pool.putconn(conn)

@retry_on_db_fail()
def import_blockchair_tsv(filepath, batch_size=10000):
    """
    Import addresses from Blockchair TSV.GZ file into the wallets table.
    
    Args:
        filepath: Path to the .tsv.gz file
        batch_size: Number of addresses to import in each batch
    """
    conn = get_db_connection()
    try:
        import gzip
        import csv
        from tqdm import tqdm
        import os
        
        # Get file size for progress tracking
        file_size = os.path.getsize(filepath)
        print(f"Importing from {filepath} ({file_size / (1024*1024):.2f} MB compressed)")
        
        # Count lines to estimate total records
        print("Estimating number of records...")
        with gzip.open(filepath, 'rt') as f:
            for count, _ in enumerate(f):
                if count == 0:  # Skip header
                    continue
                if count % 1000000 == 0:
                    print(f"Counted {count:,} lines so far...")
                if count >= 10000000:  # Stop counting after 10M lines to save time
                    print(f"More than {count:,} records detected, showing progress in batches")
                    break
        
        total_records = count
        print(f"Estimated {total_records:,} records to import")
                
        # Create temporary table for faster bulk loading
        with conn.cursor() as cur:
            # Create temporary table
            cur.execute("""
            CREATE TEMP TABLE temp_wallets (
                address TEXT PRIMARY KEY
            ) ON COMMIT DROP;
            """)
            conn.commit()
            
            # Process file in batches
            batch_count = 0
            record_count = 0
            address_batch = []
            
            with gzip.open(filepath, 'rt') as f:
                # Skip header
                next(f)
                
                # Create CSV reader with tab delimiter
                reader = csv.reader(f, delimiter='\t')
                
                # Process rows
                for i, row in enumerate(reader):
                    if not row or len(row) < 1:
                        continue
                        
                    address = row[0].strip()
                    if address:
                        address_batch.append((address,))
                        
                    # Process batch when it reaches batch_size
                    if len(address_batch) >= batch_size:
                        with conn.cursor() as cur:
                            try:
                                # Use executemany for batch insertion into temp table
                                cur.executemany(
                                    "INSERT INTO temp_wallets (address) VALUES (%s) ON CONFLICT (address) DO NOTHING", 
                                    address_batch
                                )
                                # Move from temp to main table
                                cur.execute("""
                                INSERT INTO wallets (address)
                                SELECT address FROM temp_wallets
                                ON CONFLICT (address) DO NOTHING;
                                """)
                                # Clear temp table for next batch
                                cur.execute("TRUNCATE TABLE temp_wallets;")
                                conn.commit()
                                
                                batch_count += 1
                                record_count += len(address_batch)
                                print(f"Imported batch {batch_count}: {record_count:,} addresses ({record_count/total_records*100:.2f}% complete)")
                                
                            except Exception as e:
                                conn.rollback()
                                logging.error(f"Error in batch import: {e}")
                                
                        # Clear batch
                        address_batch = []
            
            # Process any remaining addresses
            if address_batch:
                with conn.cursor() as cur:
                    try:
                        cur.executemany(
                            "INSERT INTO temp_wallets (address) VALUES (%s) ON CONFLICT (address) DO NOTHING", 
                            address_batch
                        )
                        cur.execute("""
                        INSERT INTO wallets (address)
                        SELECT address FROM temp_wallets
                        ON CONFLICT (address) DO NOTHING;
                        """)
                        conn.commit()
                        
                        record_count += len(address_batch)
                        print(f"Imported final batch: {record_count:,} addresses total")
                        
                    except Exception as e:
                        conn.rollback()
                        logging.error(f"Error in final batch import: {e}")
                        
        print(f"Import complete. Imported {record_count:,} addresses.")
        
    except Exception as e:
        logging.error(f"Error importing Blockchair TSV: {e}")
        raise
    finally:
        db_pool.putconn(conn)
                        

@retry_on_db_fail()
def address_exists_in_db(address):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            try:
                cur.execute("SELECT 1 FROM wallets WHERE address = %s", (address,))
                exists = cur.fetchone()
                return exists is not None
            except psycopg2.ProgrammingError as e:
                if "no results to fetch" in str(e):
                    # This happens when the query returns no rows
                    logging.debug(f"No result for address: {address}")
                    return False
                else:
                    # Re-raise other programming errors
                    raise
    finally:
        db_pool.putconn(conn)
        
@retry_on_db_fail()
def check_addresses_batch(addresses):
    """
    Check multiple addresses against the database in a single query.
    Returns a list of addresses that were found in the database.
    """
    if not addresses:
        return []
        
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            try:
                placeholders = ','.join(['%s'] * len(addresses))
                query = f"SELECT address FROM wallets WHERE address IN ({placeholders})"
                cur.execute(query, addresses)
                
                # Safely handle empty result sets
                result = cur.fetchall()
                if result:
                    found_addresses = [row[0] for row in result]
                    return found_addresses
                else:
                    return []
            except psycopg2.ProgrammingError as e:
                if "no results to fetch" in str(e):
                    # This happens when the query returns no rows
                    logging.debug("No matching addresses found in the database")
                    return []
                else:
                    # Re-raise other programming errors
                    raise
    finally:
        db_pool.putconn(conn)

@retry_on_db_fail()
def create_tables():
    """Create necessary tables in the PostgreSQL database."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Create wallets table if it doesn't exist
            cur.execute('''
            CREATE TABLE IF NOT EXISTS wallets (
                address TEXT PRIMARY KEY
            );
            ''')
            
            # Use NUMERIC(78, 0) instead of BIGINT for progress values
            # Bitcoin addresses are derived from 256-bit numbers, so we need a much larger
            # numeric type to store these values
            cur.execute('''
            CREATE TABLE IF NOT EXISTS progress (
                id SERIAL PRIMARY KEY,
                instance INTEGER UNIQUE NOT NULL,
                value NUMERIC(78, 0) NOT NULL,
                updated_at DATE DEFAULT CURRENT_DATE
            );
            ''')

            cur.execute('''
            CREATE TABLE IF NOT EXISTS wallet_database (
                id SERIAL PRIMARY KEY,
                wif TEXT NOT NULL,
                address TEXT NOT NULL,
                balance REAL NOT NULL
            );
            ''')

            cur.execute('''
            CREATE TABLE IF NOT EXISTS hash_rates (
                id SERIAL PRIMARY KEY,
                instance INTEGER NOT NULL,
                hash_rate REAL NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            ''')
            
            # Try to modify existing column type if table exists but has incorrect type
            try:
                cur.execute('''
                ALTER TABLE progress 
                ALTER COLUMN value TYPE NUMERIC(78, 0);
                ''')
                logging.info("Modified progress.value column to NUMERIC(78, 0)")
            except psycopg2.Error as e:
                logging.warning(f"Could not modify progress.value column: {e}")
                
            conn.commit()
    finally:
        if conn is not None and db_pool is not None:
            db_pool.putconn(conn)

@retry_on_db_fail()
def test_address_insertion():
    simulated_key = Key()
    simulated_address = simulated_key.address
    simulated_wif = simulated_key.to_wif()
    print(f"Simulated address: {simulated_address}")

    if address_exists_in_db(simulated_address):
        print(f"Address {simulated_address} already exists in the database!")
        return

    save_to_wallet_database(simulated_wif, simulated_address, 0)

    if address_exists_in_db(simulated_address):
        print(f"Address {simulated_address} was successfully saved to the database!")
    else:
        print(f"Failed to save address {simulated_address} to the database.")

    with open('wallet_database.txt', 'r') as file:
        if simulated_address in file.read():
            print(f"Address {simulated_address} was successfully saved to wallet_database.txt!")
        else:
            print(f"Failed to save address {simulated_address} to wallet_database.txt.")
            
@retry_on_db_fail()
def save_progress(instance, value):
    """Save progress to the PostgreSQL database."""
    conn = get_db_connection()
    
    if conn is None:
        logging.error("Unable to get database connection for save_progress")
        return
        
    try:
        with conn.cursor() as cur:
            try:
                # Convert value to string first to handle extremely large integers
                value_str = str(value)
                
                cur.execute("""
                INSERT INTO progress (instance, value)
                VALUES (%s, %s::numeric)
                ON CONFLICT (instance) 
                DO UPDATE SET value = EXCLUDED.value, updated_at = CURRENT_DATE;
                """, (instance, value_str))
                conn.commit()
                
                # Log occasional progress for monitoring
                if int(value_str) % 1000000 == 0:
                    logging.info(f"Progress saved for instance {instance}: {int(value_str):,}")
                    
            except psycopg2.Error as e:
                logging.error(f"Database error during save_progress: {e}")
                conn.rollback()  # Rollback transaction on error
    finally:
        if conn is not None and db_pool is not None:
            db_pool.putconn(conn)

@retry_on_db_fail()
def load_progress(instance):
    """Load progress from the PostgreSQL database."""
    conn = get_db_connection()
    
    if conn is None:
        logging.error("Failed to get database connection")
        return None
    
    try:
        # Set cursor to handle errors better
        with conn.cursor() as cur:
            try:
                # Ensure tables exist before querying - use NUMERIC instead of BIGINT
                # for larger number storage capability
                cur.execute("""
                CREATE TABLE IF NOT EXISTS progress (
                    id SERIAL PRIMARY KEY,
                    instance INTEGER UNIQUE NOT NULL,
                    value NUMERIC(78, 0) NOT NULL,
                    updated_at DATE DEFAULT CURRENT_DATE
                );
                """)
                conn.commit()
                
                # Now query
                cur.execute("SELECT value FROM progress WHERE instance = %s", (instance,))
                result = cur.fetchone()
                return result[0] if result else None
            except psycopg2.ProgrammingError as e:
                if "no results to fetch" in str(e):
                    # This happens when the query returns no rows
                    logging.debug(f"No progress found for instance {instance}")
                    return None
                else:
                    # Log other errors
                    logging.error(f"Database error: {e}")
                    return None
            except psycopg2.Error as e:
                logging.error(f"Database error: {e}")
                return None
    finally:
        if conn is not None and db_pool is not None:
            db_pool.putconn(conn)

@retry_on_db_fail()
def save_to_wallet_database(wif, address, balance):
    """Save wallet details to file and database."""
    # First save to text file
    try:
        with open('wallet_database.txt', 'a') as wallet_db:
            wallet_db.write(f'{wif},{address},{balance}\n')
    except Exception as e:
        logging.error(f"Error saving to wallet_database.txt: {e}")
    
    # Then save to database
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            try:
                cur.execute("""
                INSERT INTO wallet_database (wif, address, balance)
                VALUES (%s, %s, %s);
                """, (wif, address, balance))
                conn.commit()
            except psycopg2.Error as e:
                logging.error(f"Database error during wallet insertion: {e}")
    finally:
        db_pool.putconn(conn)
        
@retry_on_db_fail()
def batch_save_to_wallet_database(wallet_data):
    """
    Save multiple wallet details to file and database in a batch.
    wallet_data should be a list of tuples (wif, address, balance).
    """
    if not wallet_data:
        return
        
    # First save to text file
    try:
        with open('wallet_database.txt', 'a') as wallet_db:
            for wif, address, balance in wallet_data:
                wallet_db.write(f'{wif},{address},{balance}\n')
    except Exception as e:
        logging.error(f"Error saving batch to wallet_database.txt: {e}")
    
    # Then save to database
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            try:
                # Using executemany for batch insertion
                cur.executemany("""
                INSERT INTO wallet_database (wif, address, balance)
                VALUES (%s, %s, %s);
                """, wallet_data)
                conn.commit()
            except psycopg2.Error as e:
                logging.error(f"Database error during batch wallet insertion: {e}")
    finally:
        db_pool.putconn(conn)

@retry_on_db_fail()         
def insert_hash_rate(instance, hash_rate):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            try:
                cur.execute("INSERT INTO hash_rates (instance, hash_rate) VALUES (%s, %s)", (instance, hash_rate))
                conn.commit()
            except psycopg2.Error as e:
                logging.error(f"Database error while inserting hash rate: {e}")
    finally:
        db_pool.putconn(conn)
                
@retry_on_db_fail()
def get_total_addresses():
    """Return total number of addresses processed."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            try:
                cur.execute("SELECT COUNT(*) FROM progress")
                result = cur.fetchone()
                return result[0] if result else 0
            except psycopg2.ProgrammingError as e:
                if "no results to fetch" in str(e):
                    logging.debug("No total addresses found")
                    return 0
                else:
                    raise
            except psycopg2.Error as e:
                logging.error(f"Database error in get_total_addresses: {e}")
                return 0
    finally:
        db_pool.putconn(conn)

@retry_on_db_fail()
def get_total_found_addresses():
    """Return total number of found addresses."""
    conn = get_db_connection()  
    try:
        with conn.cursor() as cur:
            try:
                cur.execute("SELECT COUNT(*) FROM wallet_database")
                result = cur.fetchone()
                return result[0] if result else 0
            except psycopg2.ProgrammingError as e:
                if "no results to fetch" in str(e):
                    logging.debug("No found addresses")
                    return 0
                else:
                    raise
            except psycopg2.Error as e:
                logging.error(f"Database error in get_total_found_addresses: {e}")
                return 0
    finally:
        db_pool.putconn(conn)

@retry_on_db_fail()
def get_total_addresses_to_bruteforce():
    """Return total number of addresses to be bruteforced."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            try:
                cur.execute("SELECT COUNT(*) FROM wallets") 
                result = cur.fetchone()
                return result[0] if result else 0
            except psycopg2.ProgrammingError as e:
                if "no results to fetch" in str(e):
                    logging.debug("No addresses to bruteforce")
                    return 0
                else:
                    raise
            except psycopg2.Error as e:
                logging.error(f"Database error in get_total_addresses_to_bruteforce: {e}")
                return 0
    finally:
        db_pool.putconn(conn)
