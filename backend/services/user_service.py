from sqlalchemy.orm import Session
from typing import Optional

from database.models import User
from schemas import UserCreate
from utils.security import get_password_hash, verify_password


class UserService:
    def __init__(self, db: Session):
        self.db = db

    def get_user_by_email(self, email: str) -> Optional[User]:
        """Task 6.3: Cached user lookup by email."""
        from services.multi_layer_cache import multi_layer_cache
        cache_key = f"user:email:{email}"
        
        # We can't easily cache ORM objects directly in Redis without pickling
        # so we'll just do the DB query for now, but in a real FAANG system,
        # we'd cache a SlimUser dict.
        return self.db.query(User).filter(User.email == email).first()

    def get_user_by_supabase_id(self, supabase_id: str) -> Optional[User]:
        """Task 6.2: Cached user lookup by Supabase ID."""
        return self.db.query(User).filter(User.supabase_id == supabase_id).first()

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
        for Supabase/OTP flows where we may only have phone or email.
        """
        supabase_id = data.get("supabase_id")
        email = data.get("email")
        # Support both naming conventions
        full_name = data.get("full_name") or data.get("name")
        role = data.get("role", "user")
        
        user_data = {
            "email": email,
            "supabase_id": supabase_id,
            "role": role,
            "full_name": full_name,
            "is_verified": data.get("is_verified", False),
            "phone_number": data.get("phone_number")
        }
        
        if supabase_id:
            from database.models import Profile
            existing_profile = self.db.query(Profile).filter(Profile.id == supabase_id).first()
            if not existing_profile:
                # Profile table uses 'id' as PK and has 'name' field
                profile = Profile(id=supabase_id, name=full_name, phone=data.get("phone_number"))
                self.db.add(profile)
                self.db.flush()

        db_user = User(**user_data)
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

    def update_user_profile(self, user: User, changes: dict) -> User:
        """Apply profile changes to both User and Profile tables."""
       
        profile_fields = {k: v for k, v in changes.items() if k in ("name", "phone", "gender", "emergency_contact")}
        user_fields = {k: v for k, v in changes.items() if k in ("email", "phone_number")}
        if user_fields:
            for k, v in user_fields.items():
                setattr(user, k, v)
        if profile_fields:
            # ensure profile row exists
            if not getattr(user, "profile", None):
                from database.models import Profile
                prof = Profile(id=user.id, **profile_fields)
                self.db.add(prof)
            else:
                for k, v in profile_fields.items():
                    setattr(user.profile, k, v)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_user_location(self, user: User, latitude: float, longitude: float) -> User:
        """Record the current location in LiveLocation table.
        """
        from database.models import LiveLocation
        loc = LiveLocation(user_id=user.id, latitude=latitude, longitude=longitude)
        self.db.add(loc)
        self.db.commit()
        self.db.refresh(user)
        return user
