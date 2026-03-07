import sqlite3

db_path = 'backend/database/railway_data.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("PRAGMA table_info(train_fares)")
print("Schema for train_fares:")
for row in cursor.fetchall():
    print(row)

cursor.execute("SELECT * FROM train_fares LIMIT 5")
print("\nSample rows:")
for row in cursor.fetchall():
    print(row)
conn.close()
