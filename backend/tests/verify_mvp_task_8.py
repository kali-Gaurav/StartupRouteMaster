import asyncio
import sys
import os
from datetime import datetime, timedelta
from sqlalchemy import text

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.session import SessionLocal, engine_transit
from core.route_engine.orchestrator import UnifiedRoutingOrchestrator
from core.route_engine.constraints_engine import ConstraintsEngine
from core.data_structures import Route, RouteSegment

async def verify_task_8():
    print("\n>>> STARTING VERIFICATION: MVP TASK 8 (CANCELLATION PRUNING)")
    
    db_user = SessionLocal()
    
    # 1. Setup - Ensure table exists and clear any old data for test train
    train_no = "TEST_CANCEL_123"
    test_date = (datetime.now() + timedelta(days=5)).date()
    date_str = test_date.strftime("%Y-%m-%d")
    
    with engine_transit.connect() as conn:
        conn.execute(text("DELETE FROM cancelled_trains WHERE train_no = :tno"), {"tno": train_no})
        conn.commit()

    # 2. Test initial search (found)
    print(f"  Testing initial state (Train {train_no} not cancelled)...")
    
    orchestrator = UnifiedRoutingOrchestrator(MagicMock())
    constraints = ConstraintsEngine.initialize_constraints("comfort", test_date)
    
    # Mock some routes
    r1 = Route()
    r1.add_segment(RouteSegment(trip_id=1, departure_stop_id=1, arrival_stop_id=2, 
                                 departure_time=datetime.now(), arrival_time=datetime.now(),
                                 duration_minutes=100, distance_km=100.0, train_number=train_no))
    r1.score = 100.0
    
    # Before cancellation
    filtered_before = await orchestrator._filter_cancelled_trains([r1], datetime.combine(test_date, datetime.min.time()), engine_transit)
    print(f"    Routes before cancellation: {len(filtered_before)}")
    assert len(filtered_before) == 1
    
    # 3. Apply Cancellation (Subtask 8.2)
    print(f"\n  Applying cancellation for Train {train_no} on {date_str}...")
    with engine_transit.connect() as conn:
        conn.execute(text(
            "INSERT INTO cancelled_trains (train_no, travel_date, reason) VALUES (:tno, :dt, :r)"
        ), {"tno": train_no, "dt": date_str, "r": "Test Pruning"})
        conn.commit()
        
    # 4. Test search again (pruned)
    print(f"  Testing state after cancellation...")
    filtered_after = await orchestrator._filter_cancelled_trains([r1], datetime.combine(test_date, datetime.min.time()), engine_transit)
    print(f"    Routes after cancellation: {len(filtered_after)}")
    
    assert len(filtered_after) == 0
    print("    SUCCESS: Route containing cancelled train was pruned.")
    
    # 5. Verify different date (not pruned)
    print(f"\n  Verifying different date (Train should still run)...")
    diff_date = test_date + timedelta(days=1)
    filtered_diff = await orchestrator._filter_cancelled_trains([r1], datetime.combine(diff_date, datetime.min.time()), engine_transit)
    assert len(filtered_diff) == 1
    print("    SUCCESS: Cancellation is date-specific.")

    # 6. Cleanup
    with engine_transit.connect() as conn:
        conn.execute(text("DELETE FROM cancelled_trains WHERE train_no = :tno"), {"tno": train_no})
        conn.commit()

    print("\n✅ ALL MVP TASK 8 SUBTASKS VERIFIED!")

from unittest.mock import MagicMock
if __name__ == "__main__":
    asyncio.run(verify_task_8())
