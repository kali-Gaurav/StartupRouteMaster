
import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.append(str(backend_root))

from database.session import initialize_database_pools, SessionTransit
from sqlalchemy import text

async def check():
    await initialize_database_pools()
    s = SessionTransit()
    try:
        r = s.execute(text('SELECT MIN(start_date), MAX(end_date) FROM calendar')).fetchone()
        print(f"Date Range: {r}")
        
        # Also check count of stop_times
        c = s.execute(text('SELECT COUNT(*) FROM stop_times')).scalar()
        print(f"Stop Times Count: {c}")
        
        # Check weekdays
        weekdays = s.execute(text("SELECT SUM(monday), SUM(tuesday), SUM(wednesday), SUM(thursday), SUM(friday), SUM(saturday), SUM(sunday) FROM calendar")).fetchone()
        print(f"Weekday Service Distribution: {weekdays}")
        
    finally:
        s.close()

if __name__ == "__main__":
    asyncio.run(check())
