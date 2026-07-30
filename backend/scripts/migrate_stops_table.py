import sys
import os
from sqlalchemy import text

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from database.session import SessionTransit

async def migrate_stops():
    from core.infrastructure.container import container
    await container.get("db")
    
    db = SessionTransit()
    try:
        logger = print
        print("Checking for missing columns in 'stops' table...")
        
        # Check if columns exist
        res = db.execute(text("PRAGMA table_info(stops)")).fetchall()
        columns = [r[1] for r in res]
        
        if "centrality_score" not in columns:
            print("Adding 'centrality_score' column...")
            db.execute(text("ALTER TABLE stops ADD COLUMN centrality_score FLOAT DEFAULT 0.0"))
        
        if "zone" not in columns:
            print("Adding 'zone' column...")
            db.execute(text("ALTER TABLE stops ADD COLUMN zone VARCHAR(10)"))
            
        db.commit()
        print("✅ Migration complete.")
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(migrate_stops())
