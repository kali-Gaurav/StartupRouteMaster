from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
import logging
from datetime import date
from pydantic import BaseModel

from database import get_db
from database.models import User
from api.dependencies import get_current_user
from services.reconciliation_service import ReconciliationService

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
        
    service = ReconciliationService(db)
    results = service.reconcile_nightly_batch()
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
    target_date: date = None,
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
