from db_manager import address_exists_in_db, save_to_wallet_database, save_progress, load_progress, insert_hash_rate
from notification_manager import send_slack_message
import requests
from time import sleep, time
from bit import Key
import os

webhook_url = os.getenv("SLACK_WEBHOOK_URL")

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
            insert_hash_rate(r + 1, hash_rate_last_30min)
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