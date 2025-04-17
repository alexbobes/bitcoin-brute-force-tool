#!/usr/bin/env python3
"""
Database connection diagnostic tool for Bitcoin Brute Force Tool
This script checks PostgreSQL configuration and connection issues
"""

import os
import sys
import psycopg2
from dotenv import load_dotenv
import subprocess
import platform

def print_header(text):
    """Print a formatted header"""
    print("\n" + "=" * 80)
    print(f" {text} ".center(80, "="))
    print("=" * 80)

def print_section(text):
    """Print a section header"""
    print("\n" + "-" * 80)
    print(f" {text} ".center(80, "-"))
    print("-" * 80)

def print_success(text):
    """Print a success message"""
    print(f"\n✅ {text}")

def print_error(text):
    """Print an error message"""
    print(f"\n❌ {text}")

def print_warning(text):
    """Print a warning message"""
    print(f"\n⚠️ {text}")

def print_info(text):
    """Print an info message"""
    print(f"\n➡️ {text}")

def check_platform():
    """Check the operating system"""
    print_section("Platform Information")
    system = platform.system()
    release = platform.release()
    print(f"Operating System: {system} {release}")
    
    if system == "Windows":
        print_warning("Running on Windows - PostgreSQL may require additional configuration")
        print_info("On Windows, PostgreSQL often runs as a service")
        print_info("Ensure the PostgreSQL service is running:")
        print("  - Open Services (services.msc)")
        print("  - Look for 'postgresql' or similar service")
        print("  - Ensure it is started and set to Automatic")
    elif system == "Linux":
        print_info("On Linux, check PostgreSQL service status:")
        try:
            output = subprocess.check_output(["systemctl", "status", "postgresql"], 
                                           stderr=subprocess.STDOUT,
                                           text=True)
            print(output[:500])  # Show first 500 chars
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"Could not check PostgreSQL service: {e}")
            print("You can manually check with: sudo systemctl status postgresql")
    elif system == "Darwin":  # macOS
        print_info("On macOS, check PostgreSQL service status:")
        try:
            output = subprocess.check_output(["brew", "services", "list", "postgresql"], 
                                           stderr=subprocess.STDOUT,
                                           text=True)
            print(output)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"Could not check PostgreSQL service: {e}")
            print("You can manually check with: brew services list postgresql")

def check_env_file():
    """Check database configuration in .env file"""
    print_section("Environment Variables Check")
    
    # Try to load from .env file
    load_dotenv()
    
    # Get variables with defaults
    db_host = os.getenv("DB_HOST", "localhost")
    db_user = os.getenv("DB_USER", "")
    db_password = os.getenv("DB_PASSWORD", "")
    db_name = os.getenv("DB_NAME", "bitcoin_brute")
    db_sslmode = os.getenv("DB_SSLMODE", "prefer")
    
    env_ok = True
    
    # Check each variable
    if not db_host:
        print_error("DB_HOST is missing")
        env_ok = False
    else:
        print_info(f"DB_HOST is set to: {db_host}")
        
    if not db_user:
        print_error("DB_USER is missing")
        env_ok = False
    else:
        print_info(f"DB_USER is set to: {db_user}")
        
    if not db_password:
        print_warning("DB_PASSWORD is not set - this requires PostgreSQL to be configured for 'trust' authentication")
    else:
        masked_pass = '*' * len(db_password)
        print_info(f"DB_PASSWORD is set to: {masked_pass}")
        
    if not db_name:
        print_error("DB_NAME is missing")
        env_ok = False
    else:
        print_info(f"DB_NAME is set to: {db_name}")
        
    print_info(f"DB_SSLMODE is set to: {db_sslmode}")
    
    if not env_ok:
        print_error("Environment variables are incomplete. Please check your .env file.")
        print("Example .env file:")
        print("""
DB_HOST=localhost
DB_USER=postgres
DB_PASSWORD=your_password
DB_NAME=bitcoin_brute
DB_SSLMODE=disable
        """)
    
    return {
        "host": db_host,
        "user": db_user,
        "password": db_password,
        "dbname": db_name,
        "sslmode": db_sslmode
    }

def check_postgres_installed():
    """Check if PostgreSQL client tools are installed"""
    print_section("PostgreSQL Installation Check")
    
    try:
        output = subprocess.check_output(["psql", "--version"], stderr=subprocess.STDOUT, text=True)
        print_success(f"PostgreSQL client installed: {output.strip()}")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print_error("PostgreSQL client (psql) not found")
        print_info("Please install PostgreSQL client tools:")
        print("  - Ubuntu/Debian: sudo apt-get install postgresql-client")
        print("  - CentOS/RHEL: sudo yum install postgresql")
        print("  - macOS: brew install postgresql")
        print("  - Windows: Install from https://www.postgresql.org/download/windows/")
        return False

def test_connection(db_config):
    """Test PostgreSQL connection"""
    print_section("PostgreSQL Connection Test")
    
    try:
        # Try to connect
        print(f"Connecting to PostgreSQL at {db_config['host']} as {db_config['user']}...")
        conn = psycopg2.connect(**db_config)
        
        # Get connection info
        with conn.cursor() as cur:
            cur.execute("SELECT version()")
            version = cur.fetchone()[0]
            print_success(f"Successfully connected to PostgreSQL")
            print_info(f"PostgreSQL version: {version}")
            
            # Check if we can create and query tables
            print_info("Testing database operations...")
            
            # Create test table
            cur.execute("""
            CREATE TABLE IF NOT EXISTS db_test (
                id SERIAL PRIMARY KEY,
                test_val TEXT
            )
            """)
            
            # Insert test value
            cur.execute("INSERT INTO db_test (test_val) VALUES ('connection_test')")
            
            # Query test value
            cur.execute("SELECT test_val FROM db_test WHERE test_val = 'connection_test'")
            result = cur.fetchone()
            
            if result and result[0] == 'connection_test':
                print_success("Database operations working correctly")
            else:
                print_error("Database operations test failed")
                
            # Clean up
            cur.execute("DROP TABLE db_test")
            
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print_error(f"Connection failed: {e}")
        
        # Provide troubleshooting help based on the error
        error_msg = str(e).lower()
        
        if "connection refused" in error_msg:
            print_info("PostgreSQL server is not running or is not accepting connections")
            print_info("Check if PostgreSQL is running with:")
            print("  - Linux: sudo systemctl status postgresql")
            print("  - macOS: brew services list | grep postgres")
            print("  - Windows: Check Services manager for PostgreSQL service")
        
        if "password authentication failed" in error_msg:
            print_info("Password authentication failed")
            print_info("Check your DB_PASSWORD in .env file")
            print_info("You can update PostgreSQL password with:")
            print(f"  sudo -u postgres psql -c \"ALTER USER {db_config['user']} WITH PASSWORD 'new_password';\"")
            print("Then update your .env file with the new password")
        
        if "role" in error_msg and "does not exist" in error_msg:
            print_info(f"The PostgreSQL user '{db_config['user']}' does not exist.")
            print_info(f"To create this user, run the following commands as a PostgreSQL superuser:")
            print(f"  sudo -u postgres psql -c \"CREATE USER {db_config['user']} WITH PASSWORD 'your_password';\"")
            print(f"  sudo -u postgres psql -c \"ALTER USER {db_config['user']} WITH SUPERUSER;\"")
        
        if "database" in error_msg and "does not exist" in error_msg:
            print_info(f"The database '{db_config['dbname']}' does not exist.")
            print_info(f"To create this database, run the following command:")
            print(f"  sudo -u postgres psql -c \"CREATE DATABASE {db_config['dbname']} OWNER {db_config['user']};\"")
        
        return False

def check_schema():
    """Check database schema for expected tables"""
    print_section("Database Schema Check")
    
    # Get database configuration from environment
    db_config = {
        "host": os.getenv("DB_HOST", "localhost"),
        "user": os.getenv("DB_USER", ""),
        "password": os.getenv("DB_PASSWORD", ""),
        "dbname": os.getenv("DB_NAME", "bitcoin_brute"),
        "sslmode": os.getenv("DB_SSLMODE", "prefer")
    }
    
    try:
        conn = psycopg2.connect(**db_config)
        
        with conn.cursor() as cur:
            # Check if expected tables exist
            expected_tables = [
                "wallets",
                "progress",
                "wallet_database",
                "hash_rates",
                "daily_stats",
                "schema_migrations",
                "session_tracking"
            ]
            
            cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            """)
            
            existing_tables = [row[0] for row in cur.fetchall()]
            
            print_info("Checking for required tables:")
            missing_tables = []
            
            for table in expected_tables:
                if table in existing_tables:
                    print_success(f"Table '{table}' exists")
                else:
                    print_error(f"Table '{table}' is missing")
                    missing_tables.append(table)
            
            if missing_tables:
                print_warning("Missing tables detected. Run migrations or initialize database:")
                print("  python -c 'from src.database.db_manager import create_tables; create_tables()'")
            
            # Check wallet_database table schema
            if "wallet_database" in existing_tables:
                cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'wallet_database'
                """)
                
                columns = [row[0] for row in cur.fetchall()]
                
                print_info("Checking wallet_database table columns:")
                
                expected_columns = ["id", "wif", "address", "balance", "found_at"]
                
                for column in expected_columns:
                    if column in columns:
                        print_success(f"Column '{column}' exists")
                    else:
                        print_error(f"Column '{column}' is missing")
                        print_info(f"This may cause errors in code that expects the '{column}' column")
                        
                        if column == "found_at":
                            print_info("To add the missing found_at column:")
                            print("  python -c 'from src.database.db_manager import run_migrations; run_migrations()'")
            
            # Check daily_stats table schema
            if "daily_stats" in existing_tables:
                cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'daily_stats'
                """)
                
                columns = [row[0] for row in cur.fetchall()]
                
                print_info("Checking daily_stats table columns:")
                
                expected_columns = ["id", "date", "addresses_checked", "addresses_found", "avg_hash_rate", "created_at"]
                
                for column in expected_columns:
                    if column in columns:
                        print_success(f"Column '{column}' exists")
                    else:
                        print_error(f"Column '{column}' is missing")
                
                # Check data type of addresses_checked
                cur.execute("""
                SELECT data_type 
                FROM information_schema.columns 
                WHERE table_name = 'daily_stats' AND column_name = 'addresses_checked'
                """)
                
                data_type = cur.fetchone()
                if data_type:
                    print_info(f"Column 'addresses_checked' has data type: {data_type[0]}")
                    
                    if data_type[0] not in ('numeric', 'bigint'):
                        print_warning("For large values, this column should be NUMERIC(78, 0) or at least BIGINT")
            
        conn.close()
        return True
    except Exception as e:
        print_error(f"Error checking schema: {e}")
        return False

def fix_common_issues():
    """Offer to fix common database issues"""
    print_section("Database Fixes")
    
    print("Would you like to fix common database issues? (y/n)")
    response = input("> ").strip().lower()
    
    if response != 'y':
        print_info("Skipping database fixes")
        return
    
    # Get database configuration from environment
    db_config = {
        "host": os.getenv("DB_HOST", "localhost"),
        "user": os.getenv("DB_USER", ""),
        "password": os.getenv("DB_PASSWORD", ""),
        "dbname": os.getenv("DB_NAME", "bitcoin_brute"),
        "sslmode": os.getenv("DB_SSLMODE", "prefer")
    }
    
    try:
        conn = psycopg2.connect(**db_config)
        conn.autocommit = True
        
        with conn.cursor() as cur:
            # 1. Fix found_at column if missing
            try:
                cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'wallet_database' AND column_name = 'found_at'
                """)
                if not cur.fetchone():
                    print_info("Adding missing found_at column to wallet_database table")
                    cur.execute("""
                    ALTER TABLE wallet_database 
                    ADD COLUMN found_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    """)
                    print_success("Added found_at column")
            except Exception as e:
                print_error(f"Error fixing found_at column: {e}")
            
            # 2. Fix daily_stats table data types
            try:
                cur.execute("""
                SELECT data_type 
                FROM information_schema.columns 
                WHERE table_name = 'daily_stats' AND column_name = 'addresses_checked'
                """)
                data_type = cur.fetchone()
                if data_type and data_type[0] not in ('numeric', 'bigint'):
                    print_info("Updating addresses_checked column data type")
                    cur.execute("""
                    ALTER TABLE daily_stats 
                    ALTER COLUMN addresses_checked TYPE NUMERIC(78, 0)
                    """)
                    print_success("Updated addresses_checked column type")
            except Exception as e:
                print_error(f"Error fixing daily_stats column type: {e}")
            
            # 3. Create missing tables if needed
            try:
                print_info("Running database migrations")
                print_info("Importing run_migrations function...")
                
                try:
                    # Add parent directory to path
                    sys.path.insert(0, os.path.abspath('.'))
                    from src.database.db_manager import run_migrations
                    print_info("Running migrations...")
                    run_migrations()
                    print_success("Migrations completed")
                except ImportError as e:
                    print_error(f"Could not import migration function: {e}")
                    print_info("Please run the following command separately:")
                    print("  python -c 'from src.database.db_manager import run_migrations; run_migrations()'")
            except Exception as e:
                print_error(f"Error running migrations: {e}")
        
        conn.close()
        print_success("Database fixes completed")
    except Exception as e:
        print_error(f"Could not connect to apply fixes: {e}")

def main():
    """Main function to run all checks"""
    print_header("Bitcoin Brute Force Tool - Database Diagnostic Tool")
    
    # Check platform information
    check_platform()
    
    # Check if PostgreSQL client is installed
    postgres_available = check_postgres_installed()
    
    # Check .env file configuration
    db_config = check_env_file()
    
    # Test database connection
    if postgres_available:
        connection_ok = test_connection(db_config)
        
        # Check schema if connection successful
        if connection_ok:
            schema_ok = check_schema()
            
            if not schema_ok:
                fix_common_issues()
        else:
            print_warning("Cannot check schema due to connection failure")
    
    print_section("Diagnostic Summary")
    print_info("Based on the checks, here are troubleshooting steps:")
    print("1. Ensure PostgreSQL is running")
    print("2. Check .env file has correct database credentials")
    print("3. Verify the user has permissions to access the database")
    print("4. Run application migrations to create/update tables")
    print("5. If needed, modify code to handle missing columns gracefully")
    
    print_info("For specific error 'column found_at does not exist':")
    print("- Run migrations to add the column: python -c 'from src.database.db_manager import run_migrations; run_migrations()'")
    
    print_info("For transaction errors:")
    print("- Ensure all database exceptions include conn.rollback() before returning")
    
    print_info("For type errors (int + str):")
    print("- Update daily_stats functions to explicitly convert types: int(str(value))")
    
    print("\nFor more information, check the documentation or seek help from the project maintainers.")

if __name__ == "__main__":
    main()