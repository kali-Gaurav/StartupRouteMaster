import sqlite3

def check_trains():
    conn = sqlite3.connect('backend/database/railway_data.db')
    cursor = conn.cursor()
    
    # NDLS = New Delhi, BCT = Mumbai Central (sometimes MMCT)
    # Let's find trains that have both NDLS and BCT in their schedule
    query = """
    SELECT s1.train_no, t.train_name
    FROM train_schedule s1
    JOIN train_schedule s2 ON s1.train_no = s2.train_no
    JOIN trains_master t ON s1.train_no = t.train_no
    WHERE s1.station_code = 'NDLS' AND s2.station_code = 'BCT'
    AND s1.arrival_time < s2.arrival_time
    """
    cursor.execute(query)
    results = cursor.fetchall()
    print(f"Trains from NDLS to BCT: {results}")
    
    if not results:
        # Try MMCT
        query = query.replace("'BCT'", "'MMCT'")
        cursor.execute(query)
        results = cursor.fetchall()
        print(f"Trains from NDLS to MMCT: {results}")

    conn.close()

if __name__ == "__main__":
    check_trains()
