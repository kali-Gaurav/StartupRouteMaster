import logging
import sys
import os
import time
from functools import lru_cache
from typing import Union, Optional

from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session
from jose import jwt, JWTError

# Ensure correct pathing
sys.path.insert(0, os.path.dirname(__file__))

from database.session import SessionUser, get_auth_db, get_db
from database.models import User, Profile
from config import Config
from utils.crypto import encrypt_pii

logger = logging.getLogger(__name__)

# ============================================================================
# AUTHENTICATION (Upgraded - Task 5 & Subtask 4.5)
# ============================================================================

async def get_current_user(
    authorization: Optional[str] = Header(None), 
    db: Session = Depends(get_auth_db)
) -> User:
    """
    Upgraded Auth Sync Flow:
    1. Validate JWT (exp, aud claims)
    2. Atomic Sync (Transaction)
    3. PII Encryption (Email/Phone)
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization Header")
    
    token = authorization.replace("Bearer ", "")
    
    # --- 1. JWT Claims Validation (Real Implementation) ---
    try:
        # Decode and verify the token
        secret = Config.SUPABASE_JWT_SECRET
        if not secret:
            logger.error("SUPABASE_JWT_SECRET not set in Config")
            raise HTTPException(status_code=500, detail="Server Configuration Error")
            
        payload = jwt.decode(
            token, 
            secret, 
            algorithms=["HS256"], 
            audience="authenticated",
            options={"verify_exp": True}
        )
        
        supabase_id = payload.get("sub")
        email = payload.get("email")
        
        if not supabase_id or not email:
             raise HTTPException(status_code=401, detail="Invalid Token Payload")

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token Expired")
    except jwt.JWTError as e:
        logger.warning(f"JWT Decode Error: {e}")
        raise HTTPException(status_code=401, detail="Could not validate credentials")
    except Exception as e:
        logger.error(f"Unexpected Auth Error: {e}")
        raise HTTPException(status_code=401, detail="Authentication Failed")

    # --- 2. Atomic Sync (Suggestion #2) ---
    try:
        # Check if user exists, if not create
        user = db.query(User).filter(User.supabase_id == supabase_id).first()
        
        if not user:
            logger.info(f"Creating encrypted local record for {supabase_id}")
            
            # Use a nested transaction for atomic creation
            with db.begin_nested(): 
                # --- 3. PII Encryption (Suggestion #4) ---
                user = User(
                    supabase_id=supabase_id,
                    email=encrypt_pii(email),
                    role="user"
                )
                db.add(user)
                db.flush() # Ensure user.id is generated
                
                profile = Profile(id=supabase_id, user_id=user.id)
                db.add(profile)
            
            db.commit() # Commit the creation
        
        return user
        
    except Exception as e:
        db.rollback()
        logger.error(f"Auth sync failed: {e}")
        raise HTTPException(status_code=401, detail="Session Sync Failed")

@lru_cache(maxsize=1)
def get_route_engine():
    from core.route_engine.engine import RailwayRouteEngine
    return RailwayRouteEngine()
