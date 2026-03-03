import asyncio
import logging
from datetime import datetime
import sys
import os

# Ensure backend package is importable
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from core.route_engine.engine import RailwayRouteEngine

logging.basicConfig(level=logging.INFO)

async def test_build():
    engine = RailwayRouteEngine()
    
    # Target date
    target_date = datetime.now()
    print(f"Testing graph build and SAVE for {target_date}...")
    
    try:
        # This will build and SAVE the snapshot
        graph = await engine._get_current_graph(target_date)
        print(f"Success! Built and SAVED graph with {len(graph.snapshot.stop_cache)} stops.")
        
        # Check if StationHealthIndex was populated
        from database.session import SessionLocal
        from database.models import StationHealthIndex
        session = SessionLocal()
        count = session.query(StationHealthIndex).filter(StationHealthIndex.date == target_date.date()).count()
        print(f"StationHealthIndex records found: {count}")
        session.close()
        
    except Exception as e:
        print(f"Build failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_build())
