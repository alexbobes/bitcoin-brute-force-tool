#!/usr/bin/env python3
"""
Script to get Telegram chat ID for your bot.
This will show all recent chats that have interacted with your bot.
"""

import os
import requests
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

# Get bot token from environment
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

def main():
    if not BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN not set in .env file")
        print("Please add your bot token to the .env file.")
        return
    
    # More secure logging that doesn't expose token
    print("Bot token is configured")
    print("\nRetrieving bot information...\n")
    
    # First, test if the bot token is valid
    try:
        me_response = requests.get(f'https://api.telegram.org/bot{BOT_TOKEN}/getMe')
        me_data = me_response.json()
        
        if not me_data.get('ok', False):
            print(f"ERROR: Invalid bot token. Response: {me_data}")
            return
        
        bot_info = me_data['result']
        print(f"✓ Connected to bot: {bot_info['first_name']} (@{bot_info.get('username', 'Unknown')})")
        
    except Exception as e:
        print(f"ERROR: Could not connect to Telegram API: {e}")
        return
    
    # Now, get the updates to find available chat IDs
    print("\nGetting recent chats that have interacted with this bot...\n")
    
    try:
        updates_response = requests.get(f'https://api.telegram.org/bot{BOT_TOKEN}/getUpdates')
        updates_data = updates_response.json()
        
        if not updates_data.get('ok', False):
            print(f"ERROR: Could not get updates. Response: {updates_data}")
            return
        
        updates = updates_data['result']
        
        if not updates:
            print("No recent messages found!")
            print("\nTo get your chat ID, you need to:")
            print("1. Open Telegram and search for your bot's username")
            print("2. Start a conversation with your bot by sending a message")
            print("3. Run this script again")
            return
        
        print(f"Found {len(updates)} recent interactions\n")
        
        # Track unique chats
        unique_chats = {}
        
        for update in updates:
            chat = None
            chat_type = "Unknown"
            message_text = "Unknown"
            
            # Extract chat from different update types
            if 'message' in update:
                chat = update['message'].get('chat')
                chat_type = "Message"
                message_text = update['message'].get('text', 'No text')
            elif 'edited_message' in update:
                chat = update['edited_message'].get('chat')
                chat_type = "Edited message"
                message_text = update['edited_message'].get('text', 'No text')
            elif 'callback_query' in update and 'message' in update['callback_query']:
                chat = update['callback_query']['message'].get('chat')
                chat_type = "Callback query"
                message_text = update['callback_query'].get('data', 'No data')
            
            if chat and 'id' in chat:
                chat_id = chat['id']
                
                if chat_id not in unique_chats:
                    title = None
                    if 'title' in chat:  # For groups
                        title = chat['title']
                    else:  # For private chats
                        first_name = chat.get('first_name', '')
                        last_name = chat.get('last_name', '')
                        title = f"{first_name} {last_name}".strip()
                    
                    unique_chats[chat_id] = {
                        'title': title,
                        'type': chat.get('type', 'Unknown'),
                        'example_text': message_text
                    }
        
        if not unique_chats:
            print("No valid chats found in the updates.")
            return
        
        # Print out the chat IDs
        print("Available chats:")
        print("=======================================")
        
        for chat_id, chat_info in unique_chats.items():
            chat_type = chat_info['type']
            title = chat_info['title']
            text = chat_info['example_text']
            
            print(f"Chat ID: {chat_id}")
            print(f"Name/Title: {title}")
            print(f"Type: {chat_type}")
            print(f"Last message: {text[:30]}{'...' if len(text) > 30 else ''}")
            print("---------------------------------------")
        
        print("\nTo use a chat, add the Chat ID to your .env file:")
        print("TELEGRAM_CHAT_ID=<insert_chat_id_here>")
        
    except Exception as e:
        print(f"ERROR: {e}")
        
if __name__ == '__main__':
    main()