import sys
import os
import asyncio
from datetime import datetime
import logging
from sqlalchemy import text

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.route_engine.engine import RailwayRouteEngine
from database.session import SessionTransit

logging.basicConfig(level=logging.INFO)

async def verify_task_15_debug():
    print("\n>>> Verifying Task 15: Transfer Graph Debug")
    engine = RailwayRouteEngine()
    db = SessionTransit()
    
    target_date = datetime(2026, 3, 8)
    graph = await engine._get_current_graph(target_date)
    
    # 1. Print some sample keys from transfer_graph
    tg = graph.snapshot.transfer_graph
    sample_keys = list(tg.keys())[:10]
    print(f"  Sample Keys in transfer_graph: {sample_keys}")
    
    # 2. Check PGTN ID
    pgt_row = db.execute(text("SELECT id, code FROM stops WHERE code = 'PGT'")).fetchone()
    pgtn_row = db.execute(text("SELECT id, code FROM stops WHERE code = 'PGTN'")).fetchone()
    
    if pgt_row and pgtn_row:
        pgt_id, pgt_code = pgt_row
        pgtn_id, pgtn_code = pgtn_row
        print(f"  DB Check: PGT ID={pgt_id}, PGTN ID={pgtn_id}")
        
        # Check transfer from 142 specifically
        tr_list = tg.get(pgt_id, [])
        print(f"  Transfers for ID {pgt_id}: {[t.station_id for t in tr_list]}")
        
        # Check if 143 (PGTN) is reachable from 142
        reachable = any(t.station_id == pgtn_id for t in tr_list)
        print(f"  Is PGTN ({pgtn_id}) reachable from PGT ({pgt_id})? {reachable}")
        
        if not reachable:
            # Check the DB table content for this ID
            row = db.execute(text("SELECT * FROM transfers WHERE from_stop_id = :fid AND to_stop_id = :tid"), {"fid": pgt_id, "tid": pgtn_id}).fetchone()
            print(f"  DB Table record for {pgt_id}->{pgtn_id}: {row}")

    db.close()

if __name__ == "__main__":
    asyncio.run(verify_task_15_debug())
