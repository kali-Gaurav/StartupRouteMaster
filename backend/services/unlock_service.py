from sqlalchemy.orm import Session
from backend.models import UnlockedRoute, User, Route, Payment
from datetime import datetime
import logging
import random
from backend.config import Config

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

    def verify_live_availability(self, route_id: str, travel_date: str) -> bool:
        """
        Simulates a live availability check for a given route and date.
        In a real implementation, this would involve an API call to an external partner.
        """
        logger.info(f"Verifying live availability for route {route_id} on {travel_date} (simulated).")
        
        # Simulate external API call
        if random.random() < Config.SIMULATE_AVAILABILITY_CHECK_FAILURE_RATE:
            logger.warning(f"Simulating live availability check failure for route {route_id} on {travel_date}.")
            return False # Simulate unavailability

        # In a real scenario, make an actual API call here
        # For example:
        # try:
        #     response = await httpx.get(f"{Config.EXTERNAL_AVAILABILITY_API_URL}/check?route_id={route_id}&date={travel_date}")
        #     response.raise_for_status()
        #     data = response.json()
        #     return data.get("available", False)
        # except httpx.RequestError as e:
        #     logger.error(f"External availability API call failed: {e}")
        #     return False
            
        return True # Default to available if simulation passes and no real API is called
