import logging
import uuid
from typing import cast
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from database.session import get_db
from database.models import User, Booking, EscrowStatus
from api.dependencies import get_current_user
from services.credit_service import BUNDLE_PACKS, credit_service
from datetime import datetime

logger = logging.getLogger("credits-api")
router = APIRouter(prefix="/credits", tags=["credits"])

@router.get("/balance")
async def get_balance(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    [Task 42.D] Fetch current credit balance (Paid + Bonus).
    """
    return credit_service.get_user_balance(db, cast(str, user.id))

@router.post("/purchase")
async def purchase_credits(
    bundle_id: str = Body(..., embed=True),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    [Task 42.D] Initiate a Credit Top-up.
    Creates a CREDIT_TOPUP booking record for the UPI gateway to process.
    """
    bundle = BUNDLE_PACKS.get(bundle_id)
    if not bundle:
        raise HTTPException(status_code=400, detail="Invalid bundle selection.")

    # Generate UPI URI for the bundle price
    from services.merchant_vpa_service import merchant_vpa_service
    from utils.payments import generate_upi_uri, get_unique_paisa_amount
    
    merchant = merchant_vpa_service.get_next_vpa()
    total_amount = get_unique_paisa_amount(bundle["price"], db, merchant["vpa"])
    
    booking_id = f"TOPUP_{uuid.uuid4().hex[:8].upper()}"
    txn_note = f"RM_TOPUP_{booking_id[-4:]}"
    
    upi_link, upi_tx_id = generate_upi_uri(
        merchant_vpa=merchant["vpa"],
        merchant_name=merchant["name"],
        amount=total_amount,
        transaction_note=txn_note
    )
    
    # Create the Top-up Record (using Booking table for consistency)
    new_topup = Booking(
        id=booking_id,
        user_id=user.id,
        service_type="CREDIT_TOPUP",
        escrow_status=EscrowStatus.CREATED,
        escrow_message=f"Awaiting ₹{total_amount} for {bundle['credits']} credits.",
        amount_paid=total_amount,
        merchant_vpa=merchant["vpa"],
        upi_tx_id=upi_tx_id,
        booking_details={"bundle_id": bundle_id, "credits": bundle["credits"]},
        created_at=datetime.utcnow()
    )
    db.add(new_topup)
    db.commit()
    
    return {
        "id": new_topup.id,
        "amount": total_amount,
        "upi_url": upi_link,
        "bundle": bundle_id,
        "credits": bundle["credits"]
    }
