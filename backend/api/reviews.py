from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from schemas import ReviewCreate, ReviewRead
from services.review_service import ReviewService
from models import User
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
