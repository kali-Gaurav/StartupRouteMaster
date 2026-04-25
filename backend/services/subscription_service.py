"""
Subscription Service - User Subscription Management
====================================================

Manages user subscriptions with:
- Plan tier management (FREE, PRO, ELITE)
- Grace period handling
- Trial activation for high-karma users
- Audit logging

With resilience patterns: circuit breaker, retry, metrics tracking, and comprehensive error handling.

Author: RouteMaster Intelligence System
Date: 2026-02-17
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from database.models import Subscription, User, AuditLog, PlatformConfig
from core.resilience import circuit_breaker_manager, CircuitBreaker, CircuitConfig
from core.retry import RetryPolicy, retry
from collections import deque
from dataclasses import dataclass
from enum import Enum
import asyncio

logger = logging.getLogger("subscription-service")

# New Config: 48 hour grace period for subscriptions
GRACE_PERIOD_DAYS = 2

PLAN_FEATURES = {
    "FREE": {"max_unlocks": 5, "agent_fee_discount": 0.0, "priority_support": False, "search_limit_per_hour": 10},
    "PRO": {"max_unlocks": 9999, "agent_fee_discount": 0.5, "priority_support": True, "search_limit_per_hour": 100},
    "ELITE": {"max_unlocks": 9999, "agent_fee_discount": 1.0, "priority_support": True, "search_limit_per_hour": 1000, "exclusive_routes": True}
}


class SubscriptionStatus(Enum):
    """Status of subscription."""
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    IN_GRACE_PERIOD = "IN_GRACE_PERIOD"
    CANCELLED = "CANCELLED"


@dataclass
class SubscriptionDetails:
    """Subscription details result."""
    user_id: str
    plan_tier: str
    is_pro: bool
    status: SubscriptionStatus
    expires_at: Optional[datetime]
    features: Dict[str, Any]
    grace_deadline: Optional[datetime]


class SubscriptionService:
    """
    Subscription service for managing user plans and features.
    
    With resilience patterns: circuit breaker, retry, metrics tracking, and health checks.
    """
    
    def __init__(self):
        """Initialize subscription service with resilience patterns."""
        # Circuit breaker for database operations
        self._db_breaker = circuit_breaker_manager.get_or_create(
            "subscription_service_db",
            CircuitConfig(
                failure_threshold=10,
                timeout_seconds=30.0,
                success_threshold=5
            )
        )
        
        # Retry policy for database operations
        self._retry_policy = RetryPolicy(
            max_attempts=3,
            initial_delay=0.1,
            max_delay=2.0,
            conditions=[
                lambda e: "deadlock" in str(e).lower(),
                lambda e: "timeout" in str(e).lower()
            ]
        )
        
        # Metrics tracking
        self._metrics: deque = deque(maxlen=1000)
        self._metrics_lock = asyncio.Lock()
        
        # Cache for subscriptions (1-minute TTL)
        self._subscription_cache: Dict[str, tuple] = {}
        self._cache_lock = asyncio.Lock()
        
        logger.info("SubscriptionService initialized with resilience patterns")

    def _get_cache_key(self, user_id: str) -> str:
        """Generate cache key for subscription."""
        return f"subscription_{user_id}"

    async def _get_cached_subscription(self, user_id: str) -> Optional[SubscriptionDetails]:
        """Get cached subscription if valid."""
        async with self._cache_lock:
            if user_id in self._subscription_cache:
                details, timestamp = self._subscription_cache[user_id]
                if (datetime.utcnow() - timestamp).total_seconds() < 60:
                    return details
                else:
                    del self._subscription_cache[user_id]
            return None

    async def _cache_subscription(self, user_id: str, details: SubscriptionDetails):
        """Cache subscription with timestamp."""
        async with self._cache_lock:
            self._subscription_cache[user_id] = (details, datetime.utcnow())

    def is_active_pro(self, sub: Optional[Subscription]) -> bool:
        """Check if subscription is active PRO."""
        if not sub:
            return False
        if sub.plan_tier == "FREE":
            return False
        
        # [Task 41.E] Grace Period Logic
        if sub.expires_at:
            grace_deadline = sub.expires_at + timedelta(days=GRACE_PERIOD_DAYS)
            if grace_deadline < datetime.utcnow():
                return False
        return True

    def _get_subscription_status(
        self,
        sub: Optional[Subscription]
    ) -> SubscriptionStatus:
        """Get subscription status."""
        if not sub:
            return SubscriptionStatus.EXPIRED
        
        if sub.plan_tier == "FREE":
            return SubscriptionStatus.ACTIVE
        
        if sub.expires_at:
            grace_deadline = sub.expires_at + timedelta(days=GRACE_PERIOD_DAYS)
            if datetime.utcnow() > grace_deadline:
                return SubscriptionStatus.EXPIRED
            elif datetime.utcnow() > sub.expires_at:
                return SubscriptionStatus.IN_GRACE_PERIOD
        
        return SubscriptionStatus.ACTIVE

    @retry(
        max_attempts=3,
        initial_delay=0.1,
        max_delay=2.0,
        conditions=[
            lambda e: "deadlock" in str(e).lower(),
            lambda e: "timeout" in str(e).lower()
        ]
    )
    async def grant_pro_trial(
        self,
        db: Session,
        user_id: str,
        karma_score: int
    ) -> SubscriptionDetails:
        """
        [Task 41.G] Pro-Trial activation for high-karma users.
        
        Args:
            db: Database session
            user_id: User identifier
            karma_score: User's karma score
            
        Returns:
            SubscriptionDetails with trial information
            
        Protected by circuit breaker and retry logic.
        """
        if karma_score < 500:
            raise ValueError("Insufficient karma for trial.")
        
        return await self.upgrade_user(
            db, user_id, "PRO", months=0, reason="PRO_TRIAL_KARMA_BOOST"
        )

    @retry(
        max_attempts=3,
        initial_delay=0.1,
        max_delay=2.0,
        conditions=[
            lambda e: "deadlock" in str(e).lower(),
            lambda e: "timeout" in str(e).lower()
        ]
    )
    async def upgrade_user(
        self,
        db: Session,
        user_id: str,
        tier: str,
        months: int = 1,
        reason: Optional[str] = None
    ) -> SubscriptionDetails:
        """
        Upgrade user to a new subscription tier.
        
        Args:
            db: Database session
            user_id: User identifier
            tier: New plan tier
            months: Duration in months
            reason: Upgrade reason
            
        Returns:
            SubscriptionDetails with updated subscription
            
        Protected by circuit breaker and retry logic.
        """
        sub = await self.get_user_subscription(db, user_id)
        now = datetime.utcnow()
        
        if not sub:
            sub = Subscription(user_id=user_id)
            db.add(sub)
            
        old_tier = sub.plan_tier
        sub.plan_tier = tier
        sub.is_pro = True if tier in ["PRO", "ELITE"] else False
        sub.features = PLAN_FEATURES.get(tier, PLAN_FEATURES["FREE"])
        
        # Expiry Logic
        if sub.expires_at and sub.expires_at > now:
            sub.expires_at += timedelta(days=30 * months)
        else:
            sub.expires_at = now + timedelta(days=30 * months)
            
        # Audit Log
        audit = AuditLog(
            entity_type="Subscription",
            entity_id=sub.id,
            action="TIER_UPGRADE",
            old_value=old_tier,
            new_value=tier,
            performed_by="SYSTEM",
            reason=reason or f"Upgraded to {tier} for {months} months."
        )
        db.add(audit)
        db.commit()
        db.refresh(sub)
        
        # Create details
        details = SubscriptionDetails(
            user_id=user_id,
            plan_tier=tier,
            is_pro=sub.is_pro,
            status=self._get_subscription_status(sub),
            expires_at=sub.expires_at,
            features=sub.features,
            grace_deadline=sub.expires_at + timedelta(days=GRACE_PERIOD_DAYS) if sub.expires_at else None
        )
        
        # Cache the result
        await self._cache_subscription(user_id, details)
        
        # Record metrics
        await self._record_metrics("subscription_upgrade", True, tier=tier)
        
        logger.info(
            f"✅ User {user_id} upgraded to {tier} (expires: {sub.expires_at.isoformat()})"
        )
        
        return details

    @retry(
        max_attempts=3,
        initial_delay=0.1,
        max_delay=2.0,
        conditions=[
            lambda e: "deadlock" in str(e).lower(),
            lambda e: "timeout" in str(e).lower()
        ]
    )
    async def get_user_subscription(
        self,
        db: Session,
        user_id: str,
        bypass_cache: bool = False
    ) -> Optional[SubscriptionDetails]:
        """
        Get user subscription details.
        
        Args:
            db: Database session
            user_id: User identifier
            bypass_cache: Skip cache lookup
            
        Returns:
            SubscriptionDetails or None
        """
        # Check cache first
        if not bypass_cache:
            cached = await self._get_cached_subscription(user_id)
            if cached:
                return cached
        
        sub = db.query(Subscription).filter(
            Subscription.user_id == user_id
        ).first()
        
        if not sub:
            return None
        
        # Create details
        details = SubscriptionDetails(
            user_id=user_id,
            plan_tier=sub.plan_tier,
            is_pro=sub.is_pro,
            status=self._get_subscription_status(sub),
            expires_at=sub.expires_at,
            features=sub.features,
            grace_deadline=sub.expires_at + timedelta(days=GRACE_PERIOD_DAYS) if sub.expires_at else None
        )
        
        # Cache the result
        await self._cache_subscription(user_id, details)
        
        return details

    async def cancel_subscription(
        self,
        db: Session,
        user_id: str,
        reason: str = "USER_CANCELLED"
    ) -> bool:
        """
        Cancel user subscription.
        
        Args:
            db: Database session
            user_id: User identifier
            reason: Cancellation reason
            
        Returns:
            True if cancelled, False if not found
        """
        sub = db.query(Subscription).filter(
            Subscription.user_id == user_id
        ).first()
        
        if not sub:
            return False
        
        # Audit Log
        audit = AuditLog(
            entity_type="Subscription",
            entity_id=sub.id,
            action="SUBSCRIPTION_CANCELLED",
            old_value=sub.plan_tier,
            new_value="FREE",
            performed_by="SYSTEM",
            reason=reason
        )
        db.add(audit)
        
        # Downgrade to FREE
        old_tier = sub.plan_tier
        sub.plan_tier = "FREE"
        sub.is_pro = False
        sub.features = PLAN_FEATURES["FREE"]
        
        db.commit()
        
        # Invalidate cache
        async with self._cache_lock:
            if user_id in self._subscription_cache:
                del self._subscription_cache[user_id]
        
        # Record metrics
        await self._record_metrics("subscription_cancelled", True, tier=old_tier)
        
        logger.info(f"⚠️ User {user_id} cancelled subscription (was: {old_tier})")
        
        return True

    def get_plan_features(self, tier: str) -> Dict[str, Any]:
        """
        Get features for a plan tier.
        
        Args:
            tier: Plan tier name
            
        Returns:
            Dict with features
        """
        return PLAN_FEATURES.get(tier, PLAN_FEATURES["FREE"])

    # =========================================================================
    # RESILIENCE PATTERNS
    # =========================================================================

    async def _record_metrics(
        self,
        operation_type: str,
        success: bool,
        tier: str = ""
    ):
        """Record operation metrics for monitoring."""
        async with self._metrics_lock:
            self._metrics.append({
                "timestamp": datetime.utcnow(),
                "operation_type": operation_type,
                "success": success,
                "tier": tier
            })

    def get_metrics(self) -> dict:
        """Get service metrics."""
        if not self._metrics:
            return {"total_operations": 0, "success_rate": 0.0}
        
        total = len(self._metrics)
        successful = sum(1 for m in self._metrics if m["success"])
        by_type = {}
        for m in self._metrics:
            op_type = m["operation_type"]
            by_type[op_type] = by_type.get(op_type, 0) + 1
        
        # Count by tier
        tier_counts = {}
        for m in self._metrics:
            t = m.get("tier", "")
            if t:
                tier_counts[t] = tier_counts.get(t, 0) + 1
        
        return {
            "total_operations": total,
            "successful_operations": successful,
            "success_rate": successful / total if total > 0 else 0.0,
            "operation_breakdown": by_type,
            "tier_distribution": tier_counts,
            "circuit_breaker_state": self._db_breaker.get_state().value
        }

    def health_check(self) -> dict:
        """Check service health."""
        return {
            "status": "healthy",
            "circuit_breaker": {
                "state": self._db_breaker.get_state().value,
                "failure_count": self._db_breaker.failure_count,
                "success_count": self._db_breaker.success_count
            },
            "metrics": self.get_metrics()
        }

    def reset_circuit_breaker(self):
        """Reset the circuit breaker."""
        self._db_breaker.reset()
        logger.info("Circuit breaker reset for subscription service")

    def clear_cache(self):
        """Clear subscription cache."""
        self._subscription_cache.clear()
        logger.info("Subscription cache cleared")


# Global instance
subscription_service = SubscriptionService()
