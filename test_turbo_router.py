import asyncio
import os
import sys
from datetime import datetime, timedelta

# Add backend to sys.path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from core.route_engine.turbo_router import TurboRouter
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_turbo():
    router = TurboRouter()
    
    source = "NDLS"
    dest = "BCT"
    date = datetime.now() + timedelta(days=1)
    
    logger.info(f"--- Testing TurboRouter: {source} -> {dest} ---")
    
    routes = router.find_routes(source, dest, date)
    
    for i, r in enumerate(routes):
        print(f"\nRoute {i+1}: {r['type']} ({r['transfers']} transfers)")
        for leg in r['legs']:
            print(f"  - Train {leg['train_no']}: {leg['from']} ({leg['dep']}) -> {leg['to']} ({leg['arr']})")

if __name__ == "__main__":
    test_turbo()
