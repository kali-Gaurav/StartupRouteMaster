from sqlalchemy import create_engine, inspect
import os
from dotenv import load_dotenv

load_dotenv('backend/.env')
db_url = os.getenv('DATABASE_URL')
# Use synchronous URL
if db_url and 'postgresql+asyncpg' in db_url:
    db_url = db_url.replace('postgresql+asyncpg', 'postgresql+psycopg2')

engine = create_engine(db_url)
inspector = inspect(engine)
tables = inspector.get_table_names()

print("Tables in Database:")
for table in sorted(tables):
    print(f"- {table}")

# Check specifically for intelligence_search_events
if 'intelligence_search_events' in tables:
    print("\nColumns in intelligence_search_events:")
    columns = inspector.get_columns('intelligence_search_events')
    for col in columns:
        print(f"  - {col['name']} ({col['type']})")
else:
    print("\n intelligence_search_events table NOT FOUND!")
