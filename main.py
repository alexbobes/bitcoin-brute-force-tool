import logging
from bruteforcer import RBF, TBF, OTBF, OBF, debug_RBF, debug_TBF, debug_OTBF
from db_manager import test_address_insertion
from multiprocessing import cpu_count
from concurrent.futures import ProcessPoolExecutor

mode = [None, RBF, TBF, OTBF, OBF, debug_RBF, debug_TBF, debug_OTBF, test_address_insertion]
max_p = 115792089237316195423570985008687907852837564279074904382605163141518161494336

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

def main():
    print_menu()
    choice = get_user_choice()

    if choice == len(mode) - 1:
        test_address_insertion()
        return
    option = choice

    if option == 4:  # If user chose OBF
        cpu_cores = 1
    elif 0 < option < len(mode) - 1:  # If user chose any other bruteforce mode
        print(f'How many cores do you want to use ({cpu_count()} available)?')
        try:
            cpu_cores = int(input('> '))
            if 0 < cpu_cores <= cpu_count():
                pass
            else:
                print(f"Selected number of cores ({cpu_cores}) is out of range. Using all available cores.")
                cpu_cores = cpu_count()
        except ValueError:
            print("Invalid input. Not a valid integer. Using all available cores.")
            cpu_cores = cpu_count()
    else:  # For 'Exit' or any other unexpected input
        option = 0
        cpu_cores = 0

    if mode[option] and mode[option].__name__ != 'OBF':
        print(f"Executing {mode[option].__name__} with {cpu_cores} cores.")
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
    try:
        main()
    except Exception as e:
        logging.error(f"Error: {e}")
    finally:
        # Cleanup code, if any. For example, close DB connections or any open files.
        pass
