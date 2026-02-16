import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

def apply_optimizations():
    load_dotenv('backend/.env')
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("Error: DATABASE_URL not found in .env")
        return

    print(f"Connecting to database to apply optimizations...")
    engine = create_engine(db_url)
    
    sql_file = 'backend/scripts/database_optimization.sql'
    if not os.path.exists(sql_file):
        print(f"Error: {sql_file} not found")
        return

    with open(sql_file, 'r') as f:
        sql_commands = f.read()

    # Split by explicit COMMIT/BEGIN if needed, but we'll try running the block
    try:
        with engine.connect() as conn:
            # We execute the whole file
            # PostgreSQL can handle multiple statements in a single text() block
            conn.execute(text(sql_commands))
            conn.commit()
            print("Successfully applied database optimizations (Partitioning, MVs, Indexes)")
    except Exception as e:
        print(f"Error applying optimizations: {e}")

if __name__ == "__main__":
    apply_optimizations()
