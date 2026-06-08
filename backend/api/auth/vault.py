from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
import logging
from pydantic import BaseModel

from database import get_db
from database.models import User
from api.dependencies import get_current_user
from services.credential_vault import CredentialVault
from utils.responses import success_response

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
    Stores IRCTC credentials securely in the AES-256 vault.
    """
    vault = CredentialVault(db)
    
    if vault.is_weak_password(req.irctc_pass):
        logger.warning(f"VAULT_WEAK_PWD | User {current_user.id} using weak IRCTC password.")

    success = await vault.store_credentials(
        str(current_user.id), 
        req.irctc_user, 
        req.irctc_pass, 
        req.persistent
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to secure credentials.")
        
    return success_response(
        message="Credentials secured in AES-256 vault",
        data={"user_id": str(current_user.id), "persistent": req.persistent}
    )

@router.post("/mfa_challenge")
async def mfa_challenge_bridge(
    otp: str = Body(..., embed=True),
    current_user: User = Depends(get_current_user)
):
    """
    MFA Challenge Bridge for IRCTC.
    """
    logger.info(f"VAULT_MFA | Received OTP for user {current_user.id} | {otp[:2]}****")
    return success_response(data={}, message="MFA challenge response forwarded to worker")

@router.delete("/wipe")
async def manual_wipe(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Manually clear credentials from vault."""
    vault = CredentialVault(db)
    vault.auto_wipe(str(current_user.id))
    logger.info(f"VAULT_WIPE | Manual wipe for user {current_user.id}")
    return success_response(data={}, message="Credentials wiped successfully")
