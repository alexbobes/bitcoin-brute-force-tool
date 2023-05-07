# Bitcoin Brute Force Tool

This repository contains a Python script that attempts to brute force Bitcoin private keys to find matching addresses. This project is for educational purposes only and should not be used for any illegal activities.

## Disclaimer

This project is for educational purposes only. Using this software to access or attempt to access any unauthorized accounts or steal funds is illegal and unethical. The creator of this software is not responsible for any misuse of this software.

## Features

- Supports multiple brute force modes:
  - Random brute force (RBF)
  - Traditional brute force (TBF)
  - Offset traditional brute force (OTBF)
  - Online brute force (OBF) with API rate limiting
- Utilizes multiprocessing to take advantage of multiple CPU cores
- Supports debug modes for each brute force mode
- Automatically saves progress and hash rate information
- Save and load progress for each instance, allowing you to resume from where you left off
- Saves found addresses and balances to a wallet database (SQLite)
- Sends notifications to Slack with information about the script's progress, such as the number of addresses checked in the last 30 minutes and the total number of addresses checked

## Requirements

- Python 3.6 or higher
- [bit](https://github.com/ofek/bit) library: `pip install bit`
- [requests](https://docs.python-requests.org/en/master/) library: `pip install requests`

## Usage

1. Clone the repository: `git clone https://github.com/alexbobes/bitcoin-brute-force-tool`
2. Change to the project directory: `cd bitcoin-brute-force-tool`
3. Ensure you have the necessary libraries installed: `pip install -r requirements.txt`
4. Add the Bitcoin addresses you want to check for a match in a file named `wallets.txt`. Each address should be on a new line.
5. Run the script: `python bruteforce.py`
6. Follow the prompts to select the desired brute force mode and number of CPU cores to use.
7. To send Slack notifications, set your Slack webhook URL in the .env file. Replace YOUR_SLACK_WEBHOOK_URL with your actual webhook URL.

## Contributing

Contributions are welcome! If you have any ideas or suggestions to improve the project, feel free to open an issue or submit a pull request.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more information.
