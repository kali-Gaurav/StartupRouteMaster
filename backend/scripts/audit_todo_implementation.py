import sqlite3
import os
import json

def audit_db(db_path, expected_tables):
    if not os.path.exists(db_path):
        return {db_path: "MISSING"}
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    actual_tables = [r[0] for r in c.fetchall()]
    
    report = {}
    for table in expected_tables:
        if table in actual_tables:
            c.execute(f"PRAGMA table_info({table})")
            cols = [f"{r[1]} ({r[2]})" for r in c.fetchall()]
            report[table] = {"status": "EXISTS", "columns": cols}
        else:
            report[table] = {"status": "MISSING"}
    conn.close()
    return report

if __name__ == "__main__":
    print("--- 🔍 COMPREHENSIVE IMPLEMENTATION AUDIT (todo06 & todo07) ---")
    
    # 1. Database Check
    transit_tables = [
        'trip_service_masks', 'train_stop_bitmaps', 'hub_transit_index', 
        'hub_distance_matrix', 'city_clusters', 'station_transit_index',
        'station_rank', 'train_live_updates', 'stop_times'
    ]
    user_tables = [
        'seat_inventory', 'pnr_records', 'profiles', 'user_ai_preferences',
        'rl_feedback_logs', 'route_search_logs'
    ]
    
    transit_report = audit_db('backend/database/transit_graph.db', transit_tables)
    user_report = audit_db('backend/database/user_store.db', user_tables)
    
    print("\n--- [TRANSIT_GRAPH.DB] Verification ---")
    for t, data in transit_report.items():
        status = "✅" if data["status"] == "EXISTS" else "❌"
        print(f"{status} {t}: {data['status']}")
        if data["status"] == "EXISTS":
            print(f"   Cols: {', '.join(data['columns'][:5])}...")

    print("\n--- [USER_STORE.DB] Verification ---")
    for t, data in user_report.items():
        status = "✅" if data["status"] == "EXISTS" else "❌"
        print(f"{status} {t}: {data['status']}")
        if data["status"] == "EXISTS":
            print(f"   Cols: {', '.join(data['columns'][:5])}...")

    # 2. Logic & Script Check
    print("\n--- [SCRIPTS] Optimization Logic Check ---")
    critical_scripts = [
        'backend/scripts/build_service_masks.py',
        'backend/scripts/build_stop_bitmaps.py',
        'backend/scripts/build_hub_shortcuts.py',
        'backend/scripts/build_pruning_index.py'
    ]
    for s in critical_scripts:
        status = "✅" if os.path.exists(s) else "❌"
        print(f"{status} {s}")

    # 3. API V2 Integration Check
    print("\n--- [API V2] Endpoint Check ---")
    v2_files = ['search.py', 'live.py', 'user.py', 'booking.py', 'admin.py']
    for f in v2_files:
        path = f"backend/api/v2/{f}"
        status = "✅" if os.path.exists(path) else "❌"
        print(f"{status} {path}")
