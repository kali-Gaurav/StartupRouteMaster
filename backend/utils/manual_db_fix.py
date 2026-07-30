import sqlite3
import logging
import sys
import os

# Set PYTHONPATH
sys.path.append(os.getcwd())

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("nexus-audit")

def manual_fix():
    logger.info("🧪 Launching NEXUS-AUDIT: Manual Database Schema Enforcement...")
    
    db_path = "database/user_store.db"
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        
        # 1. Create financial_ledger if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS financial_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_uuid TEXT,
                debit_account TEXT,
                credit_account TEXT,
                user_id TEXT,
                amount REAL,
                currency TEXT DEFAULT 'INR',
                transaction_type TEXT,
                metadata_json TEXT,
                previous_row_hash TEXT,
                cumulative_hash TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Verify
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='financial_ledger'")
        if cursor.fetchone():
            logger.info(f"✅ SUCCESS: 'financial_ledger' table verified in {db_path}.")
        else:
            logger.error("🛑 FAILURE: Table still missing after CREATE.")
            
        conn.commit()
    except Exception as e:
        logger.error(f"🛑 AUDIT FAILURE: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    manual_fix()
