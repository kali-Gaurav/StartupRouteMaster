import os
import sys
import logging
from datetime import datetime

# Add backend to sys.path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from database.session import SessionLocal
from database.models import User, Profile
from services.user_service import UserService
from supabase_client import supabase
from database.config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_supabase_connection():
    logger.info("Verifying Supabase connection...")
    try:
        # Simple health check by listing public tables or getting settings
        # auth.get_user is the best way to check if URL/Keys are valid for auth
        try:
            supabase.auth.get_user("invalid-token")
            logger.info("Supabase API reachable (received expected auth response).")
            return True
        except Exception as e:
            msg = str(e).lower()
            # If we get any auth-related error, it means the service is alive and rejecting our fake token
            if any(term in msg for term in ["invalid", "401", "403", "unauthorized", "forbidden", "token", "segments"]):
                logger.info(f"Supabase API reachable (received expected response: {msg[:50]}...)")
                return True
            else:
                logger.error(f"Supabase connection failed with unexpected error: {e}")
                return False
    except Exception as e:
        logger.error(f"Failed to initialize Supabase client: {e}")
        return False

def verify_user_sync_logic():
    logger.info("Verifying User sync logic with local database...")
    db = SessionLocal()
    user_service = UserService(db)
    
    test_supabase_id = "test-sb-uuid-" + str(datetime.now().timestamp())
    test_email = f"test-{datetime.now().timestamp()}@example.com"
    
    try:
        # 1. Test creation
        logger.info(f"Creating test user with Supabase ID: {test_supabase_id}")
        user_data = {
            "email": test_email,
            "supabase_id": test_supabase_id,
            "password_hash": "supabase-managed",
            "role": "user"
        }
        user = user_service.create_user_with_data(user_data)
        
        if user and user.supabase_id == test_supabase_id:
            logger.info("✓ User creation successful.")
        else:
            logger.error("✗ User creation failed or data mismatch.")
            return False
            
        # 2. Test lookup
        logger.info("Testing lookup by Supabase ID...")
        found_user = user_service.get_user_by_supabase_id(test_supabase_id)
        if found_user and found_user.id == user.id:
            logger.info("✓ User lookup successful.")
        else:
            logger.error("✗ User lookup failed.")
            return False
            
        # 3. Clean up
        logger.info("Cleaning up test data...")
        db.delete(user)
        db.commit()
        logger.info("✓ Cleanup successful.")
        
        return True
        
    except Exception as e:
        logger.error(f"Error during user sync verification: {e}")
        db.rollback()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    conn_ok = verify_supabase_connection()
    sync_ok = verify_user_sync_logic()
    
    if conn_ok and sync_ok:
        logger.info("\nSUCCESS: Supabase integration and User sync logic verified.")
        sys.exit(0)
    else:
        logger.error("\nFAILURE: Verification failed.")
        sys.exit(1)
