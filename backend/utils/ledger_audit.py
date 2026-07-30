import hashlib
import logging
import sqlite3
import sys

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("nexus.ledger_audit")

def audit_ledger(db_path: str = "user.db"):
    """
    [Task 4.5] Cryptographic Hash Chain Audit.
    Verifies that the ledger chain has not been tampered with.
    """
    logger.info(f"🔍 [NEXUS:AUDIT] Starting Deep Scan: {db_path}...")
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 1. Fetch entries by created_at to follow the chain
        cursor.execute("SELECT id, debit_account, credit_account, amount, transaction_type, user_id, previous_row_hash, cumulative_hash FROM financial_ledger ORDER BY id ASC")
        rows = cursor.fetchall()
        
        if not rows:
             logger.info("✅ Ledger is EMPTY. Genesis state verified.")
             return True
             
        current_hash = "GENESIS"
        error_count = 0
        
        for r in rows:
            # 2. Re-calculate Hash
            # Formula must match ledger_service.py: f"{debit_acc}|{coord_acc}|{amount}|{type}|{user_id}|{prev_hash}"
            data = f"{r['debit_account']}|{r['credit_account']}|{r['amount']}|{r['transaction_type']}|{r['user_id']}|{current_hash}"
            expected_hash = hashlib.sha256(data.encode()).hexdigest()
            
            # 3. Compare with stored Cumulative Hash
            if r["cumulative_hash"] != expected_hash:
                 logger.critical(f"🛑 TAMPER DETECTED: Row {r['id']} Hash Mismatch!")
                 logger.error(f"   Stored: {r['cumulative_hash']}")
                 logger.error(f"   Calculated: {expected_hash}")
                 error_count += 1
            
            # 4. Advance Current Hash for next row
            current_hash = r["cumulative_hash"]
            
        if error_count == 0:
             logger.info(f"✅ SUCCESS: {len(rows)} Entries Verified. Hash Chain Integrity 100%.")
             return True
        else:
             logger.critical(f"❌ AUDIT FAILED: {error_count} corrupt entries found in ledger!")
             return False

    except Exception as e:
        logger.error(f"🚨 Audit process crashed: {e}")
        return False
    finally:
        if 'conn' in locals(): conn.close()

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "user.db"
    if not audit_ledger(path):
         sys.exit(1)
    sys.exit(0)
