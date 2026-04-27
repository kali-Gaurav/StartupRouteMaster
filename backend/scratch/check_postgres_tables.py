
import os
from sqlalchemy import create_engine, text
from database.config import Config

url = Config.GET_SQLALCHEMY_URL("user", is_async=False)
print(f"Connecting to: {url}")
engine = create_engine(url)
with engine.connect() as conn:
    try:
        res = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table';"))
        print(f"SQLite Tables: {res.fetchall()}")
    except:
        try:
            res = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';"))
            print(f"Postgres Tables: {[r[0] for r in res.fetchall()]}")
        except Exception as e:
            print(f"Error: {e}")
