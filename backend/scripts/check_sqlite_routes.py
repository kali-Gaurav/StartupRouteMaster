import sqlite3
import os

def check_sqlite_routes():
    db_path = 'backend/database/railway_data.db'
    train_nos = ['16185', '12275', '13110', '21107', '14890']
    
    conn = sqlite3.connect(db_path)
    try:
        for tno in train_nos:
            res = conn.execute("SELECT count(*) FROM train_routes WHERE train_no = ?", (tno,)).fetchone()
            print(f"Train {tno}: {res[0]} routes in SQLite")
            
            # If 1, let's see what it is
            if res[0] == 1:
                row = conn.execute("SELECT * FROM train_routes WHERE train_no = ?", (tno,)).fetchone()
                print(f"  - Data: {row}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_sqlite_routes()
