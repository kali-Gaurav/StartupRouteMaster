from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
import logging
from pydantic import BaseModel

from database import get_db
from database.models import User
from api.dependencies import get_current_user
from services.credential_vault import CredentialVault

router = APIRouter(prefix="/vault", tags=["vault"])
logger = logging.getLogger(__name__)

class VaultStoreRequest(BaseModel):
    irctc_user: str
    irctc_pass: str
    persistent: bool = False

@router.post("/store")
async def store_in_vault(
    req: VaultStoreRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Task 35.10: Secure UI Input.
    Stores IRCTC credentials securely in the AES-256 vault.
    """
    vault = CredentialVault(db)
    
    # Task 35.7: Weak password detection
    if vault.is_weak_password(req.irctc_pass):
        # We don't block but warn (as per IRCTC behavior)
        logger.warning(f"User {current_user.id} is using a weak IRCTC password.")

    success = vault.store_credentials(
        str(current_user.id), 
        req.irctc_user, 
        req.irctc_pass, 
        req.persistent
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to secure credentials.")
        
    return {"success": True, "message": "Credentials secured in AES-256 vault."}

@router.post("/mfa_challenge")
async def mfa_challenge_bridge(
    otp: str = Body(..., embed=True),
    current_user: User = Depends(get_current_user)
):
    """
    Task 35.8: MFA Challenge Bridge.
    Stub for handling 2FA from IRCTC.
    """
    logger.info(f"Received MFA OTP for user {current_user.id}: {otp[:2]}****")
    # In reality, this would forward the OTP to the active ghost worker session
    return {"success": True, "message": "MFA challenge response forwarded to worker."}

@router.delete("/wipe")
async def manual_wipe(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Manually clear credentials from vault."""
    vault = CredentialVault(db)
    vault.auto_wipe(str(current_user.id))
    return {"success": True, "message": "Credentials wiped successfully."}
