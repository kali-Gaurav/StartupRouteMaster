from sqlalchemy import text
from database.session import SessionLocal

session = SessionLocal()
try:
    for table in ['segments', 'trips']:
        print(f"Columns for {table}:")
        res = session.execute(text(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table}'"))
        for row in res:
            print(f"  {row[0]}: {row[1]}")
finally:
    session.close()
