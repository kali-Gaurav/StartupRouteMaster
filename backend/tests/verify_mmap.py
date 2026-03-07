import sys
import os
import logging
from sqlalchemy import text

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database.session import SessionTransit

logging.basicConfig(level=logging.INFO)

def verify_task_13():
    print("\n>>> Verifying Task 13: Memory Mapped SQLite & WAL Mode")
    db = SessionTransit()
    
    try:
        # Check MMAP
        res = db.execute(text("PRAGMA mmap_size")).fetchone()
        mmap_val = res[0]
        print(f"  MMAP Size: {mmap_val / (1024*1024):.0f} MB")
        
        # Check Journal Mode
        res = db.execute(text("PRAGMA journal_mode")).fetchone()
        j_mode = res[0]
        print(f"  Journal Mode: {j_mode}")
        
        # Check Synchronous
        res = db.execute(text("PRAGMA synchronous")).fetchone()
        sync_val = res[0]
        print(f"  Synchronous: {sync_val}")

        if mmap_val >= 2147483648 and j_mode.upper() == "WAL":
            print("\n✅ TASK 13 VERIFIED: SQLite is fully optimized for memory mapping.")
            return True
        else:
            print("\n❌ TASK 13 FAILED: Pragmas not set correctly.")
            return False
            
    except Exception as e:
        print(f"❌ Error during verification: {e}")
        return False
    finally:
        db.close()

if __name__ == "__main__":
    verify_task_13()
