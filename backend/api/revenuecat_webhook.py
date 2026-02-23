from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session
import hmac
import hashlib
import logging
from datetime import datetime

from backend.config import Config
from backend.database import get_db
from backend.services.subscription_service import SubscriptionService
from backend.services.revenue_cat_verifier import RevenueCatVerifier

router = APIRouter(prefix="/api/revenuecat", tags=["revenuecat"])
logger = logging.getLogger(__name__)

# RevenueCat sends a header 'X-RevenueCat-Signature' containing a webhook signature.
# Reference: https://docs.revenuecat.com/docs/webhooks

@router.post("/webhook")
async def handle_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    signature = request.headers.get("X-RevenueCat-Signature")
    if Config.REVENUECAT_API_KEY and signature:
        expected = hmac.new(
            Config.REVENUECAT_API_KEY.encode("utf-8"),
            body,
            hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise HTTPException(status_code=400, detail="Invalid webhook signature")
    else:
        logger.warning("Webhook received without signature or API key configured")

    payload = await request.json()
    event_type = payload.get("event")
    subscriber = payload.get("subscriber", {})
    app_user_id = subscriber.get("original_app_user_id") or subscriber.get("app_user_id")

    if not app_user_id:
        logger.warning("Webhook without app user id: %s", payload)
        return {"success": False}

    subsvc = SubscriptionService(db)

    # Process events that affect entitlement
    if event_type in ("INITIAL_PURCHASE", "RENEWAL", "RESTORE", "EXPIRATION", "CANCELLATION", "REFUND"):
        ent = subscriber.get("entitlements", {}).get(RevenueCatVerifier.ENTITLEMENT_ID)
        is_active = bool(ent)
        expires = None
        if ent and ent.get("expires_date"):
            from dateutil import parser
            try:
                expires = parser.isoparse(ent.get("expires_date"))
            except:
                expires = None
        # update local subscription
        subsvc.set_subscription(
            user_id=app_user_id,
            is_pro=is_active,
            expires_at=expires,
            source="revenuecat",
            original_app_user_id=app_user_id
        )
        logger.info(f"Updated subscription for {app_user_id} via webhook: {event_type}, active={is_active}")
    else:
        logger.info(f"Received unhandled RevenueCat webhook event: {event_type}")

    return {"success": True}
