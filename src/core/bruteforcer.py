"""
Core bruteforce functionality for Bitcoin address generation.
Provides various methods to generate and check Bitcoin addresses.
"""

import os
import logging
import requests
import multiprocessing
import threading
from queue import Queue
from time import sleep, time
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from dotenv import load_dotenv
from bit import Key

# Import from project modules
from src.database.db_manager import (
    address_exists_in_db, check_addresses_batch, save_to_wallet_database, 
    batch_save_to_wallet_database, save_progress, load_progress, insert_hash_rate,
    update_daily_stats, initialize_session_tracking, finalize_session_tracking
)
from src.notifications.notification_manager import send_slack_message
from src.notifications.telegram_notifier import (
    send_stats_update, send_found_address_alert, is_telegram_configured
)

# Load environment variables
load_dotenv()

# Notification configurations
webhook_url = os.getenv("SLACK_WEBHOOK_URL")
telegram_enabled = is_telegram_configured()
telegram_interval = int(os.getenv("TELEGRAM_STATS_INTERVAL", "15"))  # Default to 15 minutes

# Constants for optimization
BATCH_SIZE = 1000  # Number of addresses to generate before checking against DB
PROGRESS_INTERVAL = 10000  # How often to save progress to DB
STATUS_INTERVAL = 60  # How often to output status logs in seconds
# Number of threads to use for parallel address generation (per process)
NUM_THREADS = min(32, multiprocessing.cpu_count() * 2)  # Use 2x CPU cores or max 32


def generate_keys_batch(func, start, batch_size):
    """
    Generate a batch of keys using the provided function.
    Returns a list of (index, key) tuples.
    """
    result = []
    for i in range(start, start + batch_size):
        key = func(i)
        result.append((i, key))
    return result

def bruteforce_template(r, sep_p, func, debug=False, mode_name=None, total_cores=1):
    # Get function name if mode_name not provided
    if mode_name is None:
        import inspect
        # Get the caller's name (RBF, TBF, etc.)
        frame = inspect.currentframe().f_back
        mode_name = frame.f_code.co_name
    
    # Simple session tracking initialization
    session_id = None
    try:
        session_id = initialize_session_tracking()
        if session_id:
            logging.info(f"Session tracking active with ID: {session_id}")
        else:
            logging.warning("Failed to initialize session tracking, continuing without it")
    except Exception as e:
        logging.error(f"Error initializing session tracking: {e}")
        # Continue anyway, session tracking is non-critical
    
    instance_id = r + 1
    keys_processed = 0
    sint = int(load_progress(r) or (sep_p * r if sep_p * r != 0 else 1))
    mint = sep_p * (r + 1)
    print(f'Instance: {instance_id} - Generating addresses...')
    
    keys_generated = 0
    start_time = time()
    last_update = start_time
    last_status_update = start_time
    last_telegram_update = start_time
    last_30min_keys_generated = 0
    
    # Store found addresses for reporting
    found_addresses = []
    
    # To store batch of generated addresses
    batch_addresses = []
    batch_keys = []
    
    while sint < mint:
        # Generate addresses in batches
        batch_end = min(sint + BATCH_SIZE, mint)
        batch_size = batch_end - sint
        
        # Clear previous batch
        batch_addresses = []
        batch_keys = []
        
        # Prepare for parallel generation
        if batch_size > 100:  # Only use parallel processing for larger batches
            # Split the batch into smaller chunks for parallel processing
            chunk_size = batch_size // NUM_THREADS
            if chunk_size == 0:
                chunk_size = 1
                
            # Create a partial function with the key generation function
            gen_func = partial(generate_keys_batch, func)
            
            # Create chunks for parallel processing
            chunks = [(sint + i * chunk_size, min(chunk_size, batch_end - (sint + i * chunk_size))) 
                      for i in range(NUM_THREADS)]
            
            # Generate keys in parallel using ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
                results = list(executor.map(lambda args: gen_func(*args), chunks))
                
            # Flatten results
            key_tuples = []
            for chunk in results:
                key_tuples.extend(chunk)
                
            # Sort by index to maintain order
            key_tuples.sort(key=lambda x: x[0])
            
            # Extract keys
            for _, pk in key_tuples:
                batch_addresses.append(pk.address)
                batch_keys.append(pk)
                
                if debug and len(batch_addresses) <= 10:  # Limit debug output
                    print(f'Instance: {r + 1} - Generated: {pk.address}')
        else:
            # For small batches, use simple loop
            for i in range(sint, batch_end):
                pk = func(i)
                batch_addresses.append(pk.address)
                batch_keys.append(pk)
                
                if debug and len(batch_addresses) <= 10:  # Limit debug output
                    print(f'Instance: {r + 1} - Generated: {pk.address}')
        
        # Check all addresses in batch against database in one query
        found_addresses = check_addresses_batch(batch_addresses)
        
        # Process found addresses
        if found_addresses:
            # Create data for batch save
            wallet_data = []
            # Keep track of found addresses for reporting
            newly_found = []
            
            # Open found.txt for appending all at once
            with open('found.txt', 'a') as result:
                for address in found_addresses:
                    idx = batch_addresses.index(address)
                    pk = batch_keys[idx]
                    wif = pk.to_wif()
                    
                    print(f'Instance: {instance_id} - Found: {address}')
                    
                    # Record for reporting
                    newly_found.append(address)
                    
                    # Send notifications
                    if webhook_url:
                        send_slack_message(webhook_url, f'Instance: {instance_id} - Found address: {address}')
                    
                    # Send Telegram alert
                    if telegram_enabled:
                        send_found_address_alert(address, wif=wif, balance=0)
                    
                    # Save to found.txt
                    result.write(f'{wif}\n')
                    
                    # Add to batch for database
                    wallet_data.append((wif, address, 0))
            
            # Save all found addresses in one batch
            if wallet_data:
                batch_save_to_wallet_database(wallet_data)
                
            # Add the newly found addresses to the tracked list for reporting
            found_addresses.extend(newly_found)
                
        # Update counters
        sint = batch_end
        keys_processed += len(batch_addresses)
        keys_generated += len(batch_addresses)
        
        # Save progress periodically - but be careful with very large numbers
        if keys_processed % PROGRESS_INTERVAL == 0:
            # Explicitly convert to string to handle huge integers safely
            save_progress(r, str(sint))
        
        # Status update
        current_time = time()
        elapsed_time = current_time - start_time
        elapsed_time_since_update = current_time - last_update
        elapsed_time_since_telegram = current_time - last_telegram_update
        
        # Status logging at regular intervals
        if current_time - last_status_update >= STATUS_INTERVAL:
            rate = keys_generated / max(1, elapsed_time)
            print(f'Instance: {instance_id} - Processed: {keys_generated:,} addresses, Rate: {rate:.2f} keys/sec')
            last_status_update = current_time
        
        # Telegram stats updates at configured interval
        if telegram_enabled and elapsed_time_since_telegram >= (telegram_interval * 60):
            rate = keys_generated / max(1, elapsed_time)
            
            # Make sure the Telegram module gets refreshed information
            updated_telegram_enabled = is_telegram_configured()
            
            if updated_telegram_enabled:
                # Prepare stats data for Telegram
                stats = {
                    "mode": mode_name,
                    "instance": instance_id,
                    "cores": total_cores,
                    "addresses_checked": keys_generated,
                    "elapsed_time": elapsed_time,
                    "rate": rate,
                    "found_addresses": found_addresses[-5:] if found_addresses else []  # Send the 5 most recent finds
                }
                
                # Send Telegram update with debug info
                logging.info(f"Sending Telegram stats update from instance {instance_id}")
                try:
                    success = send_stats_update(stats)
                    if success:
                        logging.info("Telegram stats update sent successfully")
                    else:
                        logging.warning("Failed to send Telegram stats update")
                except Exception as e:
                    logging.error(f"Error sending Telegram stats: {e}", exc_info=True)
            else:
                logging.warning("Telegram not properly configured, skipping notification")
            
            last_telegram_update = current_time
            
        # Performance metrics and Slack notification every 30 minutes
        if elapsed_time_since_update >= 1800: 
            addresses_checked_last_30min = keys_generated - last_30min_keys_generated
            last_30min_keys_generated = keys_generated
            hash_rate_last_30min = addresses_checked_last_30min / elapsed_time_since_update
            insert_hash_rate(instance_id, hash_rate_last_30min)
            
            # Simple and non-blocking update call
            try:
                update_daily_stats()
            except Exception as e:
                logging.error(f"Error updating daily stats: {e}")
                # Continue processing regardless of errors
                
            last_update = current_time
            
            # Only send Slack message if webhook is configured
            if webhook_url:
                message = (f'Instance: {instance_id} - Checked {addresses_checked_last_30min:,} addresses in the past 30 minutes.\n'
                          f'Instance: {instance_id} - Checked {keys_generated:,} addresses in total.\n'
                          f'Instance: {instance_id} - Hash rate (last 30 minutes): {hash_rate_last_30min:.2f} keys/sec.\n')
                send_slack_message(webhook_url, message)

    # Simple session finalization
    if session_id:
        try:
            finalize_session_tracking(session_id)
            logging.info(f"Session {session_id} completed")
        except Exception as e:
            logging.error(f"Error finalizing session: {e}")

    print(f'Instance: {r + 1}  - Done')

def RBF(r, sep_p, total_cores=1):
    bruteforce_template(r, sep_p, lambda _: Key(), mode_name="RBF", total_cores=total_cores)

def TBF(r, sep_p, total_cores=1):
    bruteforce_template(r, sep_p, Key.from_int, mode_name="TBF", total_cores=total_cores)

def OTBF(r, sep_p, total_cores=1):
    bruteforce_template(r, sep_p, lambda sint: Key.from_int(sint + 10 ** 75), mode_name="OTBF", total_cores=total_cores)

def debug_RBF(r, sep_p, total_cores=1):
    bruteforce_template(r, sep_p, lambda _: Key(), debug=True, mode_name="debug_RBF", total_cores=total_cores)

def debug_TBF(r, sep_p, total_cores=1):
    bruteforce_template(r, sep_p, Key.from_int, debug=True, mode_name="debug_TBF", total_cores=total_cores)

def debug_OTBF(r, sep_p, total_cores=1):
    bruteforce_template(r, sep_p, lambda sint: Key.from_int(sint + 10 ** 75), debug=True, mode_name="debug_OTBF", total_cores=total_cores)

def OBF():
    print('Instance: 1 - Generating random addresses...')
    
    # Tracking variables
    start_time = time()
    last_status_update = start_time
    last_telegram_update = start_time
    addresses_checked = 0
    found_addresses = []
    
    while True:
        pk = Key()
        address = pk.address
        wif = pk.to_wif()
        
        print(f'Instance: 1 - Generated: {address} wif: {wif}')
        print('Instance: 1 - Checking balance...')
        
        try:
            # Add SSL handling and headers for more reliable connections
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            # Use a session with more control over SSL settings
            session = requests.Session()
            # Set a longer timeout for slow connections
            response = session.get(
                f'https://blockchain.info/q/addressbalance/{address}/',
                headers=headers,
                timeout=30,
                verify=True  # Enable SSL verification
            )
            
            # Close the session to free resources
            session.close()
            
            # Parse the balance
            balance = int(response.text)
        except ValueError:
            print(f'Instance: 1 - Error reading balance from: {address}')
            continue
        except requests.exceptions.SSLError as e:
            print(f'Instance: 1 - SSL Error checking balance: {e}')
            print('This is likely due to an SSL configuration issue. Trying alternative API...')
            
            try:
                # Try an alternative API with different SSL requirements
                alt_response = requests.get(
                    f'https://api.blockcypher.com/v1/btc/main/addrs/{address}/balance',
                    headers=headers,
                    timeout=30
                )
                balance = alt_response.json().get('final_balance', 0)
            except Exception as alt_e:
                print(f'Instance: 1 - Error with alternative API: {alt_e}')
                print('Sleeping for 30 seconds before retrying...')
                sleep(30)
                continue
        except Exception as e:
            print(f'Instance: 1 - Error checking balance: {e}')
            print('Sleeping for 30 seconds before retrying...')
            sleep(30)
            continue

        addresses_checked += 1
        print(f'Instance: 1 - {address} has balance: {balance}')
        
        # If balance is found, record it
        if balance > 0:
            with open('found.txt', 'a') as result:
                result.write(f'{wif}\n')
            save_to_wallet_database(wif, address, balance)
            print(f'Instance: 1 - Added address to found.txt and wallet_database.txt')
            
            # Record for reporting
            found_addresses.append(address)
            
            # Send notifications
            if webhook_url:
                message = f'Instance: 1 - Found address with a balance: {address}'
                send_slack_message(webhook_url, message)
                
            if telegram_enabled:
                send_found_address_alert(address, wif=wif, balance=balance)
                
        # Status updates
        current_time = time()
        elapsed_time = current_time - start_time
        
        # Status logging every minute
        if current_time - last_status_update >= 60:
            rate = addresses_checked / elapsed_time
            print(f'Instance: 1 - Checked {addresses_checked} addresses, Rate: {rate:.4f} keys/sec')
            last_status_update = current_time
            
        # Telegram updates
        if telegram_enabled and current_time - last_telegram_update >= (telegram_interval * 60):
            # Prepare stats for Telegram
            stats = {
                "mode": "OBF (Online)",
                "instance": 1,
                "cores": 1,
                "addresses_checked": addresses_checked,
                "elapsed_time": elapsed_time,
                "rate": addresses_checked / elapsed_time,
                "found_addresses": found_addresses[-5:] if found_addresses else []
            }
            
            # Send update
            try:
                send_stats_update(stats)
            except Exception as e:
                logging.error(f"Error sending Telegram stats: {e}")
                
            last_telegram_update = current_time
            
        print('Sleeping for 10 seconds...')
        sleep(10)