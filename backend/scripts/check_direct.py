import psycopg2
import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'backend'))
from database.config import Config

def check():
    conn = psycopg2.connect(Config.DATABASE_URL)
    cur = conn.cursor()
    src = 'NDLS'
    dst = 'BCT'
    sql = """
        SELECT jsonb_object_keys(s.trains_map) as t1 
        FROM station_transit_index s 
        JOIN station_transit_index d ON d.station_code = %s 
        WHERE s.station_code = %s 
        AND d.trains_map ? jsonb_object_keys(s.trains_map)
    """
    cur.execute(sql, (dst, src))
    rows = cur.fetchall()
    print(f"Direct trains for {src} to {dst}: {len(rows)}")
    for r in rows:
        print(r[0])
    conn.close()

if __name__ == "__main__":
    check()
