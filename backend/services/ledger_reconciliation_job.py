import logging
from sqlalchemy.orm import Session
from database.session import SessionUser
from database.models import User, FraudAlert
from services.ledger_service import ledger_service
from services.fraud_service import fraud_service

logger = logging.getLogger("ledger-reconciliation")

class LedgerReconciliationJob:
    """
    [Task 49.4 & 49.8] Nightly Audit Job.
    Compares Walllet Balance vs Ledger Parity.
    """
    @staticmethod
    def run_recon(db: Session):
        logger.info("🕵️ Starting Platform-Wide Financial Reconciliation...")
        
        # 1. Integrity Check [49.9]
        if not ledger_service.verify_ledger_integrity(db):
            logger.critical("🛑 LEDGER INTEGRITY FAILURE! Halting and Alerting Admins.")
            # Trigger Global System Fraud Alert
            fraud_service.create_alert(db, None, "LEDGER_TAMPER_DETECTED", "CRITICAL", {"reason": "Hash Chain Break"})
            return
            
        # 2. Per-User Parity [49.4]
        users = db.query(User).filter(User.is_active == True).all()
        variance_count = 0
        
        for u in users:
            # Note: Credits to INR conversion logic needed for production parity
            # Assume 1 Credit = ₹39.9
            ledger_balance_inr = ledger_service.get_account_balance(db, "USER_WALLET", user_id=u.id)
            wallet_credits = u.credits or 0
            wallet_value_inr = wallet_credits * 39.9
            
            variance = abs(ledger_balance_inr - wallet_value_inr)
            
            if variance > 0.1: # Allow for tiny float rounding [49.8]
                logger.warning(f"🚨 Variance Detected for {u.email}: ₹{variance:.2f}")
                fraud_service.create_alert(
                    db, u.id, "FINANCIAL_VARIANCE", "HIGH", 
                    {"ledger": ledger_balance_inr, "wallet_value": wallet_value_inr}
                )
                variance_count += 1
                
        logger.info(f"✅ Recon Finished. Total Variance Alerts: {variance_count}")

recon_job = LedgerReconciliationJob()
