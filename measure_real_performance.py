import asyncio
import time
import logging
from datetime import datetime, timedelta
import os
import sys

# Set up logging to be quiet
logging.basicConfig(level=logging.ERROR)

# Add backend to sys.path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from core.route_engine import RouteEngine
from core.route_engine.constraints import RouteConstraints

async def measure():
    engine = RouteEngine()
    # Force initialization (loads graph)
    print("Initializing engine...")
    start_init = time.time()
    try:
        await engine.initialize()
    except Exception as e:
        print(f"Error during initialization: {e}")
    print(f"Engine initialized in {time.time() - start_init:.2f}s")

    test_cases = [
        ("NDLS", "CSMT"),
        ("NDLS", "HWH"),
        ("BCT", "PUNE"),
        ("MAS", "SBC"),
        ("NDLS", "MAS"),
    ]

    departure_date = datetime.now() + timedelta(days=1)
    departure_date = departure_date.replace(hour=8, minute=0, second=0, microsecond=0)

    constraints = RouteConstraints(max_results=5)

    print("\n{: <6} {: <6} {: <8} {: <10}".format("From", "To", "Routes", "Time (s)"))
    print("-" * 35)

    for src, dst in test_cases:
        start = time.time()
        try:
            routes = await engine.search_routes(src, dst, departure_date, constraints)
            elapsed = time.time() - start
            print("{: <6} {: <6} {: <8} {: <10.3f}".format(src, dst, len(routes), elapsed))
        except Exception as e:
            print("{: <6} {: <6} {: <8} {: <10}".format(src, dst, "ERROR", str(e)[:10]))

if __name__ == "__main__":
    asyncio.run(measure())
