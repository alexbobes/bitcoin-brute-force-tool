#!/usr/bin/env python3
"""
Telegram notification module for Bitcoin Brute Force Tool.
"""

import os
import logging
import requests
import sys
import json
from time import sleep
from dotenv import load_dotenv

# Set up logging more verbosely for this module
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Load environment variables
load_dotenv()

# Get Telegram configuration from environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Log startup information
logging.info("Telegram notifier module loaded")
logging.info(f"Bot token exists: {bool(TELEGRAM_BOT_TOKEN)}")
logging.info(f"Chat ID exists: {bool(TELEGRAM_CHAT_ID)}")
# More secure logging without revealing tokens
if TELEGRAM_BOT_TOKEN:
    logging.info(f"Telegram bot token is configured")
if TELEGRAM_CHAT_ID:
    logging.info(f"Telegram chat ID is configured: {TELEGRAM_CHAT_ID}")

def is_telegram_configured():
    """Check if Telegram integration is configured properly."""
    if not TELEGRAM_BOT_TOKEN:
        logging.warning("Telegram bot token is not configured")
        return False
    if not TELEGRAM_CHAT_ID:
        logging.warning("Telegram chat ID is not configured")
        return False
        
    # Both are configured
    logging.info(f"Telegram is properly configured with bot token and chat ID: {TELEGRAM_CHAT_ID}")
    return True

def send_telegram_message(message, max_retries=3):
    """
    Send a message to a Telegram chat.
    
    Args:
        message: The text message to send
        max_retries: Maximum number of retry attempts
        
    Returns:
        bool: True if message was sent successfully, False otherwise
    """
    global TELEGRAM_CHAT_ID  # Need to declare global here before use
    
    if not is_telegram_configured():
        logging.warning("Telegram notification failed: Bot token or chat ID not configured")
        return False
    
    # Try different formats for chat ID - this is often the issue
    chat_id_formats = [
        TELEGRAM_CHAT_ID,                                     # Original format
        str(TELEGRAM_CHAT_ID).replace('-', '-100'),           # Convert group ID to supergroup format
        str(TELEGRAM_CHAT_ID).replace('-100', '-'),           # Convert supergroup to normal group
        str(TELEGRAM_CHAT_ID).lstrip('-'),                    # Try positive ID
        f"-100{str(TELEGRAM_CHAT_ID).lstrip('-')}",           # Try supergroup format with positive ID
        f"-{str(TELEGRAM_CHAT_ID).lstrip('-')}"               # Try normal group with positive ID
    ]
    
    # Try all chat ID formats
    for chat_id in chat_id_formats:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",  # Enable HTML formatting
            "disable_web_page_preview": True
        }
        
        # Log the request details for debugging
        logging.info(f"Trying to send Telegram message to chat ID: {chat_id}")
        
        # Try sending with retries
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    url,
                    json=payload,
                    timeout=30
                )
                
                # Log the response
                logging.info(f"Telegram API response status: {response.status_code}")
                
                # Check if successful
                if response.status_code == 200:
                    logging.info(f"Telegram notification sent successfully to {chat_id}")
                    
                    # If this format worked but is different from configured, remember it
                    if chat_id != TELEGRAM_CHAT_ID:
                        logging.info(f"Working chat ID format found: {chat_id} (original was {TELEGRAM_CHAT_ID})")
                        
                        # Store the working chat ID for future use
                        TELEGRAM_CHAT_ID = chat_id
                        
                    return True
                else:
                    # Log error details but keep trying other formats
                    error_info = response.json() if response.text else "No response data"
                    logging.debug(f"Telegram API error with chat_id {chat_id} (attempt {attempt+1}/{max_retries}): {error_info}")
                    
                    # Don't retry this format immediately - try next format
                    break
                    
            except Exception as e:
                logging.debug(f"Request error with chat_id {chat_id} (attempt {attempt+1}/{max_retries}): {e}")
                break
    
    # If we get here, all attempts failed
    logging.error(f"Failed to send Telegram message after trying all chat ID formats")
    return False

def send_stats_update(stats):
    """
    Send a nicely formatted statistics update to Telegram.
    
    Args:
        stats: Dictionary containing statistics to report
        
    Returns:
        bool: True if message was sent successfully, False otherwise
    """
    if not is_telegram_configured():
        return False
    
    try:
        # Format message with statistics
        message = "<b>🔄 Bitcoin Brute Force Status Update</b>\n\n"
        
        # Add mode information
        if "mode" in stats:
            message += f"<b>Mode:</b> {stats['mode']}\n"
        
        # Add instance information
        if "instance" in stats:
            message += f"<b>Instance:</b> {stats['instance']}\n"
        
        # Add core count
        if "cores" in stats:
            message += f"<b>Cores:</b> {stats['cores']}\n"
        
        # Add address counts
        if "addresses_checked" in stats:
            message += f"<b>Addresses Checked:</b> {stats['addresses_checked']:,}\n"
        
        # Add time information
        if "elapsed_time" in stats:
            hours, remainder = divmod(stats['elapsed_time'], 3600)
            minutes, seconds = divmod(remainder, 60)
            message += f"<b>Elapsed Time:</b> {int(hours)}h {int(minutes)}m {int(seconds)}s\n"
        
        # Add performance metrics
        if "rate" in stats:
            message += f"<b>Current Rate:</b> {stats['rate']:.2f} keys/sec\n"
        
        # Add address details for any found addresses
        if "found_addresses" in stats and stats["found_addresses"]:
            message += "\n<b>🎯 Found Addresses:</b>\n"
            for addr in stats["found_addresses"]:
                message += f"• <code>{addr}</code>\n"
        
        # Send the message
        logging.info("Sending stats update to Telegram")
        return send_telegram_message(message)
        
    except Exception as e:
        logging.error(f"Error formatting Telegram stats message: {e}")
        return False

def send_found_address_alert(address, wif=None, balance=None):
    """
    Send an alert when a matching address is found.
    
    Args:
        address: The Bitcoin address that was found
        wif: The private key in WIF format (optional)
        balance: The balance of the address (optional)
        
    Returns:
        bool: True if message was sent successfully, False otherwise
    """
    if not is_telegram_configured():
        return False
    
    try:
        # Format the alert message
        message = "<b>🚨 ADDRESS FOUND! 🚨</b>\n\n"
        message += f"<b>Address:</b> <code>{address}</code>\n"
        
        if wif:
            message += f"<b>Private Key (WIF):</b> <code>{wif}</code>\n"
        
        if balance is not None:
            message += f"<b>Balance:</b> {balance} BTC\n"
            
        message += "\n<i>Address saved to database and found.txt</i>"
        
        # Send the message with higher priority (more retries)
        logging.info(f"Sending found address alert to Telegram: {address}")
        return send_telegram_message(message)
        
    except Exception as e:
        logging.error(f"Error sending Telegram alert: {e}")
        return False

# Test function
def test_telegram_notification():
    """Test if Telegram notifications are working."""
    if not is_telegram_configured():
        print("Telegram is not configured. Please set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env file")
        return False
    
    test_message = (
        "<b>🧪 Bitcoin Brute Force Tool - Telegram Test</b>\n\n"
        "This is a test message to verify Telegram integration is working correctly.\n\n"
        "<i>If you can see this message, notifications are correctly configured!</i>"
    )
    
    success = send_telegram_message(test_message)
    if success:
        print("✅ Test message sent successfully to Telegram!")
    else:
        print("❌ Failed to send test message to Telegram. Check your configuration and internet connection.")
    
    return success

if __name__ == "__main__":
    # Run test if this file is executed directly
    test_telegram_notification()