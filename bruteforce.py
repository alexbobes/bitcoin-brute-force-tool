import json
import os
import logging
from time import sleep, time
from bit import Key
from concurrent.futures import ProcessPoolExecutor
from dotenv import load_dotenv
from multiprocessing import cpu_count
import requests
import mysql.connector

load_dotenv()
logging.basicConfig(level=logging.INFO)

webhook_url = os.getenv("SLACK_WEBHOOK_URL")
max_p = 115792089237316195423570985008687907852837564279074904382605163141518161494336

def store_wallets_in_db():
    with mysql.connector.connect(
        host="localhost",
        user="root",
        password="root",
        database="bitcoin_db",
        buffered=True
    ) as conn:
        with conn.cursor() as cur:
            with open('wallets.txt', 'r') as file:
                for line in file:
                    wallet_address = line.strip()
                    if wallet_address:
                        cur.execute("INSERT IGNORE INTO wallets (address) VALUES (%s)", (wallet_address,))
    
def address_exists_in_db(address):
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="root",
        database="bitcoin_db"
    )
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM wallets WHERE address = %s", (address,))
    exists = cur.fetchone()
    cur.close()
    conn.close()
    return exists is not None

def create_tables():
    """Create necessary tables in the MySQL database."""
    with mysql.connector.connect(
        host="localhost",
        user="root",
        password="root",
        database="bitcoin_db",
        buffered=True
    ) as conn:
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
            conn.commit()

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

def send_slack_message(url, message, max_retries=30, retry_interval=5):
    if not url:
        logging.info("Slack webhook URL not set. Skipping sending message.")
        return

    headers = {'Content-Type': 'application/json'}
    data = json.dumps({'text': message})

    for retry in range(max_retries):
        try:
            response = requests.post(url, headers=headers, data=data)
            response.raise_for_status()
            break  
        except requests.exceptions.RequestException as e:
            logging.error(f"Error: {e}")
            if retry < max_retries - 1:
                logging.info(f"Failed to send Slack message. Retrying in {retry_interval} seconds... ({retry + 1}/{max_retries})")
                sleep(retry_interval)
            else:
                logging.info(f"Failed to send Slack message after {max_retries} attempts. Skipping...")

def save_progress(instance, value):
    """Save progress to the MySQL database."""
    with mysql.connector.connect(
        host="localhost",
        user="root",
        password="root",
        database="bitcoin_db",
        buffered=True
    ) as conn:
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

def load_progress(instance):
    """Load progress from the MySQL database."""
    with mysql.connector.connect(
        host="localhost",
        user="root",
        password="root",
        database="bitcoin_db",
        buffered=True
    ) as conn:
        with conn.cursor() as cur:
            try:
                cur.execute("SELECT value FROM progress WHERE instance = %s", (instance,))
                result = cur.fetchone()
                return result[0] if result else None
            except mysql.connector.Error as e:
                logging.error(f"Database error: {e}")
                return None

def save_to_wallet_database(wif, address, balance):
    """Save wallet details to file."""
    with open('wallet_database.txt', 'a') as wallet_db:
        wallet_db.write(f'{wif},{address},{balance}\n')
    with mysql.connector.connect(
        host="localhost",
        user="root",
        password="root",
        database="bitcoin_db",
        buffered=True
    ) as conn:
        with conn.cursor() as cur:
            try:
                cur.execute("""
                INSERT INTO wallet_database (wif, address, balance)
                VALUES (%s, %s, %s);
                """, (wif, address, balance))
                conn.commit()
            except mysql.connector.Error as e:
                logging.error(f"Database error during wallet insertion: {e}")

def bruteforce_template(r, sep_p, func, debug=False):
    keys_processed = 0
    sint = int(load_progress(r) or (sep_p * r if sep_p * r != 0 else 1))
    mint = sep_p * (r + 1)
    print(f'Instance: {r + 1} - Generating addresses...')
    
    keys_generated = 0
    start_time = time()
    last_update = start_time
    last_30min_keys_generated = 0    
    
    while sint < mint:
        pk = func(sint)
        if debug:
            print(f'Instance: {r + 1} - Generated: {pk.address}')
        if address_exists_in_db(pk.address):
            print(f'Instance: {r + 1} - Found: {pk.address}')
            send_slack_message(webhook_url, f'Instance: {r + 1} - Found address: {pk.address}')
            with open('found.txt', 'a') as result:
                result.write(f'{pk.to_wif()}\n')
            save_to_wallet_database(pk.to_wif(), pk.address, 0)
        sint += 1
        save_progress(r, sint)
        keys_processed += 1
        keys_generated += 1
        current_time = time()
        elapsed_time_since_update = current_time - last_update
        if elapsed_time_since_update >= 1800: 
            addresses_checked_last_30min = keys_generated - last_30min_keys_generated
            last_30min_keys_generated = keys_generated
            hash_rate_last_30min = addresses_checked_last_30min / elapsed_time_since_update
            try:
                with mysql.connector.connect(
                    host="localhost",
                    user="root",
                    password="root",
                    database="bitcoin_db",
                    buffered=True
                ) as conn:
                    with conn.cursor() as cur:
                        cur.execute("INSERT INTO hash_rates (instance, hash_rate) VALUES (%s, %s)", (r + 1, hash_rate_last_30min))
                    conn.commit()
            except mysql.connector.Error as e:
                logging.error(f"Database error while inserting hash rate: {e}")
            last_update = current_time
            message = (f'Instance: {r + 1} - Checked {addresses_checked_last_30min} addresses in the past 30 minutes.\n'
                       f'Instance: {r + 1} - Checked {keys_generated} addresses in total.\n'
                       f'Instance: {r + 1} - Hash rate (last 30 minutes): {hash_rate_last_30min:.2f} keys/sec.\n')
            send_slack_message(webhook_url, message)

    print(f'Instance: {r + 1}  - Done')

def RBF(r, sep_p):
    bruteforce_template(r, sep_p, lambda _: Key())

def TBF(r, sep_p):
    bruteforce_template(r, sep_p, Key.from_int)

def OTBF(r, sep_p):
    bruteforce_template(r, sep_p, lambda sint: Key.from_int(sint + 10 ** 75))

def debug_RBF(r, sep_p):
    bruteforce_template(r, sep_p, lambda _: Key(), debug=True)

def debug_TBF(r, sep_p):
    bruteforce_template(r, sep_p, Key.from_int, debug=True)

def debug_OTBF(r, sep_p):
    bruteforce_template(r, sep_p, lambda sint: Key.from_int(sint + 10 ** 75), debug=True)

def OBF():
    print('Instance: 1 - Generating random addresses...')
    while True:
        pk = Key()
        print(f'Instance: 1 - Generated: {pk.address} wif: {pk.to_wif()}')
        print('Instance: 1 - Checking balance...')
        try:
            balance = int(requests.get(f'https://blockchain.info/q/addressbalance/{pk.address}/').text)
        except ValueError:
            print(f'Instance: 1 - Error reading balance from: {pk.address}')
            continue

        print(f'Instance: 1 - {pk.address} has balance: {balance}')
        if balance > 0:
            with open('found.txt', 'a') as result:
                result.write(f'{pk.to_wif()}')
            save_to_wallet_database(pk.to_wif(), pk.address, balance)
            print(f'Instance: 1 - Added address to found.txt and wallet_database.txt')
            message = f'Instance: {r + 1} - Found address with a balance: {pk.address}'
            send_slack_message(webhook_url, message)
        print('Sleeping for 10 seconds...')
        sleep(10)

def get_user_choice():
    """Get user choice for the menu."""
    try:
        choice = int(input('> '))
        if 0 <= choice < len(mode):
            return choice
        else:
            logging.info("Invalid choice. Please try again.")
            return get_user_choice()
    except ValueError:
        logging.info("Please enter a valid number.")
        return get_user_choice()

def print_menu():
    """Print the menu options."""
    menu_string = 'Select bruteforce mode or test option:\n'
    for count, function in enumerate(mode):
        if function:
            menu_string += f'{count} - {function.__name__}\n'
        else:
            menu_string += f'{count} - Exit\n'
    print(menu_string)

mode = [None, RBF, TBF, OTBF, OBF, debug_RBF, debug_TBF, debug_OTBF, test_address_insertion]

def main():
    create_tables()
    print_menu()
    choice = get_user_choice()

    if choice == len(mode) - 1:
        test_address_insertion()
        return
    if choice == 4:
        option = 4
        cpu_cores = 1
    elif choice != 0:
        logging.info(f'How many cores do you want to use ({cpu_count()} available)')
        try:
            cpu_cores = int(input('> '))
            cpu_cores = cpu_cores if 0 < cpu_cores <= cpu_count() else cpu_count()
        except ValueError:
            logging.error("Invalid number of cores. Using all available cores.")
            cpu_cores = cpu_count()
        option = choice if 0 < choice <= len(mode) - 1 else 0
    else:
        option = 0
        cpu_cores = 0

    if mode[option] and mode[option].__name__ != 'OBF':
        logging.info(f'Starting bruteforce instances in mode: {mode[option].__name__} with {cpu_cores} core(s)\n')
        with ProcessPoolExecutor(max_workers=cpu_cores) as executor:
            futures = [executor.submit(mode[option], i, round(max_p / cpu_cores)) for i in range(cpu_cores)]
            for future in futures:
                future.result()
    elif mode[option].__name__ == 'OBF':
        logging.info(f'Starting bruteforce in mode: {mode[option].__name__} (6 per minute to respect API rate limit)\n')
        OBF()
    logging.info('Stopping...')


if __name__ == '__main__':
    # store_wallets_in_db()
    main()