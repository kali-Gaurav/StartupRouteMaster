
import pickle
import numpy as np
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend')))
from core.route_engine.graph import MemMapManager

def audit_tbr_data():
    backend_data = "backend/data"
    index_path = os.path.join(backend_data, "tbr_edge_index.pkl")
    
    if not os.path.exists(index_path):
        print(f"Index not found at {index_path}")
        return

    with open(index_path, "rb") as f:
        edge_index = pickle.load(f)
    
    edges = MemMapManager.load_array("tbr_edges")
    
    print(f"Total trips with transfers: {len(edge_index)}")
    
    # Check a sample trip that has transfers
    sample_tid = list(edge_index.keys())[0]
    stations_in_trip = edge_index[sample_tid]
    print(f"Trip {sample_tid} has transfers at {len(stations_in_trip)} stations.")
    
    for sid, (start, count) in list(stations_in_trip.items())[:2]:
        print(f"  At Station {sid}: {count} transfers starting at index {start}.")
        sample_edges = edges[start : start + min(3, count)]
        for e in sample_edges:
            print(f"    -> To Trip: {e['to_trip_id']}, Wait: {e['wait_time_mins']}m")

    # Check NDLS (5533) hubs
    print(f"\nChecking stations in index...")
    all_stations_with_outbound = set()
    for trip_data in edge_index.values():
        for sid in trip_data.keys():
            all_stations_with_outbound.add(sid)
            
    print(f"Distinct stations acting as transfer hubs: {len(all_stations_with_outbound)}")
    print(f"Is NDLS (5533) a transfer hub? {5533 in all_stations_with_outbound}")
    print(f"Is BPL (1091) a transfer hub? {1091 in all_stations_with_outbound}")

if __name__ == "__main__":
    audit_tbr_data()
