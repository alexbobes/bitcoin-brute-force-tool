# Bitcoin Brute Force Tool

This repository contains a Python script that attempts to brute force Bitcoin private keys to find matching addresses. It also provides a Flask web interface for real-time monitoring of the brute force process. This project is for educational purposes only and should not be used for any illegal activities.

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
- Saves found addresses and balances to a MySQL database
- Sends notifications to Slack with information about the script's progress, such as the number of addresses checked in the last 30 minutes, the total number of addresses checked, and the hash rate in the last 30 minutes
- Flask-based web interface for real-time monitoring of the brute force process, including statistics on the number of addresses tried.

## Requirements

- Python 3.6 or higher

## Usage

1. Clone the repository: `git clone https://github.com/alexbobes/bitcoin-brute-force-tool`
2. Change to the project directory: `cd bitcoin-brute-force-tool`
3. Ensure you have the necessary libraries installed: `pip install -r requirements.txt`
4. To run the brute force script: `python main.py`
5. To run the Flask web interface for real-time monitoring: `python app.py`
6. Access the web interface via `http://localhost:5000/`
7. To send Slack notifications, set your Slack webhook URL in the .env file. Replace YOUR_SLACK_WEBHOOK_URL with your actual webhook URL.

## Contributing

Contributions are welcome! If you have any ideas or suggestions to improve the project, feel free to open an issue or submit a pull request.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more information.