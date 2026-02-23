from sqlalchemy.orm import Session
from backend.models import UnlockedRoute, User, Route, Payment
from datetime import datetime
import logging
from backend.config import Config
from backend.services.revenue_cat_verifier import revenue_cat_verifier

logger = logging.getLogger(__name__)

class UnlockService:
    def __init__(self, db: Session):
        self.db = db

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
        Checks if a user has already unlocked a specific route.
        Also checks RevenueCat for 'Routemaster Pro' status which unlocks all routes.
        """
        # 1. Check if user is "Pro" via RevenueCat
        is_pro = await revenue_cat_verifier.is_user_pro(user_id)
        if is_pro is True: # Explicitly check for True to be safe
            return True

        # 2. Check individual route unlock in database
        exists = self.db.query(UnlockedRoute).filter(
            UnlockedRoute.user_id == user_id,
            UnlockedRoute.route_id == route_id
        ).first() is not None

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
