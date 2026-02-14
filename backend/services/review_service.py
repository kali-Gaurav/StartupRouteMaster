from sqlalchemy.orm import Session
from typing import Optional

from backend.models import Review, Booking, User
from backend.schemas import ReviewCreate


class ReviewService:
    def __init__(self, db: Session):
        self.db = db

    def create_review(self, review_create: ReviewCreate, user: User) -> Review:
        """
        Create a new review for a booking.
        """
        # Optional: Add validation to ensure the user owns the booking
        booking = self.db.query(Booking).filter(Booking.id == review_create.booking_id, Booking.user_id == user.id).first()
        if not booking:
            raise ValueError("Booking not found or does not belong to the user.")

        db_review = Review(
            **review_create.dict(),
            user_id=user.id
        )
        self.db.add(db_review)
        self.db.commit()
        self.db.refresh(db_review)
        return db_review
