import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from pathlib import Path

# Load .env
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

db_url = os.getenv("DATABASE_URL")

try:
    engine = create_engine(db_url)
    with engine.connect() as conn:
        print("--- Database Inspection (RAW) ---")
        
        # Stops
        print("\n📍 Stops:")
        stops = conn.execute(text("SELECT * FROM stops")).fetchall()
        for s in stops:
            print(" - " + str(dict(s._mapping)))
            
        # Trips
        print("\n🚆 Trips:")
        trips = conn.execute(text("SELECT * FROM trips")).fetchall()
        for t in trips:
            print(" - " + str(dict(t._mapping)))

except Exception as e:
    print("❌ Error: " + str(e))
