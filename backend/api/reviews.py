from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from schemas import ReviewCreate, ReviewRead
from services.review_service import ReviewService
from database.models import User, Review
from api.dependencies import get_current_user

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


@router.post("/", response_model=ReviewRead, status_code=status.HTTP_201_CREATED)
def create_review(
    review_create: ReviewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new review for a booking. Must be authenticated.
    """
    review_service = ReviewService(db)
    try:
        return review_service.create_review(review_create=review_create, user=current_user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        # For other potential errors, like database integrity errors
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not create review.")

@router.get("/my", response_model=List[ReviewRead])
async def get_user_reviews(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all reviews submitted by the current authenticated user.
    """
    reviews = db.query(Review).filter(Review.user_id == current_user.id).order_by(Review.created_at.desc()).offset(skip).limit(limit).all()
    return reviews
