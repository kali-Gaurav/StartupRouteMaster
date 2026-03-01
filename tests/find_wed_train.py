import sqlite3

def find_wednesday_train():
    conn = sqlite3.connect('backend/database/railway_data.db')
    cursor = conn.cursor()
    
    query = """
    SELECT r.train_no, t.train_name
    FROM train_running_days r
    JOIN trains_master t ON r.train_no = t.train_no
    JOIN train_schedule s1 ON r.train_no = s1.train_no
    JOIN train_schedule s2 ON r.train_no = s2.train_no
    WHERE s1.station_code = 'NDLS' AND s2.station_code = 'BCT'
    AND r.wed = 1
    """
    cursor.execute(query)
    print(f"Wednesday trains NDLS->BCT: {cursor.fetchall()}")
    
    conn.close()

if __name__ == "__main__":
    find_wednesday_train()
