from sqlalchemy import text
import sys
import os

# Ensure backend package is importable
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from database.session import SessionLocal

def inspect():
    session = SessionLocal()
    try:
        print("Columns for train_availability_cache:")
        res = session.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'train_availability_cache'"))
        for row in res:
            print(f"  {row[0]}: {row[1]}")
    finally:
        session.close()

if __name__ == "__main__":
    inspect()
