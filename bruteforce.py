from bit import Key
from multiprocessing import cpu_count
from requests import get
from time import sleep, time
from concurrent.futures import ThreadPoolExecutor

with open('wallets.txt', 'r') as file:
    wallets = set(file.read().split('\n'))
    if '' in wallets:
        wallets.remove('')

max_p = 115792089237316195423570985008687907852837564279074904382605163141518161494336

def save_progress(instance, value):
    with open(f'progress_{instance}.txt', 'w') as progress_file:
        progress_file.write(str(value))

def load_progress(instance):
    try:
        with open(f'progress_{instance}.txt', 'r') as progress_file:
            progress_value = progress_file.read().strip()
            return int(progress_value) if progress_value else None
    except (FileNotFoundError, ValueError):
        return Nonegit 


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
        if elapsed_time_since_update >= 60:
            total_elapsed_time = current_time - start_time
            hash_rate = keys_generated / total_elapsed_time
            with open(f'hash_rate_{r}.txt', 'w') as hash_rate_file:
                hash_rate_file.write(f'Instance: {r + 1} - Hash rate: {hash_rate:.2f} keys/s\n')
            last_update = current_time

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
        print('Sleeping for 10 seconds...')
        sleep(10)


def main():
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
