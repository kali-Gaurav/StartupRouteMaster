import asyncio
import logging
import sys
import os

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.session import initialize_database_pools, SessionUser, UserBase
from database import models # Register models
from sqlalchemy import inspect, text

async def main():
    logging.basicConfig(level=logging.INFO)
    await initialize_database_pools()
    
    db = SessionUser()
    try:
        # 1. Create tables if they don't exist
        # UserBase.metadata.create_all(db.get_bind()) # This won't work easily if we want to be safe
        
        # 2. Check if specific tables exist and create them if missing
        inspector = inspect(db.get_bind())
        existing_tables = inspector.get_table_names()
        
        target_tables = [
            "intelligence_search_events",
            "intelligence_recommendation_events",
            "intelligence_conversion_events",
            "intelligence_safety_events",
            "intelligence_metrics",
            "global_intelligence_state"
        ]
        
        for table in target_tables:
            if table not in existing_tables:
                print(f"Creating table: {table}")
                # We can't easily call create_all for just one table without filtering the metadata
                # but since we are in a script, let's just try to create all and ignore existing
                try:
                    # Filter metadata to only include what we want if we want to be surgical
                    # or just run it and let SQLAlchemy handle it
                    UserBase.metadata.create_all(db.get_bind())
                    print(f"Successfully ensured {table} exists (or was already there).")
                except Exception as e:
                    print(f"Error ensuring {table}: {e}")
        
        # 3. Check for 'conversion_events' and 'safety_events' vs 'intelligence_*' versions
        # If conversion_events exists, maybe we should alias or migrate?
        # For now, we just want the intelligence_* ones to exist as expected by models.py
        
        print("\nFinal table check:")
        inspector = inspect(db.get_bind())
        for t in sorted(inspector.get_table_names()):
            if "intel" in t or t in ["search_events", "recommendation_events", "conversion_events", "safety_events"]:
                print(f" - {t}")
                
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
