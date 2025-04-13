#!/usr/bin/env python3
"""
Main entry point for Bitcoin Brute Force Tool.
Provides a command-line interface to select and run different brute force modes.
"""

import logging
from multiprocessing import cpu_count
from concurrent.futures import ProcessPoolExecutor

# Import from project modules
from src.core.bruteforcer import RBF, TBF, OTBF, OBF, debug_RBF, debug_TBF, debug_OTBF
from src.database.db_manager import test_address_insertion, create_tables, get_total_addresses_to_bruteforce

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Define all available modes with descriptions
MODE_DESCRIPTIONS = {
    'Exit': 'Exit the program',
    'RBF': 'Random Brute Force - Generate completely random Bitcoin addresses',
    'TBF': 'Traditional Brute Force - Sequential generation of Bitcoin addresses using integers',
    'OTBF': 'Offset Traditional Brute Force - Sequential generation starting from a large offset (10^75)',
    'OBF': 'Online Brute Force - Generate random addresses and check balances via Blockchain.info API',
    'debug_RBF': 'Debug: Random Brute Force with verbose output',
    'debug_TBF': 'Debug: Traditional Brute Force with verbose output',
    'debug_OTBF': 'Debug: Offset Traditional Brute Force with verbose output',
    'test_address_insertion': 'Test database connection by inserting a test address'
}

# Configure modes
mode = [None, RBF, TBF, OTBF, OBF, debug_RBF, debug_TBF, debug_OTBF, test_address_insertion]
# Maximum value for Bitcoin private keys (SECP256k1 curve order - 1)
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
    """Print the menu options with detailed descriptions."""
    # Get total addresses in database for information
    try:
        target_count = get_total_addresses_to_bruteforce()
        print(f"\n===== BITCOIN BRUTE FORCE TOOL =====")
        print(f"Target addresses in database: {target_count:,}")
        print(f"===================================\n")
    except Exception as e:
        print("\n===== BITCOIN BRUTE FORCE TOOL =====\n")
        logging.warning(f"Could not retrieve address count: {e}")
    
    print('Select a brute force mode or test option:\n')
    
    # Print each mode with description
    for count, function in enumerate(mode):
        if function:
            name = function.__name__
            description = MODE_DESCRIPTIONS.get(name, "No description available")
            print(f'{count} - {name}: {description}')
        else:
            print(f'{count} - Exit: Exit the program')
    
    # Print additional help information
    print("\nMode explanations:")
    print("- Random (RBF): Each instance generates completely random Bitcoin private keys")
    print("- Traditional (TBF): Systematically generates keys from integers in a defined range")
    print("- Offset (OTBF): Like TBF but starts from an extremely large number (10^75)")
    print("- Online (OBF): Generates random keys and checks live balance (API limited)")
    print("- Debug modes: Same as above but with verbose output for testing")
    
    print("\nPerformance note: Optimized batch processing is enabled for all modes")

def main():
    # Ensure database tables exist
    create_tables()
    
    # Display menu with descriptions
    print_menu()
    
    # Get user choice
    choice = get_user_choice()
    
    # Exit if chosen
    if choice == 0:
        print("Exiting program. Goodbye!")
        return
        
    option = choice
    
    # Test address insertion and return
    if option == len(mode) - 1:
        print("\nRunning database test...\n")
        test_address_insertion()
        return
    
    # Determine CPU cores to use
    if option == 4:  # OBF mode uses only 1 core due to API limits
        cpu_cores = 1
        print("\nOnline Brute Force (OBF) mode uses 1 core to respect API rate limits")
    elif 0 < option < len(mode) - 1:
        available_cores = cpu_count()
        
        print(f"\nHow many CPU cores do you want to use? ({available_cores} available)")
        print(f"More cores = faster processing, but higher system load")
        print(f"Recommended: Use {max(1, available_cores - 1)} cores to keep system responsive")
        
        try:
            cpu_cores = int(input('> '))
            if 0 < cpu_cores <= available_cores:
                pass
            else:
                print(f"\nSelected number of cores ({cpu_cores}) is out of range.")
                print(f"Using {available_cores} cores instead.")
                cpu_cores = available_cores
        except ValueError:
            print("\nInvalid input. Not a valid integer.")
            print(f"Using {available_cores} cores instead.")
            cpu_cores = available_cores
    else: 
        option = 0
        cpu_cores = 0
    
    # Run the selected mode
    mode_name = mode[option].__name__
    if mode[option] and mode_name != 'OBF':
        # For all non-OBF modes, use parallel processing
        print(f"\nExecuting {mode_name} with {cpu_cores} cores.")
        print(f"This mode will check generated addresses against your loaded database.")
        print(f"Press Ctrl+C to stop at any time.\n")
        
        logging.info(f'Starting bruteforce instances in mode: {mode_name} with {cpu_cores} core(s)\n')
        try:
            with ProcessPoolExecutor(max_workers=cpu_cores) as executor:
                # Convert to string to handle extremely large numbers correctly
                # This prevents overflow issues with very large key ranges
                max_p_str = str(max_p)
                key_range_per_core = int(int(max_p_str) / cpu_cores)
                
                # Submit tasks to process pool - pass total cores count for statistics
                futures = [executor.submit(mode[option], i, key_range_per_core, cpu_cores) for i in range(cpu_cores)]
                
                # Wait for all tasks to complete
                for future in futures:
                    future.result()
        except KeyboardInterrupt:
            print("\nBrute force operation interrupted by user. Shutting down...")
            
    elif mode_name == 'OBF':
        # For OBF mode, use API with rate limiting
        print("\nStarting Online Brute Force (OBF) mode.")
        print("This mode checks random addresses directly against the blockchain.")
        print("Rate limited to ~6 addresses per minute to respect API limits.")
        print("Press Ctrl+C to stop at any time.\n")
        
        logging.info(f'Starting bruteforce in mode: {mode_name} (6 per minute to respect API rate limit)\n')
        try:
            OBF()
        except KeyboardInterrupt:
            print("\nOnline brute force operation interrupted by user. Shutting down...")
    
    logging.info('Stopping...')
    print("\nOperation complete. To run again, restart the program.")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logging.error(f"Error: {e}", exc_info=True)