import httpx
import logging
from backend.config import Config
from backend.services.subscription_service import SubscriptionService
from backend.services.cache_service import cache_service
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class RevenueCatVerifier:
    """
    Service to verify RevenueCat entitlements on the backend.
    Documentation: https://www.revenuecat.com/docs/api-v1
    """
    
    API_URL = "https://api.revenuecat.com/v1"
    ENTITLEMENT_ID = "Routemaster Pro"

    def __init__(self):
        # Pull API key from environment/config
        self.api_key = Config.REVENUECAT_API_KEY
        if not self.api_key:
            logger.warning("RevenueCat API key is not configured. Entitlement checks will always return False.")
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Platform": "server"
        }

    async def is_user_pro(self, app_user_id: str, db: Session | None = None) -> bool:
        """
        Determines whether a user is a Pro subscriber.

        Order of checks:
        1. Cache (Redis) - short lived (5 minutes)
        2. Local subscription table (db) - persisted
        3. RevenueCat API fallback - update db/cache

        `db` is optional but recommended for DB updates when making API call.
        """
        cache_key = f"revenuecat:pro:{app_user_id}"
        # 1. Cache
        cached = cache_service.get(cache_key)
        if cached is not None:
            return cached is True

        # 2. Local DB
        if db is not None:
            subsvc = SubscriptionService(db)
            if subsvc.is_active(app_user_id):
                cache_service.set(cache_key, True, ttl_seconds=300)
                return True

        # 3. Remote API
        if not self.api_key:
            return False  # cannot query without key

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{self.API_URL}/subscribers/{app_user_id}",
                    headers=self.headers
                )
            if response.status_code == 200:
                data = response.json()
                subscriber = data.get("subscriber", {})
                entitlements = subscriber.get("entitlements", {})
                pro_entitlement = entitlements.get(self.ENTITLEMENT_ID)
                if pro_entitlement:
                    # determine expiry
                    expires = pro_entitlement.get("expires_date")
                    exp_dt = None
                    if expires:
                        try:
                            from dateutil import parser
                            exp_dt = parser.isoparse(expires)
                        except Exception:
                            exp_dt = None
                    if db is not None:
                        subsvc = SubscriptionService(db)
                        subsvc.set_subscription(
                            user_id=app_user_id,
                            is_pro=True,
                            expires_at=exp_dt,
                            source="revenuecat",
                            original_app_user_id=app_user_id
                        )
                    # update cache
                    cache_service.set(cache_key, True, ttl_seconds=300)
                    return True
        except Exception as e:
            logger.error(f"Error verifying RevenueCat status for {app_user_id}: {e}")
            # fall back to DB value if available
            if db is not None:
                subsvc = SubscriptionService(db)
                if subsvc.is_active(app_user_id):
                    cache_service.set(cache_key, True, ttl_seconds=300)
                    return True
        # default
        cache_service.set(cache_key, False, ttl_seconds=300)
        return False


revenue_cat_verifier = RevenueCatVerifier()

    async def is_user_pro(self, app_user_id: str) -> bool:
        """
        Queries RevenueCat to see if the user has an active 'Routemaster Pro' entitlement.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.API_URL}/subscribers/{app_user_id}",
                    headers=self.headers
                )
                
                if response.status_code == 200:
                    data = response.json()
                    subscriber = data.get("subscriber", {})
                    entitlements = subscriber.get("entitlements", {})
                    
                    # Check if 'Routemaster Pro' is active
                    pro_entitlement = entitlements.get(self.ENTITLEMENT_ID)
                    if pro_entitlement:
                        # Check if it has an expires_date and if it's in the future
                        # Or if it's null (lifetime)
                        return True
                    
                return False
        except Exception as e:
            logger.error(f"Error verifying RevenueCat status for {app_user_id}: {e}")
            return False

revenue_cat_verifier = RevenueCatVerifier()
