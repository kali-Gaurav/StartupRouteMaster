import asyncio
from database.session import initialize_database_pools, SessionTransit
from sqlalchemy import text

async def fix_schema():
    await initialize_database_pools()
    db = SessionTransit()
    try:
        db.execute(text('ALTER TABLE station_realtime_heartbeats ADD COLUMN guardian_score FLOAT DEFAULT 1.0'))
        db.commit()
    except Exception:
        pass # Ignore if already exists

    try:
        db.execute(text('ALTER TABLE station_realtime_heartbeats ADD COLUMN active_agents_count INTEGER DEFAULT 0'))
        db.commit()
        print("Column active_agents_count added successfully.")
    except Exception as e:
        print(f"Error adding active_agents_count: {e}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(fix_schema())
