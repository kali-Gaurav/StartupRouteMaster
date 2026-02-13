from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from database import get_db
from models import User
from services.user_service import UserService
from utils.security import decode_access_token, credentials_exception

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/users/token")


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    """
    Dependency to get the current authenticated user from a JWT token.
    """
    token_data = decode_access_token(token)
    user_service = UserService(db)
    user = user_service.get_user_by_email(email=token_data.email)
    if user is None:
        raise credentials_exception
    return user
