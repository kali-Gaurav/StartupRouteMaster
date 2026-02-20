# check_db.py
import argparse
from sqlalchemy import create_engine
import time

print("--- Database Connection Test ---")

parser = argparse.ArgumentParser(description="Test PostgreSQL database connection.")
parser.add_argument("--db-url", required=True, help="URL for the target PostgreSQL database.")
args = parser.parse_args()

# Give Docker container a moment to initialize
print("Waiting 5 seconds for the database container to be ready...")
time.sleep(5)

# To prevent leaking the password in logs, we'll print a sanitized version
sanitized_url = args.db_url.split('@')[1] if '@' in args.db_url else args.db_url
print(f"\nAttempting to connect to database at: {sanitized_url}")

try:
    engine = create_engine(args.db_url)
    with engine.connect() as connection:
        print("\n✅ SUCCESS: Successfully connected to the PostgreSQL database!")
        print("You can now tell me to proceed.")
        
except Exception as e:
    print("\n❌ FAILURE: Failed to connect to the database.")
    print("\nPlease check the following:")
    print("1. Is the Docker container running? (Check with 'docker ps')")
    print("2. Is the password in the command you are running correct?")
    print(f"\nReported Error: {e}")

print("\n--- End of Test ---")