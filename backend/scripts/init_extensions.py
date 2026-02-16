import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

def init_extensions():
    load_dotenv('backend/.env')
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("Error: DATABASE_URL not found")
        return

    engine = create_engine(db_url)
    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gin;"))
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist;"))
            conn.commit()
            print("Successfully initialized PostgreSQL extensions (postgis, pg_trgm, btree_gin/gist)")
    except Exception as e:
        print(f"Error initializing extensions: {e}")

if __name__ == "__main__":
    init_extensions()
