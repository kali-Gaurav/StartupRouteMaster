import sqlite3
import os

def check():
    conn = sqlite3.connect('backend/database/railway_data.db')
    cur = conn.cursor()
    train_no = "12952"
    cur.execute("SELECT * FROM train_running_days WHERE train_no = ?", (train_no,))
    print(f"Running Days for {train_no}: {cur.fetchone()}")
    
    cur.execute("SELECT station_code, arrival_time, departure_time, seq_no FROM train_routes WHERE train_no = ? ORDER BY seq_no", (train_no,))
    print(f"Route for {train_no}:")
    for r in cur.fetchall():
        print(f"  {r[0]} - {r[1]} / {r[2]} (Seq: {r[3]})")
    conn.close()

if __name__ == "__main__":
    check()
