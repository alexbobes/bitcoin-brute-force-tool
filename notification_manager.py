import requests
import logging
from time import sleep
import json

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