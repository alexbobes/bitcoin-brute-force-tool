from flask import Flask, render_template, jsonify, stream_with_context, Response
from src.database.db_manager import (
    get_total_addresses, 
    get_total_found_addresses, 
    get_total_addresses_to_bruteforce,
    get_average_hash_rate
)
import logging
from flask_bootstrap import Bootstrap
import json
from time import sleep
from datetime import datetime

logging.basicConfig(level=logging.DEBUG)

# Initialize Flask with correct template and static folder paths
app = Flask(__name__, 
           template_folder='../../templates',
           static_folder='../../static')
Bootstrap(app)

@app.route('/')
def index():
    # Get real data from database
    total_addresses = get_total_addresses()
    total_found = get_total_found_addresses() 
    total_addresses_to_bruteforce = get_total_addresses_to_bruteforce()
    hash_rate = get_average_hash_rate()
    
    # Add current datetime for display
    now = datetime.now()
    
    # Log the real values
    logging.info(f"Initial page load - Addresses: {total_addresses}, Found: {total_found}, To Bruteforce: {total_addresses_to_bruteforce}, Hash Rate: {hash_rate}")
    
    return render_template('index.html', 
                          total_addresses=total_addresses, 
                          total_found=total_found, 
                          total_addresses_to_bruteforce=total_addresses_to_bruteforce,
                          hash_rate=hash_rate,
                          now=now)

@app.route('/api/total-addresses', methods=['GET'])
def total_addresses():
    """Return the real number of processed addresses"""
    total = get_total_addresses()
    logging.debug(f"API - Total addresses: {total}")
    return jsonify({"total_addresses": total})

@app.route('/api/total-to-bruteforce', methods=['GET'])
def total_to_bruteforce():
    """Return the real number of addresses to bruteforce"""
    total = get_total_addresses_to_bruteforce()
    logging.debug(f"API - Total to bruteforce: {total}")
    return jsonify({"total_to_bruteforce": total})

@app.route('/api/total-found', methods=['GET'])
def total_found():
    """Return the real number of found addresses"""
    total = get_total_found_addresses()
    logging.debug(f"API - Total found: {total}")
    return jsonify({"total_found": total})

@app.route('/api/hash-rate', methods=['GET'])
def hash_rate():
    """Get the real hash rate from database"""
    rate = get_average_hash_rate()
    logging.debug(f"API - Hash rate: {rate}")
    return jsonify({"hash_rate": rate})

def human_format(value):
    number = float(value)
    magnitude = 0
    while abs(number) >= 1000:
        magnitude += 1
        number /= 1000.0
    return '%.4f %s' % (number, ['', 'K', 'M', 'B', 'T'][magnitude])

app.jinja_env.filters['human_format'] = human_format

if __name__ == '__main__':
    app.run(debug=True)