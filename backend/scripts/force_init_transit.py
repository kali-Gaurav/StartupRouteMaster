import sqlite3
import sys
import os

# Ensure backend package is importable
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from database.session import transit_db_path
from database.models import TransitBase

def force_create_transit():
    raw_path = transit_db_path.replace("sqlite:///", "")
    print(f"Forcing table creation in {raw_path}...")
    
    from database.session import engine_transit
    try:
        TransitBase.metadata.create_all(bind=engine_transit)
        
        # Verify with raw sqlite
        conn = sqlite3.connect(raw_path)
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        print(f"Tables now in transit_graph.db: {[t[0] for t in tables]}")
        conn.close()
        
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    force_create_transit()
