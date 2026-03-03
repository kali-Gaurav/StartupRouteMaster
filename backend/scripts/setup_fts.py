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
    # Convert sqlite:/// path to raw path
    raw_path = transit_db_path.replace("sqlite:///", "")
    print(f"Initializing FTS5 on {raw_path}...")
    
    conn = sqlite3.connect(raw_path)
    try:
        # 1. Create FTS5 Virtual Table for Stations
        conn.execute("DROP TABLE IF EXISTS stops_fts")
        conn.execute("""
            CREATE VIRTUAL TABLE stops_fts USING fts5(
                stop_id UNINDEXED,
                code,
                name,
                city,
                content='stops',
                content_rowid='id'
            )
        """)
        
        # 2. Populate FTS5 table
        conn.execute("""
            INSERT INTO stops_fts(rowid, code, name, city)
            SELECT id, code, name, city FROM stops
        """)
        
        # 3. Create Triggers to keep FTS in sync
        conn.execute("DROP TRIGGER IF EXISTS stops_ai")
        conn.execute("""
            CREATE TRIGGER stops_ai AFTER INSERT ON stops BEGIN
                INSERT INTO stops_fts(rowid, code, name, city) VALUES (new.id, new.code, new.name, new.city);
            END
        """)
        
        conn.commit()
        print("🚀 SQLite FTS5 Setup Complete for Stations.")
        
    except Exception as e:
        print(f"FTS Setup Failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    setup_fts()
