import sys
import os
import json
import pickle

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from database.session import SessionTransit
from sqlalchemy import text

GRAPH_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'safety_graph.bin')

def build_safety_graph():
    print("🕸️ Building Offline Safety Graph DB...")
    db = SessionTransit()
    try:
        # 1. Fetch all stations and their nearest authorities
        stations = db.execute(text("SELECT id, name, latitude, longitude, nearest_authority_id FROM stations")).fetchall()
        
        # 2. Fetch all authorities
        authorities = db.execute(text("SELECT id, name, type, contact_number, latitude, longitude FROM emergency_authorities")).fetchall()
        
        # 3. Construct Graph
        # We store this as a dictionary for O(1) station-to-authority lookups
        graph = {
            "stations": {s[0]: {"name": s[1], "lat": s[2], "lng": s[3], "auth_id": s[4]} for s in stations},
            "authorities": {a[0]: {"name": a[1], "type": a[2], "phone": a[3], "lat": a[4], "lng": a[5]} for a in authorities}
        }
        
        # 4. Serialize to Binary (using pickle for complex dict, or we could use custom struct)
        # For a graph, a serialized dict is highly efficient for O(1) access
        os.makedirs(os.path.dirname(GRAPH_FILE), exist_ok=True)
        with open(GRAPH_FILE, 'wb') as f:
            pickle.dump(graph, f)
            
        print(f"✅ Safety Graph built: {GRAPH_FILE}")
        print(f"📊 Nodes: {len(stations)} Stations, {len(authorities)} Authorities")
        print(f"🗜️ Size: {os.path.getsize(GRAPH_FILE) / 1024:.2f} KB")
        
    finally:
        db.close()

if __name__ == "__main__":
    build_safety_graph()
