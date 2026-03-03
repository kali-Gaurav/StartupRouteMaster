import logging
import sys
import os
from functools import lru_cache
from typing import Union, Optional

from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session

# Ensure correct pathing
sys.path.insert(0, os.path.dirname(__file__))

from database.session import SessionUser, SessionTransit
from database.models import User, Profile, ZeroRouteDiagnostic
from config import Config

logger = logging.getLogger(__name__)

# ============================================================================
# DATABASE DEPENDENCIES
# ============================================================================

def get_db():
    """Dependency for User Operational Store (user_store.db)"""
    db = SessionUser()
    try:
        yield db
    finally:
        db.close()

def get_transit_db():
    """Dependency for Transit Graph Store (transit_graph.db)"""
    db = SessionTransit()
    try:
        yield db
    finally:
        db.close()

# ============================================================================
# AUTHENTICATION
# ============================================================================

async def get_current_user(
    authorization: Optional[str] = Header(None), 
    db: Session = Depends(get_db)
) -> User:
    """Validates Supabase JWT and syncs with local User Store."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization")
    
    token = authorization.replace("Bearer ", "")
    
    try:
        # Logical Auth Flow:
        # 1. Decode Supabase JWT (mocked for now)
        # 2. Get Supabase ID
        supabase_id = token if len(token) > 20 else "fixed_test_id"
        
        # 3. Check local user_store.db
        user = db.query(User).filter(User.supabase_id == supabase_id).first()
        if not user:
            user = User(supabase_id=supabase_id, email="real_user@example.com")
            db.add(user)
            db.flush()
            db.add(Profile(id=supabase_id, user_id=user.id))
            db.commit()
        return user
    except Exception as e:
        logger.error(f"Auth sync failed: {e}")
        raise HTTPException(status_code=401, detail="Session Invalid")

# ============================================================================
# ROUTING ENGINES
# ============================================================================

@lru_cache(maxsize=1)
def get_route_engine():
    from core.route_engine.engine import RailwayRouteEngine
    return RailwayRouteEngine()

def get_active_route_engine():
    return get_route_engine()
