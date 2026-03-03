import sqlite3
import os

def check():
    conn = sqlite3.connect('backend/database/railway_data.db')
    cur = conn.cursor()
    sql = """
        SELECT tr.train_no, trd.mon, trd.tue, trd.wed, trd.thu, trd.fri, trd.sat, trd.sun
        FROM train_routes tr
        JOIN train_running_days trd ON tr.train_no = trd.train_no
        WHERE tr.station_code = 'NDLS'
        AND EXISTS (SELECT 1 FROM train_routes tr2 WHERE tr2.train_no = tr.train_no AND tr2.station_code = 'BCT' AND tr2.seq_no > tr.seq_no)
        LIMIT 20
    """
    cur.execute(sql)
    for r in cur.fetchall():
        print(f"Train {r[0]}: Mon={r[1]}, Tue={r[2]}, Wed={r[3]}, Thu={r[4]}, Fri={r[5]}, Sat={r[6]}, Sun={r[7]}")
    conn.close()

if __name__ == "__main__":
    check()
