import sqlite3
from datetime import date

db_path = 'backend/database/transit_graph.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check if DAILY exists
cursor.execute("SELECT COUNT(*) FROM calendar WHERE service_id = 'DAILY'")
count = cursor.fetchone()[0]

if count == 0:
    print("Inserting DAILY service into calendar table...")
    cursor.execute("""
        INSERT INTO calendar (service_id, monday, tuesday, wednesday, thursday, friday, saturday, sunday, start_date, end_date)
        VALUES ('DAILY', 1, 1, 1, 1, 1, 1, 1, '2020-01-01', '2030-12-31')
    """)
    conn.commit()
    print("Done.")
else:
    print("DAILY service already exists.")

conn.close()
