from flask import Flask, render_template, jsonify, stream_with_context, Response
from db_manager import (get_total_addresses, get_total_found_addresses,
                        get_total_addresses_by_day, get_total_addresses_to_bruteforce)
import logging
from flask_bootstrap import Bootstrap
import json
from time import sleep
import db_manager

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
Bootstrap(app)

@app.route('/')
def index():
    total_addresses = db_manager.get_total_addresses()
    total_found = db_manager.get_total_found_addresses() 
    total_addresses_to_bruteforce = get_total_addresses_to_bruteforce()
    
    return render_template('index.html', total_addresses=total_addresses, total_found=total_found, total_addresses_to_bruteforce=total_addresses_to_bruteforce)

@app.route('/api/addresses-by-day', methods=['GET'])
def addresses_by_day_stream():

    def datetime_to_string(dt):
        return dt.strftime('%Y-%m-%d')

    def generate():
        while True:
            data = get_total_addresses_by_day()
            yield f"data: {json.dumps(data, default=datetime_to_string)}\n\n"
            sleep(10)

    return Response(stream_with_context(generate()), content_type='text/event-stream')

@app.route('/api/total-addresses', methods=['GET'])
def total_addresses():
    total = get_total_addresses()
    return jsonify({"total_addresses": total})

@app.route('/api/total-to-bruteforce', methods=['GET'])
def total_to_bruteforce():
    total = get_total_addresses_to_bruteforce()
    return jsonify({"total_to_bruteforce": total})

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