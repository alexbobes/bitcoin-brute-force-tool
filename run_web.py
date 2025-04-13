#!/usr/bin/env python3
"""
Runner script for Bitcoin Brute Force Tool web interface.
This is a convenience script that imports the web app and runs it.
"""

from src.ui.app import app

if __name__ == "__main__":
    app.run(debug=True)