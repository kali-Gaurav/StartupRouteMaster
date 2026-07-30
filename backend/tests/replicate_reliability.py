
import sqlite3
import random
from datetime import datetime, timedelta

db_path = "backend/database/transit_graph.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("🏁 Generating Mock Reliability Data...")

# 1. Clear existing updates
cursor.execute("DELETE FROM train_live_updates")

# 2. Get 200 trips to mock data for
cursor.execute("SELECT id, train_no FROM trips LIMIT 200")
trips = cursor.fetchall()

updates = []
now = datetime.now()

# Define per-train performance profiles (Stable vs Chaotic)
profiles = {} # tid -> (avg_delay, variance)
for tid, t_no in trips:
    if str(t_no).startswith("12") or str(t_no).startswith("22"): # Express
        profiles[t_no] = (random.randint(5, 30), 10)
    else: # Passenger/Slow
        profiles[t_no] = (random.randint(60, 240), 60)

for tid, t_no in trips:
    p_avg, p_var = profiles[t_no]
    for i in range(25): # 25 historical points per train
        delay = max(0, int(random.gauss(p_avg, p_var)))
        recorded_at = now - timedelta(hours=i * 6)
        updates.append((t_no, delay, recorded_at.strftime("%Y-%m-%d %H:%M:%S")))

cursor.executemany("""
    INSERT INTO train_live_updates (train_number, delay_minutes, recorded_at)
    VALUES (?, ?, ?)
""", updates)

print(f"✅ Injected {len(updates)} reliability samples for {len(trips)} trains.")
conn.commit()
conn.close()
