#!/usr/bin/env python3
"""
Setup script to help correct Telegram chat configuration.
This script helps users properly set up their Telegram bot and obtain the correct chat ID.
"""

import os
import sys
import logging
import requests
from time import sleep
from dotenv import load_dotenv, set_key

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Load current environment variables
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

def check_bot_token():
    """Verify if the bot token is valid by checking with Telegram API."""
    if not TELEGRAM_BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN is not set in your .env file.")
        return False
    
    # Try to get bot information
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe"
    
    try:
        response = requests.get(url, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                bot_info = data.get("result", {})
                print(f"✅ Bot token is valid! Connected to:")
                print(f"   Bot Name: {bot_info.get('first_name')}")
                print(f"   Username: @{bot_info.get('username')}")
                print(f"   Bot ID: {bot_info.get('id')}")
                return True
        
        print(f"❌ Invalid bot token. API response: {response.text}")
        return False
    except Exception as e:
        print(f"❌ Error checking bot token: {e}")
        return False

def get_updates():
    """Get recent updates (messages) sent to the bot."""
    if not TELEGRAM_BOT_TOKEN:
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    
    try:
        response = requests.get(url, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                updates = data.get("result", [])
                return updates
        
        print(f"❌ Error getting updates: {response.text}")
        return []
    except Exception as e:
        print(f"❌ Error: {e}")
        return []

def get_chat_ids():
    """Extract unique chat IDs from updates."""
    updates = get_updates()
    chat_ids = set()
    
    if not updates:
        return chat_ids
    
    for update in updates:
        # Extract from various types of updates
        if "message" in update and "chat" in update["message"]:
            chat = update["message"]["chat"]
            chat_id = chat["id"]
            chat_name = chat.get("title") or f"{chat.get('first_name', '')} {chat.get('last_name', '')}".strip()
            chat_type = chat.get("type", "unknown")
            chat_ids.add((chat_id, chat_name, chat_type))
        
        elif "callback_query" in update and "message" in update["callback_query"]:
            chat = update["callback_query"]["message"]["chat"]
            chat_id = chat["id"]
            chat_name = chat.get("title") or f"{chat.get('first_name', '')} {chat.get('last_name', '')}".strip()
            chat_type = chat.get("type", "unknown")
            chat_ids.add((chat_id, chat_name, chat_type))
    
    return chat_ids

def send_test_message(chat_id):
    """Send a test message to a specific chat."""
    if not TELEGRAM_BOT_TOKEN:
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": "🧪 Test message from Bitcoin Brute Force Tool\n\nIf you can see this message, your bot is correctly configured!",
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        
        if response.status_code == 200:
            print(f"✅ Test message sent successfully to chat_id: {chat_id}")
            return True
        
        print(f"❌ Failed to send test message: {response.text}")
        return False
    except Exception as e:
        print(f"❌ Error sending test message: {e}")
        return False

def update_env_file(chat_id):
    """Update the .env file with the correct chat ID."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    
    if not os.path.exists(env_path):
        print(f"❌ .env file not found at {env_path}")
        return False
    
    try:
        # Update the .env file
        set_key(env_path, "TELEGRAM_CHAT_ID", str(chat_id))
        print(f"✅ Updated .env file with TELEGRAM_CHAT_ID={chat_id}")
        return True
    except Exception as e:
        print(f"❌ Error updating .env file: {e}")
        return False

def main():
    print("\n=== TELEGRAM BOT SETUP ASSISTANT ===\n")
    
    # Check if bot token is valid
    print("Step 1: Checking your bot token...")
    if not check_bot_token():
        print("\nTo create a new bot:")
        print("1. Start a chat with @BotFather on Telegram")
        print("2. Send /newbot and follow the instructions")
        print("3. Copy the provided token to your .env file as TELEGRAM_BOT_TOKEN")
        return
    
    # Display instructions
    print("\nStep 2: Setting up chat permissions...")
    print("For the bot to send you messages, you need to start a conversation with it.")
    print("Please choose one of the following options:")
    print("1. Send a message to your bot in a private chat")
    print("2. Add your bot to a group and send a message mentioning the bot")
    print("\nAfter sending a message, wait a few seconds, then continue this setup.")
    
    input("\nPress Enter to continue after you've sent a message to your bot...")
    
    # Get available chat IDs
    print("\nStep 3: Checking for available chats...")
    chat_ids = get_chat_ids()
    
    if not chat_ids:
        print("❌ No chats found. Please make sure you've sent a message to your bot.")
        print("You can try again by running this script later.")
        return
    
    # Display available chats
    print(f"\nFound {len(chat_ids)} available chat(s):")
    
    for i, (chat_id, name, chat_type) in enumerate(chat_ids):
        print(f"{i+1}. {name} ({chat_type}) - ID: {chat_id}")
    
    # Let the user select a chat
    try:
        selection = int(input("\nEnter the number of the chat you want to use: "))
        if 1 <= selection <= len(chat_ids):
            selected_chat_id, name, chat_type = list(chat_ids)[selection-1]
            
            # Send test message
            print(f"\nSending test message to {name}...")
            if send_test_message(selected_chat_id):
                # Update .env file
                if update_env_file(selected_chat_id):
                    print("\n✅ Setup completed successfully!")
                    print(f"Chat ID {selected_chat_id} has been saved to your .env file.")
                    print("\nYou can now run the main application and Telegram notifications should work.")
        else:
            print("❌ Invalid selection.")
    except ValueError:
        print("❌ Please enter a valid number.")

if __name__ == "__main__":
    main()