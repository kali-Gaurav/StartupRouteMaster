import sqlite3
import sys
import os

def verify_quotas():
    db_path = 'backend/database/transit_graph.db'
    conn = sqlite3.connect(db_path)
    try:
        res = conn.execute("SELECT train_no, date, quota_mask FROM train_quota_masks LIMIT 3").fetchall()
        print(f"Sample Quota Masks: {res}")
        if res:
            print("🎉 SUCCESS: Quota bitmask index is functional.")
    finally:
        conn.close()

if __name__ == "__main__":
    verify_quotas()
