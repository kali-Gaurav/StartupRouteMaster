import sqlite3
import os

db_path = os.path.join("database", "storage", "user_store.db")
print(f"Connecting to {db_path}")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
try:
    cursor.execute("ALTER TABLE users RENAME COLUMN supabase_id TO firebase_uid")
    conn.commit()
    print("Successfully renamed column!")
except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
