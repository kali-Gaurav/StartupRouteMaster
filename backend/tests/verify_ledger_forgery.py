import asyncio
import logging
import sys
import os

# Set PYTHONPATH
sys.path.append(os.getcwd())

from core.nexus.financial.signer import ledger_signer
from core.nexus.financial.alerts import financial_alerts

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("verify-forgery")

async def run_forgery_test():
    logger.info("🧪 Launching NEXUS-4.8: Financial Forgery Stress Check...")
    
    # 1. Simulate a signature mismatch
    logger.info("🛡️ Testing Task 4.6: Cryptographic Signature Integrity...")
    
    mock_data = "debit:acc1|credit:acc2|amount:100.0"
    mock_id = 12345
    
    # Generate valid signature
    valid_sig = await ledger_signer.generate_signature(mock_id, mock_data)
    
    # Verify valid
    is_valid = await ledger_signer.verify_signature(mock_id, mock_data, valid_sig)
    
    if is_valid:
        logger.info("✅ SUCCESS: Valid signature correctly verified.")
    else:
        logger.error("❌ FAILURE: Valid signature failed to verify.")
        return 1

    # Simulate TAMPERING
    tampered_data = "debit:acc1|credit:acc2|amount:999.0" # Altered amount
    
    is_valid_tampered = await ledger_signer.verify_signature(mock_id, tampered_data, valid_sig)
    
    if not is_valid_tampered:
         logger.info("✅ SUCCESS: Tampered signature correctly REJECTED.")
    else:
         logger.error("❌ FAILURE: Tampered data was accepted as valid! Security risk.")
         return 1

    # 2. Simulate Alert Triggering [Task 4.7]
    logger.info("🛡️ Testing Task 4.7: Financial Alerting Engine...")
    
    from core.nexus.bootstrapper import nexus_boot
    from core.nexus.state import SystemState
    
    nexus_boot.state = SystemState.READY # Mock initial state
    
    await financial_alerts.trigger_tamper_alert("Stress Test Forgery", mock_id)
    
    if nexus_boot.state == SystemState.DEGRADED:
         logger.info("✅ SUCCESS: System State degraded to DEGRADED on tampering event.")
    else:
         logger.error("❌ FAILURE: System State remained READY despite alert.")
         return 1

    logger.info("🎉 Task 4.8 VERIFIED: Financial Integrity Layer is Deeply Hardened.")
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(run_forgery_test()))
