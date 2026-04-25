from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
import logging
from datetime import date
from typing import Optional
from pydantic import BaseModel

from database import get_db
from database.models import User, UnclaimedFund
from api.dependencies import get_current_user
from services.finance.reconciliation_orchestrator import get_reconciliation_orchestrator

router = APIRouter(prefix="/admin/reconciliation", tags=["admin_reconciliation"])
logger = logging.getLogger(__name__)

class RollbackRequest(BaseModel):
    transaction_id: str
    reason: str

@router.post("/trigger_nightly_batch")
async def trigger_nightly_batch(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Admin endpoint to manually trigger the nightly reconciliation batch."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
        
    orchestrator = get_reconciliation_orchestrator(db)
    # The new orchestrator uses process_pending_reconciliations logic
    results = await orchestrator.reconcile_limbo_funds()
    return {"success": True, "details": results}

@router.post("/upload_statement")
async def upload_bank_statement(
    format_type: str = "AUTO",
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Task 8.1 & 8.8: Upload CSV and parse multiple formats."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
        
    content = await file.read()
    service = ReconciliationService(db)
    
    try:
        transactions = service.parse_bank_csv(content.decode('utf-8'), format_type)
        from database.models import BankTransaction
        
        saved_count = 0
        for tx in transactions:
            # Avoid inserting duplicates
            exists = db.query(BankTransaction).filter(BankTransaction.utr == tx["utr"]).first()
            if not exists:
                new_tx = BankTransaction(
                    utr=tx["utr"],
                    amount=tx["amount"],
                    raw_payload=tx["raw"],
                    bank_name=format_type,
                    status="PENDING"
                )
                db.add(new_tx)
                saved_count += 1
                
        db.commit()
        return {"success": True, "parsed": len(transactions), "newly_saved": saved_count}
    except Exception as e:
        logger.error(f"Failed to parse statement: {e}")
        raise HTTPException(status_code=400, detail="Invalid CSV format")

@router.get("/profit_loss")
async def get_profit_loss(
    target_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Task 8.5: Daily Profit/Loss statement."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
        
    target_date = target_date or date.today()
    service = ReconciliationService(db)
    return {"success": True, "report": service.generate_pl_report(target_date)}

@router.get("/discrepancy_report")
async def get_discrepancy_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Task 8.6: Get unmatched funds."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
        
    service = ReconciliationService(db)
    return {"success": True, "report": service.get_discrepancy_report()}

@router.post("/rollback")
async def rollback_transaction(
    req: RollbackRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Task 8.10: Rollback incorrectly verified transactions."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
        
    service = ReconciliationService(db)
    res = service.rollback_transaction(str(current_user.id), req.transaction_id, req.reason)
    if not res["success"]:
        raise HTTPException(status_code=400, detail=res["message"])
    return res
@router.get("/limbo_transactions")
async def get_limbo_transactions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """[Task 49.2] Fetch unclaimed and unmatched bank payments from the new FinOps store."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    limbo = db.query(UnclaimedFund).filter(UnclaimedFund.status == "UNCLAIMED").order_by(UnclaimedFund.received_at.desc()).all()
    return {"success": True, "data": limbo}

@router.post("/manual_settle_agent/{agent_id}")
async def manual_settle_agent(
    agent_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """[Task 44.4] Manually trigger settlement batch via the new SettlementEngine."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    from services.finance.settlement_engine import settlement_engine
    await settlement_engine.run_daily_settlement(db) # In production we might filter by agent_id
    return {"success": True, "message": "Settlement sequence initiated via FinOps Engine."}

@router.post("/emergency_unlock")
async def emergency_unlock(
    current_user: User = Depends(get_current_user)
):
    """[Task 4.9] Override PLATFORM_FINANCIAL_LOCK and resume operations."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    from services.multi_layer_cache import multi_layer_cache
    await multi_layer_cache.clear_all_caches() # Aggressive recovery
    logger.critical(f"🏁 [SECURITY] Platform manually UNLOCKED and CACHE CLEANED by Admin: {current_user.id}")
    
    from services.ws_manager import ws_manager
    await ws_manager.broadcast_global("🟢 SYSTEM ALERT: Platform Outage Resolved. Operations Resumed.", "SYSTEM_STATUS")
    
    return {"success": True, "message": "Global financial lock cleared and cache flushed."}
