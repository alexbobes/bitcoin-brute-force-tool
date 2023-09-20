import mysql.connector
import logging
import os
from bit import Key
import time
from dotenv import load_dotenv
from mysql.connector import pooling
import logging

load_dotenv()

db_config = {
  "host": os.getenv("DB_HOST"),
  "user": os.getenv("DB_USER"),
  "password": os.getenv("DB_PASSWORD"),
  "database": os.getenv("DB_NAME"),
  "buffered": True
}
db_pool = None

def initialize_pool():
    global db_pool
    try:
        db_pool = pooling.MySQLConnectionPool(pool_name="bitcoin_pool", pool_size=20, **db_config)
        logging.info("DB pool initialized successfully.")
    except mysql.connector.Error as e:
        logging.error(f"Error initializing DB pool: {e}")
        db_pool = None

initialize_pool()

def get_db_connection():
    global db_pool
    if not db_pool:
        logging.error("DB pool not initialized. Initializing now...")
        initialize_pool()
    try:
        conn = db_pool.get_connection()
        logging.debug(f"DB Config: {db_config}")
        logging.debug(f"Connection object: {conn}")
        if not conn:
            logging.error("Received None connection from the pool!")
            raise mysql.connector.PoolError("Received None connection from the pool!")
        return conn
    except mysql.connector.Error as e:
        logging.error(f"Error while trying to get a connection: {e}")
        raise

def retry_on_db_fail(max_retries=5, delay=2):
    """A decorator to retry a function if it fails due to database connection issues."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            for _ in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (mysql.connector.PoolError, AttributeError) as e: 
                    if 'queue is full' in str(e) or 'NoneType' in str(e): 
                        logging.warning(f"DB Pool Error: {e}. Retrying in {delay} seconds...")
                        time.sleep(delay)
                    else:
                        raise  
            logging.error(f"Failed to get a DB connection after {max_retries} attempts.")
            raise mysql.connector.PoolError("Max retries reached for database connection.")
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
                        cur.execute("INSERT IGNORE INTO wallets (address) VALUES (%s)", (wallet_address,))
    finally:
        conn.close()
                        

@retry_on_db_fail()
def address_exists_in_db(address):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM wallets WHERE address = %s", (address,))
            exists = cur.fetchone()
            return exists is not None
    finally:
        conn.close()

@retry_on_db_fail()
def create_tables():
    """Create necessary tables in the MySQL database."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('''
            CREATE TABLE IF NOT EXISTS progress (
                id INT AUTO_INCREMENT PRIMARY KEY,
                instance INT NOT NULL,
                value BIGINT NOT NULL
            );
            ''')

            cur.execute('''
            CREATE TABLE IF NOT EXISTS wallet_database (
                id INT AUTO_INCREMENT PRIMARY KEY,
                wif TEXT NOT NULL,
                address TEXT NOT NULL,
                balance REAL NOT NULL
            );
            ''')

            cur.execute('''
            CREATE TABLE IF NOT EXISTS hash_rates (
                id INT AUTO_INCREMENT PRIMARY KEY,
                instance INT NOT NULL,
                hash_rate REAL NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            ''')

            cur.execute("SHOW COLUMNS FROM progress LIKE 'updated_at'")
            if not cur.fetchone():
                cur.execute('''
                ALTER TABLE progress ADD COLUMN updated_at DATE DEFAULT CURRENT_DATE
                ''')
            
            conn.commit()
    finally:
        conn.close()

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
    """Save progress to the MySQL database."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            try:
                cur.execute("""
                INSERT INTO progress (instance, value)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE value = %s;
                """, (instance, value, value))
                conn.commit()
            except mysql.connector.Error as e:
                logging.error(f"Database error: {e}")
    finally:
        conn.close()

@retry_on_db_fail()
def load_progress(instance):
    """Load progress from the MySQL database."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            try:
                cur.execute("SELECT value FROM progress WHERE instance = %s", (instance,))
                result = cur.fetchone()
                return result[0] if result else None
            except mysql.connector.Error as e:
                logging.error(f"Database error: {e}")
                return None
    finally:
        conn.close()

@retry_on_db_fail()
def save_to_wallet_database(wif, address, balance):
    """Save wallet details to file."""
    conn = get_db_connection()
    try:
        with open('wallet_database.txt', 'a') as wallet_db:
            wallet_db.write(f'{wif},{address},{balance}\n')
    finally:
        conn.close()
    try:
        with conn.cursor() as cur:
            try:
                cur.execute("""
                INSERT INTO wallet_database (wif, address, balance)
                VALUES (%s, %s, %s);
                """, (wif, address, balance))
                conn.commit()
            except mysql.connector.Error as e:
                logging.error(f"Database error during wallet insertion: {e}")
    finally:
        conn.close()

@retry_on_db_fail()         
def insert_hash_rate(instance, hash_rate):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            try:
                cur.execute("INSERT INTO hash_rates (instance, hash_rate) VALUES (%s, %s)", (instance, hash_rate))
                conn.commit()
            except mysql.connector.Error as e:
                logging.error(f"Database error while inserting hash rate: {e}")
    finally:
        conn.close()
                
@retry_on_db_fail()
def get_total_addresses():
    """Return total number of addresses processed."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM progress")
        result = cur.fetchone()
        return result[0] if result else 0
    finally:
        cur.close()
        conn.close()

@retry_on_db_fail()
def get_total_found_addresses():
    """Return total number of found addresses."""
    conn = get_db_connection()  
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM wallet_database")
        result = cur.fetchone()
        cur.close()
        return result[0] if result else 0
    finally:
        conn.close()

@retry_on_db_fail()
def get_total_addresses_by_day():
    """Return total number of addresses processed by day."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT DATE(updated_at) as updated_day, SUM(value) 
            FROM progress 
            GROUP BY DATE(updated_at)
            ORDER BY DATE(updated_at) DESC
        """)
        result = cur.fetchall()
        return [{"date": row[0].strftime('%Y-%m-%d'), "count": row[1]} for row in result]
    except Exception as e:
        raise
    finally:
        cur.close()
        conn.close()

@retry_on_db_fail()
def get_total_addresses_to_bruteforce():
    """Return total number of addresses to be bruteforced."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM wallets") 
        result = cur.fetchone()
        return result[0] if result else 0
    finally:
        cur.close()
        conn.close()
