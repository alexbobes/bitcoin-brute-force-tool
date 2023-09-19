from flask import Flask, render_template, jsonify
from db_manager import get_total_addresses_by_day
import db_manager

app = Flask(__name__)

@app.route('/')
def index():
    total_addresses = db_manager.get_total_addresses()
    total_found = db_manager.get_total_found_addresses() 
    
    return render_template('index.html', total_addresses=total_addresses, total_found=total_found)

@app.route('/api/addresses-by-day', methods=['GET'])
def addresses_by_day():
    data = get_total_addresses_by_day()
    return jsonify(data)

if __name__ == '__main__':
    app.run(debug=True)
