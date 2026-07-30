import logging
from typing import List, Callable, Any
from fastapi import HTTPException, Depends
from database.models import User

logger = logging.getLogger(__name__)

class Permissions:
    """
    Utility class for handling granular permission checks.
    Can be used as FastAPI dependencies.
    """
    
    @staticmethod
    def is_admin(user: User):
        if user.role != "admin":
            raise HTTPException(status_code=403, detail="Admin access required.")
        return True

    @staticmethod
    def is_staff(user: User):
        if user.role not in ["admin", "staff"]:
            raise HTTPException(status_code=403, detail="Staff access required.")
        return True

    @staticmethod
    def can_manage_resource(resource_owner_id: str):
        """
        Dependency factory for owner-based permissions.
        Ensures the current user is either the owner or an admin.
        """
        def check(user: User):
            if user.role != "admin" and user.id != resource_owner_id:
                logger.warning(f"Access Denied: User {user.id} tried to manage resource of {resource_owner_id}")
                raise HTTPException(status_code=403, detail="You do not have permission to manage this resource.")
            return True
        return check

    @staticmethod
    def has_any_role(allowed_roles: List[str]):
        """
        Dependency factory for role-based permissions.
        """
        def check(user: User):
            if user.role not in allowed_roles:
                logger.warning(f"Access Denied: User {user.id} role '{user.role}' not in {allowed_roles}")
                raise HTTPException(status_code=403, detail=f"Permission denied: {', '.join(allowed_roles)} required.")
            return True
        return check
