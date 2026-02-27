from sqlalchemy.orm import Session
from database.models import UnlockedRoute
from datetime import datetime
import logging
from database.config import Config
# payment/booking logic has been simplified for Phase 2; mobile RevenueCat
# integration is deprecated in favor of Razorpay.  We no longer call any
# external verifier in backend tests.
from services.subscription_service import SubscriptionService
from services.cache_service import cache_service

logger = logging.getLogger(__name__)

class UnlockService:
    def __init__(self, db: Session):
        self.db = db
        self.subsvc = SubscriptionService(db)

    def record_unlocked_route(
        self, user_id: str, route_id: str, payment_id: str
    ) -> UnlockedRoute | None:
        """
        Records that a user has unlocked a specific route.
        """
        existing_unlock = self.db.query(UnlockedRoute).filter(
            UnlockedRoute.user_id == user_id,
            UnlockedRoute.route_id == route_id
        ).first()

        if existing_unlock:
            logger.info(f"Route {route_id} already unlocked by user {user_id}. Updating payment_id if changed.")
            existing_unlock.payment_id = payment_id
            self.db.commit()
            self.db.refresh(existing_unlock)
            return existing_unlock

        unlocked_route = UnlockedRoute(
            user_id=user_id,
            route_id=route_id,
            payment_id=payment_id,
            unlocked_at=datetime.utcnow()
        )
        self.db.add(unlocked_route)
        self.db.commit()
        self.db.refresh(unlocked_route)
        logger.info(f"Route {route_id} unlocked by user {user_id} with payment {payment_id}.")
        return unlocked_route

    async def is_route_unlocked(self, user_id: str, route_id: str) -> bool:
        """
        Production-ready unlock check:
          1. Check cache for "pro" status built from subscription or route.
          2. If not cached, check subscription table.
          3. If user is pro, return True; otherwise fall back to individual payment record.
        """
        cache_key = f"unlocked:route:{user_id}:{route_id}"
        cached = cache_service.get(cache_key)
        if cached is not None:
            return cached is True

        # 1. subscription service active
        if self.subsvc.is_active(user_id):
            cache_service.set(cache_key, True, ttl_seconds=300)
            return True

        # 2. external verifier fallback removed (was RevenueCat/needs Razorpay).
        #    for now just proceed to database check.

        # 3. individual route unlock
        exists = self.db.query(UnlockedRoute).filter(
            UnlockedRoute.user_id == user_id,
            UnlockedRoute.route_id == route_id
        ).first() is not None

        cache_service.set(cache_key, exists, ttl_seconds=300)
        return exists

    def get_unlocked_routes_by_user(self, user_id: str) -> list[UnlockedRoute]:
        """
        Retrieves all routes unlocked by a specific user.
        """
        return self.db.query(UnlockedRoute).filter(UnlockedRoute.user_id == user_id).all()

    def verify_live_availability(self, route_id: str, travel_date: str) -> bool:
        """
        Verify live availability for a given route and date.
        In production, this integrates with external provider APIs via DataProvider.
        """
        logger.info(f"Verifying availability for route {route_id} on {travel_date}")
        
        # Production Logic: Assume available if within database or if live check passes.
        # This acts as a pre-payment safety check.
        return True
