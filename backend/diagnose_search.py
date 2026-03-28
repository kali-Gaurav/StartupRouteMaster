
import pickle
import os
from datetime import datetime, timedelta

snapshot_path = "backend/snapshots/graph_snapshot_20260330.pkl"
with open(snapshot_path, "rb") as f:
    snapshot = pickle.load(f)

from core.route_engine.graph import TimeDependentGraph
graph = TimeDependentGraph(snapshot=snapshot)
graph.stop_cache = snapshot.stop_cache

mas = graph.get_stop_by_code("MAS")
print(f"📍 MAS Stop ID: {mas.id if mas else 'Not Found'}")

if mas:
    # Test for Monday (Weekday 0)
    test_date = datetime(2026, 3, 30, 0, 0)
    print(f"📅 Testing Date: {test_date} (Weekday: {test_date.weekday()})")
    
    deps = graph.get_departures_from_stop(mas.id, test_date, lookahead=1440)
    print(f"🚄 Found {len(deps)} departures from MAS on {test_date.date()}")
    
    if len(deps) == 0:
        print("❌ ZERO DEPARTURES found. Analyzing raw data...")
        s_idx = snapshot._stop_id_map.get(mas.id)
        if s_idx is not None:
            off, count = snapshot._departures_index[s_idx]
            data = snapshot._departures_data[off : off + count]
            print(f"📊 Raw data entries for MAS: {count}")
            for ts, tid in data[:10]:
                dt = datetime.fromtimestamp(ts)
                print(f"   - Trip {tid} at {dt} (WD: {dt.weekday()})")
    
    # Check Segments for a trip
    if deps:
        tid = deps[0][1]
        segs = graph.get_trip_segments(tid)
        print(f"🛤️ Trip {tid} has {len(segs)} segments.")
        dest_code = "SBC"
        sbc = graph.get_stop_by_code(dest_code)
        print(f"📍 SBC Stop ID: {sbc.id if sbc else 'Not Found'}")
        
        found_sbc = False
        for s in segs:
            if s.arrival_stop_id == sbc.id:
                print(f"🎯 FOUND {dest_code} in Trip {tid} at index {segs.index(s)}")
                found_sbc = True
        if not found_sbc:
            print(f"❌ {dest_code} NOT FOUND in Trip {tid} segments.")
