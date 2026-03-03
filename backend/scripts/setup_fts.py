"""
[Advanced DB] setup_fts.py (TODO #21)

Initializes SQLite FTS5 (Full-Text Search) for stations and trains.
Enables lightning-fast autocomplete.
"""

import sqlite3
import sys
import os

# Ensure backend package is importable
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from database.session import transit_db_path

def setup_fts():
    raw_path = transit_db_path.replace("sqlite:///", "")
    print(f"Initializing Production-Grade FTS5 on {raw_path}...")
    
    conn = sqlite3.connect(raw_path)
    try:
        # --- 1. STATIONS FTS5 (External Content) ---
        conn.execute("DROP TABLE IF EXISTS stops_fts")
        conn.execute("""
            CREATE VIRTUAL TABLE stops_fts USING fts5(
                code,
                name,
                city,
                content='stops',
                content_rowid='id'
            )
        """)
        conn.execute("INSERT INTO stops_fts(rowid, code, name, city) SELECT id, code, name, city FROM stops")

        # --- 2. TRAINS FTS5 (Self-Contained to avoid rowid mismatch with string PK) ---
        conn.execute("DROP TABLE IF EXISTS trains_fts")
        conn.execute("""
            CREATE VIRTUAL TABLE trains_fts USING fts5(
                train_number,
                train_name
            )
        """)
        conn.execute("INSERT INTO trains_fts(train_number, train_name) SELECT train_number, train_name FROM trains_master")
        
        conn.commit()
        print("🚀 Production FTS5 Setup Complete (Stations + Trains).")
        
    except Exception as e:
        print(f"FTS Setup Failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    setup_fts()
