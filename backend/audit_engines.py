
import asyncio
import logging
import sys
import os
from datetime import datetime

# Assuming this script is in 'backend/'
# Add current directory to sys.path
sys.path.append(os.getcwd())

from database.session import initialize_database_pools, SessionTransit
from core.route_engine.engine import route_engine
from core.route_engine.raptor import OptimizedRAPTOR
from core.route_engine.turbo_router import TurboRouter
from core.route_engine.constraints import RouteConstraints

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def audit_engines():
    print("--- Starting Backend Engines Audit ---")
    await initialize_database_pools()
    
    # Initialize Route Engine (this loads the graph)
    print("[*] Initializing RailwayRouteEngine...")
    try:
        await route_engine.init()
    except Exception as e:
        print(f"Warning: route_engine.init() had issues: {e}")
        # We might still be able to proceed if pools are init'd
    
    # Test OptimizedRAPTOR
    print("\n[*] Testing OptimizedRAPTOR...")
    try:
        # Get graph for today
        now = datetime.now()
        graph = await route_engine._get_current_graph(now)
        
        raptor = OptimizedRAPTOR(max_transfers=2)
        constraints = RouteConstraints()
        
        # Source: 49 (ANDHERI - ADH), Destination: 27 (ABU ROAD - ABR)
        source_id = 49
        dest_id = 27
        
        print(f"Searching routes from ID {source_id} to {dest_id} using RAPTOR...")
        routes = await raptor.find_routes(source_id, dest_id, now, constraints, graph)
        
        print(f"RAPTOR found {len(routes)} routes.")
        for i, route in enumerate(routes[:3]):
            print(f"  Route {i+1}: {len(route.segments)} segments, Score: {route.score}")
            
    except Exception as e:
        print(f"Error testing RAPTOR: {e}")
        import traceback
        traceback.print_exc()

    # Test TurboRouter
    print("\n[*] Testing TurboRouter...")
    try:
        turbo = TurboRouter()
        
        source_code = "ADH"
        dest_code = "ABR"
        
        print(f"Searching routes from {source_code} to {dest_code} using TurboRouter...")
        routes = await turbo.find_routes(source_code, dest_code, datetime.now())
        
        print(f"TurboRouter found {len(routes)} routes.")
        for i, route in enumerate(routes[:3]):
            print(f"  Route {i+1}: Type {route.get('type')}, Duration {route.get('duration')} mins")
            
    except Exception as e:
        print(f"Error testing TurboRouter: {e}")
        import traceback
        traceback.print_exc()

    print("\n--- Backend Engines Audit Complete ---")

if __name__ == "__main__":
    asyncio.run(audit_engines())
