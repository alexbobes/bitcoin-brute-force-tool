from bit import Key
from multiprocessing import cpu_count
from requests import get
from time import time, sleep
import time as time_module
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
import requests
import json
import sqlite3
import os

load_dotenv()

webhook_url = os.getenv("SLACK_WEBHOOK_URL")

def create_tables(conn):
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS progress
                   (id INTEGER PRIMARY KEY, instance INTEGER, value INTEGER)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS wallet_database
                   (id INTEGER PRIMARY KEY, wif TEXT, address TEXT, balance REAL)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS hash_rates
                   (id INTEGER PRIMARY KEY, instance INTEGER, hash_rate REAL, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()


def send_slack_message(url, message, max_retries=30, retry_interval=5):
    if not url or url == "None":
        print("Slack webhook URL not set. Skipping sending message.")
        return

    headers = {'Content-Type': 'application/json'}
    data = json.dumps({'text': message})

    for retry in range(max_retries):
        try:
            response = requests.post(url, headers=headers, data=data)
            response.raise_for_status()
            break  # If successful, break the loop
        except requests.exceptions.RequestException as e:
            print(f"Error: {e}")  # Add this line to print the exception message
            if retry < max_retries - 1:
                print(f"Failed to send Slack message. Retrying in {retry_interval} seconds... ({retry + 1}/{max_retries})")
                time_module.sleep(retry_interval)
            else:
                print(f"Failed to send Slack message after {max_retries} attempts. Skipping...")
           

send_slack_message(webhook_url, "Bitcoin Script started >")

with open('wallets.txt', 'r') as file:
    wallets = set(file.read().split('\n'))
    if '' in wallets:
        wallets.remove('')

max_p = 115792089237316195423570985008687907852837564279074904382605163141518161494336

def save_progress(instance, value):
    conn = sqlite3.connect("progress.db")
    cursor = conn.cursor()

    cursor.execute("""
    INSERT OR REPLACE INTO progress (instance, value) VALUES (?, ?);
    """, (instance, value))

    conn.commit()
    conn.close()

def load_progress(instance):
    conn = sqlite3.connect("progress.db")
    cursor = conn.cursor()

    cursor.execute("SELECT value FROM progress WHERE instance = ?", (instance,))

    result = cursor.fetchone()

    conn.close()

    return result[0] if result else None


def save_to_wallet_database(wif, address, balance):
    with open('wallet_database.txt', 'a') as wallet_db:
        wallet_db.write(f'{wif},{address},{balance}\n')

def bruteforce_template(r, sep_p, func, debug=False):
    keys_processed = 0
    sint = load_progress(r) or (sep_p * r if sep_p * r != 0 else 1)
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
        if pk.address in wallets:
            print(f'Instance: {r + 1} - Found: {pk.address}')
            with open('found.txt', 'a') as result:
                result.write(f'{pk.to_wif()}\n')
            save_to_wallet_database(pk.to_wif(), pk.address, 0)
        sint += 1
        save_progress(r, sint)
        keys_processed += 1
        keys_generated += 1
        current_time = time()
        elapsed_time_since_update = current_time - last_update
        if elapsed_time_since_update >= 1800:  # Check every 30 minutes
            addresses_checked_last_30min = keys_generated - last_30min_keys_generated
            last_30min_keys_generated = keys_generated
            total_elapsed_time = current_time - start_time
            hash_rate_last_30min = addresses_checked_last_30min / elapsed_time_since_update
            conn = sqlite3.connect('progress.db')
            cur = conn.cursor()
            cur.execute("INSERT INTO hash_rates (instance, hash_rate) VALUES (?, ?)", (r + 1, hash_rate_last_30min))
            conn.commit()
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

# OBF remains unchanged
def OBF():
    print('Instance: 1 - Generating random addresses...')
    while True:
        pk = Key()
        print(f'Instance: 1 - Generated: {pk.address} wif: {pk.to_wif()}')
        print('Instance: 1 - Checking balance...')
        try:
            balance = int(get(f'https://blockchain.info/q/addressbalance/{pk.address}/').text)
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


def main():
    conn = sqlite3.connect('progress.db')
    create_tables(conn)
    mode = (None, RBF, TBF, OTBF, OBF, debug_RBF, debug_TBF, debug_OTBF)

    menu_string = 'Select bruteforce mode:\n'
    for count, function in enumerate(mode):
        try:
            if 'debug' in function.__name__:
                menu_string += f'{count} - {function.__name__} (Prints output)\n'
            else:
                menu_string += f'{count} - {function.__name__}\n'
        except AttributeError:
            menu_string += f'{count} - Exit\n'
    print(menu_string)

    try:
        choice = int(input('> '))
        if choice == 4:
            option = 4
            cpu_cores = 1
        elif choice != 0:
            print(f'How many cores do you want to use ({cpu_count()} available)')
            cpu_cores = int(input('> '))
            cpu_cores = cpu_cores if 0 < cpu_cores < cpu_count() else cpu_count()
            option = choice if 0 < choice <= len(mode) - 1 else 0
        else:
            option = 0
            cpu_cores = 0
    except ValueError:
        option = 0
        cpu_cores = 0

    if mode[option] and mode[option].__name__ != 'OBF':
        print(f'Starting bruteforce instances in mode: {mode[option].__name__} with {cpu_cores} core(s)\n')
        # print(f'Wallets: {wallets}')

        with ThreadPoolExecutor(max_workers=cpu_cores) as executor:
            futures = [executor.submit(mode[option], i, round(max_p / cpu_cores)) for i in range(cpu_cores)]
            for future in futures:
                future.result()

    elif mode[option].__name__ == 'OBF':
        print(f'Starting bruteforce in mode: {mode[option].__name__} (6 per minute to respect API rate limit)\n')
        OBF()

    print('Stopping...')

if __name__ == '__main__':
    main()
