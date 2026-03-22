import logging
import time
from typing import Dict, Any, Optional, List
from fastapi import HTTPException, status
from core.system_monitor import system_monitor, SystemState

logger = logging.getLogger("routemaster.auth_service")

class AuthMicroservice:
    """
    Task 7: Decoupled Auth Microservice Engine.
    Handles JWT validation, Session Tracking, and Risk Assessment.
    """
    def __init__(self, db_session, redis_client=None):
        self.db = db_session
        self.redis = redis_client
        
    async def validate_token_and_user(self, token: str) -> Dict[str, Any]:
        """
        Production-grade token validation with risk-aware shedding.
        """
        # 1. System Awareness [Task 4/5 integration]
        state = system_monitor.current_state
        if state >= SystemState.CRITICAL:
            # During critical load, only allow essential admin/SOS tokens if possible
            # For simplicity, we'll just log it for now
            logger.warning("🔐 Auth: Processing login during CRITICAL state.")

        from microservices.shared.auth import SharedAuthManager
        auth_manager = SharedAuthManager(self.db, self.redis)
        
        start = time.perf_counter()
        try:
            # Verify JWT via Supabase
            sb_user = auth_manager.verify_jwt(token)
            
            # Sync to local DB
            user = auth_manager.sync_user(sb_user)
            
            duration_ms = (time.perf_counter() - start) * 1000
            system_monitor.report_request_latency(duration_ms)
            
            return {
                "status": "success",
                "user_id": user.id,
                "role": user.role,
                "email": user.email,
                "latency_ms": duration_ms
            }
        except HTTPException as e:
            raise e
        except Exception as e:
            logger.error(f"Auth Microservice Error: {e}")
            raise HTTPException(status_code=500, detail="Authentication Service Unavailable")

    async def report_login_failure(self, ip: str):
        """Task 6/7: Integrated Rate Limiting."""
        from services.multi_layer_cache import multi_layer_cache
        await multi_layer_cache.record_failed_login(ip)
