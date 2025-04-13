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
- Saves found addresses and balances to a PostgreSQL database
- Sends notifications to Slack and Telegram with information about the script's progress, such as the number of addresses checked in the last 30 minutes, the total number of addresses checked, and the hash rate in the last 30 minutes
- Performance benchmarking tool to compare different methods and find optimal settings
- Flask-based web interface for real-time monitoring of the brute force process, including statistics on the number of addresses tried.

## Requirements

- Python 3.6 or higher

## Project Structure

The code is organized into the following structure:

```
bitcoin-brute-force-tool/
├── run.py                      # Main entry point script
├── run_web.py                  # Web interface entry point
├── benchmark.py                # Run performance benchmark
├── import_blockchair.py        # Import addresses from BlockChair
├── import_wallets.py           # Import addresses from wallet files
├── .env                        # Environment variables (not in git)
├── .env.example                # Example environment config
├── requirements.txt            # Python dependencies
├── README.md                   # This file
├── found.txt                   # Contains found addresses
└── src/                        # Source code
    ├── core/                   # Core functionality
    │   └── bruteforcer.py      # Bitcoin address generation
    ├── database/               # Database operations
    │   ├── db_manager.py       # Database connection handling
    │   └── wallet_database.txt # Simple database for found addresses
    ├── notifications/          # Notification services
    │   ├── notification_manager.py # Slack notifications
    │   ├── telegram_notifier.py    # Telegram notifications
    │   ├── get_chat_id.py          # Helper for Telegram setup
    │   └── telegram_chat_setup.py  # Telegram configuration
    ├── scripts/                # Data management scripts
    │   ├── import_blockchair.py  # Import addresses from BlockChair
    │   └── import_wallets.py     # Import addresses from wallet files
    ├── ui/                     # Web interface
    │   ├── app.py              # Flask web application
    │   ├── static/             # Static assets (CSS, JS)
    │   └── templates/          # HTML templates
    └── utils/                  # Utility scripts
        └── benchmark.py        # Performance benchmarking
```

## Usage

1. Clone the repository: `git clone https://github.com/alexbobes/bitcoin-brute-force-tool`
2. Change to the project directory: `cd bitcoin-brute-force-tool`
3. Ensure you have the necessary libraries installed: `pip install -r requirements.txt`
4. To run the brute force script: `python run.py`
5. To run the Flask web interface for real-time monitoring: `python run_web.py`
6. Access the web interface via `http://localhost:5000/`
7. To send Slack notifications, set your Slack webhook URL in the .env file.
8. To enable Telegram notifications:
   - Create a bot using BotFather on Telegram and get the token
   - Send a message to your bot (this is required for the bot to be able to message you)
   - Run `python -m src.notifications.get_chat_id` to get your chat ID
   - Add the token and chat ID to your .env file
9. To benchmark performance and find optimal settings:
   - Run `python -m src.utils.benchmark`
   - The benchmark will test different methods and batch sizes
   - Results show keys per second for each configuration
   - Recommendations for optimal settings are provided at the end

## Benchmark Results

The tool includes a benchmark feature that helps determine the optimal settings for your hardware. Sample benchmark results:

```
+----------------------+-------+------------+------------+
|        Method        | Cores | Batch Size |  Keys/sec  |
+----------------------+-------+------------+------------+
|   Random Key (RBF)   |   1   |     1      | 20,611.23  |
| Sequential Key (TBF) |   1   |     1      | 20,552.04  |
| Batch (no threading) |   1   |    100     | 20,969.97  |
|   Batch (threaded)   |   1   |    100     |  5,374.87  |
| Batch (no threading) |   1   |   1,000    | 20,615.03  |
|   Batch (threaded)   |   1   |   1,000    |  6,990.91  |
| Batch (no threading) |   1   |   10,000   | 20,177.03  |
|   Batch (threaded)   |   1   |   10,000   |  7,311.87  |
| RBF (full pipeline)  |   1   |   1,000    | 186,730.68 |
| TBF (full pipeline)  |   1   |   1,000    | 188,878.04 |
| OTBF (full pipeline) |   1   |   1,000    | 191,496.55 |
+----------------------+-------+------------+------------+
```

Recommendations from benchmark:
- Fastest method: OTBF (full pipeline) with batch size 1,000 (~191K keys/sec)
- Random vs Sequential: Comparable performance with slight edge to random generation
- Threading: For this specific workload, single-threaded batch processing is actually faster
- Optimal batch size: 1,000 keys provides the best performance
- Daily throughput: ~16.5 trillion addresses per day per core

Your results may vary depending on your hardware. Run the benchmark on your system to get personalized recommendations.

## Contributing

Contributions are welcome! If you have any ideas or suggestions to improve the project, feel free to open an issue or submit a pull request.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more information.