
import sqlite3
import os

db_path = "backend/database/transit_graph.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("--- Hub Scoring Audit ---")
    
    # 1. Stats
    cursor.execute("SELECT COUNT(*), AVG(connectivity_score), MAX(connectivity_score) FROM stops WHERE connectivity_score > 0")
    row = cursor.fetchone()
    print(f"Stations with scores: {row[0]}")
    print(f"Average score: {row[1]:.2f}")
    print(f"Max score: {row[2]:.2f}")
    
    # 2. Major Hubs
    major_codes = ['NDLS', 'CSMT', 'MAS', 'HWH', 'SBC', 'PNBE', 'LKO', 'ADI', 'BCT', 'JP', 'KOTA']
    placeholders = ','.join(['?'] * len(major_codes))
    query_majors = f"SELECT code, name, connectivity_score, hub_type FROM stops WHERE code IN ({placeholders}) ORDER BY connectivity_score DESC"
    cursor.execute(query_majors, major_codes)
    print("\n--- Scores for Known Major Hubs ---")
    for r in cursor.fetchall():
        print(f"{r['code']:<6} | {r['name']:<25} | Score: {r['connectivity_score']:.2f} | Type: {r['hub_type']}")
    
    # 3. Top 10 Overall
    query_top = "SELECT code, name, connectivity_score, hub_type FROM stops ORDER BY connectivity_score DESC LIMIT 10"
    cursor.execute(query_top)
    print("\n--- Top 10 Scoring Stations Overall ---")
    for r in cursor.fetchall():
        print(f"{r['code']:<6} | {r['name']:<25} | Score: {r['connectivity_score']:.2f} | Type: {r['hub_type']}")
    
    conn.close()
else:
    print("DB not found")
