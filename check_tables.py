import sqlite3
conn = sqlite3.connect('backend/database/user_store.db')
c = conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
print("Tables in user_store.db:", [r[0] for r in c.fetchall()])
conn.close()
