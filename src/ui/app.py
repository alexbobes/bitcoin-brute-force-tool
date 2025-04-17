from flask import Flask, render_template, jsonify, stream_with_context, Response, request
from src.database.db_manager import (
    get_total_addresses, 
    get_total_found_addresses, 
    get_total_addresses_to_bruteforce,
    get_average_hash_rate,
    get_daily_stats,
    update_daily_stats
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
    
    # Update daily statistics on page load to ensure data is current
    try:
        update_daily_stats()
    except Exception as e:
        logging.error(f"Error updating daily stats on page load: {e}")
    
    # Get daily statistics for display
    daily_stats = get_daily_stats(days=7)
    
    # Log the real values
    logging.info(f"Initial page load - Addresses: {total_addresses}, Found: {total_found}, To Bruteforce: {total_addresses_to_bruteforce}, Hash Rate: {hash_rate}")
    
    return render_template('index.html', 
                          total_addresses=total_addresses, 
                          total_found=total_found, 
                          total_addresses_to_bruteforce=total_addresses_to_bruteforce,
                          hash_rate=hash_rate,
                          daily_stats=daily_stats,
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

@app.route('/api/daily-stats', methods=['GET'])
def daily_stats_api():
    """Get daily statistics for the past week"""
    # Update stats before returning them
    try:
        update_daily_stats()
    except Exception as e:
        logging.error(f"Error updating daily stats via API: {e}")
    
    # Get the stats
    days = request.args.get('days', default=7, type=int)
    if days > 30:  # Limit to 30 days max
        days = 30
    
    stats = get_daily_stats(days=days)
    logging.debug(f"API - Daily stats: {len(stats)} records")
    return jsonify({"daily_stats": stats})

@app.route('/api/sessions', methods=['GET'])
def sessions_api():
    """Get information about recent sessions"""
    from src.database.db_manager import get_db_connection
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Query latest sessions with their metrics
            cur.execute("""
            SELECT 
                session_id, 
                start_time, 
                end_time, 
                start_addresses, 
                final_addresses, 
                addresses_processed,
                EXTRACT(EPOCH FROM (end_time - start_time)) AS duration_seconds
            FROM 
                session_tracking
            ORDER BY 
                start_time DESC
            LIMIT 10
            """)
            
            results = cur.fetchall()
            
            # Format results
            sessions = []
            for row in results:
                end_time = row[2] if row[2] else None
                
                # Calculate duration if session has ended
                duration_formatted = None
                if row[6] and row[6] > 0:
                    duration_seconds = row[6]
                    hours = int(duration_seconds // 3600)
                    minutes = int((duration_seconds % 3600) // 60)
                    seconds = int(duration_seconds % 60)
                    duration_formatted = f"{hours}h {minutes}m {seconds}s"
                
                # Safely convert values to appropriate types
                try:
                    start_addr = int(str(row[3])) if row[3] is not None else None
                except (ValueError, TypeError):
                    start_addr = None
                    
                try:
                    final_addr = int(str(row[4])) if row[4] is not None else None
                except (ValueError, TypeError):
                    final_addr = None
                    
                try:
                    addr_processed = int(str(row[5])) if row[5] is not None else None
                except (ValueError, TypeError):
                    addr_processed = None
                
                sessions.append({
                    'session_id': row[0],
                    'start_time': row[1].isoformat() if row[1] else None,
                    'end_time': end_time.isoformat() if end_time else None,
                    'start_addresses': start_addr,
                    'final_addresses': final_addr,
                    'addresses_processed': addr_processed,
                    'duration': duration_formatted,
                    'active': end_time is None
                })
            
            return jsonify({"sessions": sessions})
    except Exception as e:
        logging.error(f"Error retrieving session data: {e}")
        if conn and not conn.closed:
            try:
                conn.rollback()  # Rollback transaction on error
            except Exception:
                pass  # Ignore errors during rollback
        return jsonify({"error": str(e), "sessions": []})
    finally:
        if conn and not conn.closed:
            try:
                conn.close()
            except Exception:
                pass  # Ignore errors during connection close

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