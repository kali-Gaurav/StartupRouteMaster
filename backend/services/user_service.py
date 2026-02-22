from sqlalchemy.orm import Session
from typing import Optional

from backend.models import User
from backend.schemas import UserCreate
from backend.utils.security import get_password_hash, verify_password


class UserService:
    def __init__(self, db: Session):
        self.db = db

    def get_user_by_email(self, email: str) -> Optional[User]:
        """
        Get a user by their email address.
        """
        return self.db.query(User).filter(User.email == email).first()

    def get_user_by_phone(self, phone: str) -> Optional[User]:
        """
        Lookup a user by their phone number.
        Used by the OTP authentication flow.
        """
        return self.db.query(User).filter(User.phone_number == phone).first()

    def create_user(self, user_create: UserCreate) -> User:
        """
        Create a new user.
        """
        hashed_password = get_password_hash(user_create.password)
        db_user = User(
            email=user_create.email,
            password_hash=hashed_password,
            phone_number=user_create.phone_number,
        )
        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)
        return db_user

    def create_user_with_data(self, data: dict) -> User:
        """
        Helper to create a user from a generic data dictionary. This is useful
        for OTP flows where we may only have phone or email without a password.
        """
        db_user = User(**data)
        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)
        return db_user

    def authenticate_user(
        self, email: str, password: str
    ) -> Optional[User]:
        """
        Authenticate a user by email and password.
        """
        user = self.get_user_by_email(email)
        if not user or not verify_password(password, user.password_hash):
            return None
        return user
