from sqlalchemy.orm import Session
from backend.models import UnlockedRoute, User, Route, Payment
from datetime import datetime
import logging

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

    def is_route_unlocked(self, user_id: str, route_id: str) -> bool:
        """
        Checks if a user has already unlocked a specific route.
        """
        return self.db.query(UnlockedRoute).filter(
            UnlockedRoute.user_id == user_id,
            UnlockedRoute.route_id == route_id
        ).first() is not None

    def get_unlocked_routes_by_user(self, user_id: str) -> list[UnlockedRoute]:
        """
        Retrieves all routes unlocked by a specific user.
        """
        return self.db.query(UnlockedRoute).filter(UnlockedRoute.user_id == user_id).all()
