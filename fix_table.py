import sqlite3
conn = sqlite3.connect('backend/database/user_store.db')
c = conn.cursor()
try:
    c.execute("ALTER TABLE rl_feedback_logs ADD COLUMN rating INTEGER")
    print("Rating column added.")
except Exception as e:
    print(f"Update failed: {e}")
conn.commit()
conn.close()
