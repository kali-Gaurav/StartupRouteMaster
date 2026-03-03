import asyncio
import logging
import sys
import os
from datetime import datetime, timedelta

# Ensure backend package is importable
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from core.route_engine.engine import RailwayRouteEngine
from core.route_engine.constraints import RouteConstraints
from database.session import SessionLocal
from database.models import RouteSearchLog, Stop
from sqlalchemy import func

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("precompute-worker")

async def precompute_routes():
    engine = RailwayRouteEngine()
    session = SessionLocal()
    
    # 1. Identify Top Pairs (TODO #37)
    try:
        top_pairs = session.query(RouteSearchLog.src, RouteSearchLog.dst, func.count(RouteSearchLog.id)).group_by(RouteSearchLog.src, RouteSearchLog.dst).order_by(func.count(RouteSearchLog.id).desc()).limit(100).all()
    except:
        top_pairs = []
    
    if not top_pairs:
        logger.info("No search history found. Using default major city pairs.")
        default_pairs = [("NDLS", "MAS"), ("NDLS", "BCT"), ("NDLS", "HWH"), ("BCT", "MAS"), ("BCT", "HWH"), ("MAS", "HWH"), ("NDLS", "SBC"), ("NDLS", "PNBE"), ("NDLS", "LKO")]
    else:
        default_pairs = [(p[0], p[1]) for p in top_pairs]

    target_date = datetime.now()
    constraints = RouteConstraints(max_results=5)
    
    # 2. Warm up graph
    logger.info(f"Warming up graph for {target_date.date()}...")
    await engine._get_current_graph(target_date)
    
    # 3. Precompute and Cache (TODO #38 & #39)
    logger.info(f"Precomputing {len(default_pairs)} pairs...")
    
    for src_code, dst_code in default_pairs:
        try:
            src_stop = session.query(Stop).filter(Stop.code == src_code).first()
            dst_stop = session.query(Stop).filter(Stop.code == dst_code).first()
            
            if not src_stop or not dst_stop:
                continue
                
            logger.info(f"Precomputing {src_code} -> {dst_code}...")
            routes = await engine.find_routes(src_stop.id, dst_stop.id, target_date, constraints)
            logger.info(f"  - Found {len(routes)} routes.")
            
        except Exception as e:
            logger.error(f"Failed to precompute {src_code}->{dst_code}: {e}")

    session.close()
    logger.info("🚀 Precomputation Finished.")

if __name__ == "__main__":
    asyncio.run(precompute_routes())
