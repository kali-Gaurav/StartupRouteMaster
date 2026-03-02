import os
from sqlalchemy import create_engine, inspect
from dotenv import load_dotenv
from pathlib import Path

# Load .env
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

db_url = os.getenv("DATABASE_URL")
if not db_url:
    print("❌ DATABASE_URL not set in .env")
    exit(1)

print(f"Connecting to database...")

try:
    engine = create_engine(db_url)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"✅ Connection successful!")
    print(f"Tables found ({len(tables)}): {', '.join(tables)}")
    
    # Check for critical transit tables
    critical_tables = ['stops', 'stop_times', 'trips', 'routes', 'calendar', 'calendar_dates']
    missing = [t for t in critical_tables if t not in tables]
    if missing:
        print(f"⚠️ Missing critical transit tables: {', '.join(missing)}")
    else:
        print(f"✅ All critical transit tables present.")

except Exception as e:
    print(f"❌ Connection failed: {e}")
