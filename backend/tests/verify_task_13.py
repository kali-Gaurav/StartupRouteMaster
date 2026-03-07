import sys
import os
from sqlalchemy import text

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database.session import SessionTransit

def verify_task_13():
    print("\n>>> Verifying Task 13: Memory Mapped SQLite & WAL Mode (v2)")
    db = SessionTransit()
    
    try:
        # Check MMAP
        res = db.execute(text("PRAGMA mmap_size")).fetchone()
        mmap_val = res[0]
        print(f"  MMAP Size: {mmap_val / (1024*1024):.0f} MB")
        
        # Check Journal Mode
        res = db.execute(text("PRAGMA journal_mode")).fetchone()
        j_mode = res[0].lower()
        print(f"  Journal Mode: {j_mode}")
        
        # Check Synchronous
        res = db.execute(text("PRAGMA synchronous")).fetchone()
        sync_val = res[0]
        print(f"  Synchronous: {sync_val}")

        # Validation: 2147483648 is 2GB. Allow small variance for alignment.
        is_mmap_ok = mmap_val >= 2000000000
        is_wal_ok = j_mode == "wal"
        is_sync_ok = sync_val == 1 # 1 is NORMAL in SQLite

        if is_mmap_ok and is_wal_ok and is_sync_ok:
            print("\n✅ TASK 13 VERIFIED: Memory Mapping and WAL are correctly configured.")
            return True
        else:
            print("\n❌ TASK 13 FAILED: Configuration mismatch.")
            print(f"  Debug: MMAP_OK={is_mmap_ok}, WAL_OK={is_wal_ok}, SYNC_OK={is_sync_ok}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        db.close()

if __name__ == "__main__":
    verify_task_13()
