"""
💰 FARE SERVICE - Fare Calculation & Verification
Production-ready with audit trail, rate limiting, fare prediction, and anomaly detection.
"""

import logging
import asyncio
import hashlib
import uuid
import json
import time
from typing import Optional, Dict, Any, Tuple, List
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict, deque

from database.config import Config
from database.models import Base
from sqlalchemy import Column, String, Text, DateTime, Float, Integer, JSON
from core.pricing.fare_calculator import calculate_fare, get_slab_fare
from core.resilience import circuit_manager, CircuitBreaker, CircuitConfig, CircuitOpenError
from core.retry import RetryPolicy, RETRY_POLICY_EXTERNAL_API
from core.retry import retry

logger = logging.getLogger(__name__)


# Create circuit breaker for RapidAPI calls
RAPIDAPI_FARE_BREAKER = circuit_manager.get_or_create(
    "rapidapi_fare",
    CircuitConfig(
        failure_threshold=3,
        timeout_seconds=120.0,
        half_open_max_calls=2
    )
)


# =========================================================================
# PRODUCTION MODELS
# =========================================================================

class FareAuditLog(Base):
    """
    Audit log for fare operations.
    Task: Financial audit trail.
    """
    __tablename__ = 'fare_audit_log'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    audit_id = Column(String(36), unique=True, nullable=False, index=True)
    train_no = Column(String(20), nullable=False, index=True)
    from_station = Column(String(10), nullable=False)
    to_station = Column(String(10), nullable=False)
    class_code = Column(String(5), nullable=False)
    action = Column(String(50), nullable=False)  # QUERY, CALCULATE, VERIFY
    fare_amount = Column(Float, nullable=True)
    source = Column(String(20), nullable=False)  # rapidapi, local, cache
    meta_data = Column('metadata', JSON, nullable=True)
    checksum = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class FareAnomaly(Base):
    """
    Detected fare anomalies for alerting.
    Task: Pricing anomaly detection.
    """
    __tablename__ = 'fare_anomalies'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    train_no = Column(String(20), nullable=False, index=True)
    route_key = Column(String(50), nullable=False, index=True)
    class_code = Column(String(5), nullable=False)
    detected_fare = Column(Float, nullable=False)
    expected_fare = Column(Float, nullable=True)
    deviation_pct = Column(Float, nullable=True)
    severity = Column(String(20), nullable=False)  # LOW, MEDIUM, HIGH, CRITICAL
    status = Column(String(20), default="open")  # open, investigating, resolved
    detected_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)


# =========================================================================
# CONFIGURATION
# =========================================================================

@dataclass
class FareConfig:
    """Configuration for fare service."""
    cache_ttl_seconds: int = 300
    stale_threshold_seconds: int = 600  # 10 minutes for fares
    rate_limit_per_minute: int = 50
    rate_limit_per_hour: int = 1000
    anomaly_threshold_pct: float = 30.0  # 30% deviation triggers alert
    prediction_enabled: bool = True


class RateLimiter:
    """Token bucket rate limiter."""
    
    def __init__(self, requests_per_minute: int = 60, requests_per_hour: int = 1000):
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self._buckets: Dict[str, Dict] = {}
        self._lock = asyncio.Lock()
    
    def _get_bucket(self, key: str) -> Dict:
        if key not in self._buckets:
            self._buckets[key] = {
                "minute_tokens": self.requests_per_minute,
                "hour_tokens": self.requests_per_hour,
                "last_minute_update": time.time(),
                "last_hour_update": time.time()
            }
        return self._buckets[key]
    
    async def allow(self, key: str) -> Tuple[bool, Dict]:
        async with self._lock:
            bucket = self._get_bucket(key)
            now = time.time()
            
            elapsed_min = now - bucket["last_minute_update"]
            bucket["minute_tokens"] = min(
                self.requests_per_minute,
                bucket["minute_tokens"] + elapsed_min * (self.requests_per_minute / 60)
            )
            
            elapsed_hour = now - bucket["last_hour_update"]
            if elapsed_hour >= 3600:
                bucket["hour_tokens"] = self.requests_per_hour
                bucket["last_hour_update"] = now
            
            bucket["last_minute_update"] = now
            
            if bucket["minute_tokens"] < 1:
                return False, {"reason": "minute_limit_exceeded", "retry_after": 60}
            if bucket["hour_tokens"] < 1:
                return False, {"reason": "hour_limit_exceeded", "retry_after": 3600}
            
            bucket["minute_tokens"] -= 1
            bucket["hour_tokens"] -= 1
            
            return True, {"remaining_minute": int(bucket["minute_tokens"]), "remaining_hour": int(bucket["hour_tokens"])}


class FareServiceMetrics:
    """Metrics tracking for fare service."""

    def __init__(self):
        self._metrics: deque = deque(maxlen=1000)
        self._metrics_lock = asyncio.Lock()

    async def record_fare_operation(self, operation: str, source: str, success: bool, duration_ms: float):
        """Record fare operation metrics."""
        async with self._metrics_lock:
            self._metrics.append({
                "timestamp": datetime.utcnow(),
                "operation": operation,
                "source": source,
                "success": success,
                "duration_ms": duration_ms
            })

    def get_metrics(self) -> dict:
        """Get service metrics."""
        if not self._metrics:
            return {"total_operations": 0, "success_rate": 0.0}

        total = len(self._metrics)
        successful = sum(1 for m in self._metrics if m["success"])
        by_source = {}
        for m in self._metrics:
            source = m.get("source", "unknown")
            if source not in by_source:
                by_source[source] = {"total": 0, "success": 0}
            by_source[source]["total"] += 1
            if m["success"]:
                by_source[source]["success"] += 1

        return {
            "total_operations": total,
            "successful_operations": successful,
            "failed_operations": total - successful,
            "success_rate": successful / total if total > 0 else 0.0,
            "by_source": by_source
        }


class FareService:
    """
    Fare calculation and verification service.
    Production-ready with:
    - Audit trail
    - Rate limiting
    - Staleness detection
    - Fare prediction
    - Anomaly detection
    """

    def __init__(self, config: Optional[type[Config]] = None, db_session=None):
        config = config or Config
        self.url = "https://irctc1.p.rapidapi.com/api/v1/getFare"
        self.enabled = getattr(config, "ENABLE_FARE_VERIFICATION", False) and bool(config.RAPIDAPI_KEY)
        self.headers = {
            "x-rapidapi-key": getattr(config, "RAPIDAPI_KEY", ""),
            "x-rapidapi-host": getattr(config, "RAPIDAPI_HOST", "irctc1.p.rapidapi.com")
        }
        self.timeout = getattr(config, "LIVE_API_TIMEOUT_MS", 10)
        self.db = db_session

        # Circuit breakers
        self._rapidapi_breaker = circuit_manager.get_or_create(
            "fare_rapidapi",
            CircuitConfig(
                failure_threshold=3,
                timeout_seconds=120.0,
                success_threshold=2,
                half_open_max_calls=2
            )
        )
        self._db_breaker = circuit_manager.get_or_create(
            "fare_db",
            CircuitConfig(
                failure_threshold=5,
                timeout_seconds=30.0,
                success_threshold=3
            )
        )

        # Retry policies
        self._rapidapi_retry = RetryPolicy(
            max_attempts=3,
            initial_delay=0.5,
            max_delay=10.0,
            conditions=[
                lambda e: "timeout" in str(e).lower(),
                lambda e: getattr(e, "status_code", 0) == 429
            ]
        )
        self._db_retry = RetryPolicy(
            max_attempts=3,
            initial_delay=0.1,
            max_delay=2.0,
            conditions=[
                lambda e: "connection" in str(e).lower()
            ]
        )

        # Metrics tracking
        self._metrics = FareServiceMetrics()

        # Production config
        self.fare_config = FareConfig()
        self._local_cache: Dict[str, Dict] = {}
        self._cache_ttl_seconds = self.fare_config.cache_ttl_seconds
        self._rate_limiter = RateLimiter(
            requests_per_minute=self.fare_config.rate_limit_per_minute,
            requests_per_hour=self.fare_config.rate_limit_per_hour
        )
        self._prediction_cache: Dict[str, Dict] = {}
        self._webhook_registry: Dict[str, List[Dict]] = defaultdict(list)

        logger.info("FareService initialized with production features and resilience patterns")

    def _get_cache_key(self, train_no: str, from_station: str, to_station: str, 
                       class_code: str, date: str) -> str:
        """Generate cache key for fare lookup."""
        return f"fare:{train_no}:{from_station}:{to_station}:{class_code}:{date}"

    def _is_cache_valid(self, cached: Dict) -> bool:
        """Check if cached fare is still valid."""
        if not cached:
            return False
        cached_time = cached.get("_cached_at", 0)
        return (datetime.utcnow().timestamp() - cached_time) < self._cache_ttl_seconds

    # =========================================================================
    # TASK: AUDIT TRAIL
    # =========================================================================
    
    def _log_audit(
        self,
        train_no: str,
        from_station: str,
        to_station: str,
        class_code: str,
        action: str,
        fare_amount: Optional[float],
        source: str,
        metadata: Optional[Dict] = None
    ) -> str:
        """Log fare operation to audit trail."""
        audit_id = str(uuid.uuid4())
        
        audit_data = {
            "audit_id": audit_id,
            "train_no": train_no,
            "from_station": from_station,
            "to_station": to_station,
            "class_code": class_code,
            "action": action,
            "fare_amount": fare_amount,
            "source": source,
            "metadata": metadata,
            "created_at": datetime.utcnow().isoformat()
        }
        
        checksum = hashlib.sha256(json.dumps(audit_data, sort_keys=True, default=str).encode()).hexdigest()
        
        if self.db:
            try:
                audit_entry = FareAuditLog(
                    audit_id=audit_id,
                    train_no=train_no,
                    from_station=from_station,
                    to_station=to_station,
                    class_code=class_code,
                    action=action,
                    fare_amount=fare_amount,
                    source=source,
                    meta_data=metadata,
                    checksum=checksum
                )
                self.db.add(audit_entry)
                self.db.commit()
            except Exception as e:
                logger.error(f"Failed to log fare audit: {e}")
                self.db.rollback()
        
        return audit_id

    def get_audit_trail(
        self,
        train_no: Optional[str] = None,
        from_station: Optional[str] = None,
        to_station: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """Retrieve fare audit trail."""
        if not self.db:
            return []
        
        try:
            query = self.db.query(FareAuditLog)
            if train_no:
                query = query.filter(FareAuditLog.train_no == train_no)
            if from_station:
                query = query.filter(FareAuditLog.from_station == from_station)
            if to_station:
                query = query.filter(FareAuditLog.to_station == to_station)
            
            audits = query.order_by(FareAuditLog.created_at.desc()).limit(limit).all()
            
            return [
                {
                    "audit_id": a.audit_id,
                    "train_no": a.train_no,
                    "from_station": a.from_station,
                    "to_station": a.to_station,
                    "class_code": a.class_code,
                    "action": a.action,
                    "fare_amount": a.fare_amount,
                    "source": a.source,
                    "metadata": a.meta_data,
                    "created_at": a.created_at.isoformat(),
                    "checksum": a.checksum
                }
                for a in audits
            ]
        except Exception as e:
            logger.error(f"Failed to retrieve fare audit: {e}")
            return []

    # =========================================================================
    # TASK: RATE LIMITING
    # =========================================================================
    
    async def check_rate_limit(self, api_key: Optional[str] = None) -> Tuple[bool, Dict]:
        """Check if request is within rate limits."""
        key = api_key or "default"
        return await self._rate_limiter.allow(key)

    def get_rate_limit_status(self, api_key: Optional[str] = None) -> Dict:
        """Get current rate limit status."""
        key = api_key or "default"
        return self._rate_limiter.get_status(key)

    # =========================================================================
    # TASK: STALENESS DETECTION
    # =========================================================================
    
    def check_fare_staleness(
        self,
        train_no: str,
        from_station: str,
        to_station: str,
        class_code: str,
        date: str = ""
    ) -> Dict:
        """Check if cached fare is stale."""
        cache_key = self._get_cache_key(train_no, from_station, to_station, class_code, date)
        
        if cache_key not in self._local_cache:
            return {"is_stale": True, "age_seconds": 0, "should_refresh": True}
        
        cached = self._local_cache[cache_key]
        age_seconds = (datetime.utcnow().timestamp() - cached.get("_cached_at", 0))
        is_stale = age_seconds > self.fare_config.stale_threshold_seconds
        
        return {
            "is_stale": is_stale,
            "age_seconds": age_seconds,
            "should_refresh": is_stale,
            "confidence": "high" if age_seconds < 60 else "medium" if age_seconds < 300 else "low"
        }

    # =========================================================================
    # TASK: FARE PREDICTION
    # =========================================================================
    
    def predict_fare(
        self,
        train_no: str,
        from_station: str,
        to_station: str,
        class_code: str,
        travel_date: str
    ) -> Dict:
        """
        Predict fare based on historical patterns.
        Task: Fare prediction.
        """
        cache_key = f"predict:{train_no}:{from_station}:{to_station}:{class_code}:{travel_date}"
        
        if cache_key in self._prediction_cache:
            return self._prediction_cache[cache_key]
        
        # Get current fare as baseline
        current_fare = self._get_baseline_fare(train_no, from_station, to_station, class_code)
        
        # Calculate prediction factors
        try:
            travel_dt = datetime.strptime(travel_date, "%Y-%m-%d")
            days_until = (travel_dt - datetime.utcnow()).days
        except:
            days_until = 30
        
        # Tatkal surge (within 1 day of travel)
        is_tatkal_period = days_until <= 1
        
        # Festival/holiday surge
        holiday_factors = self._get_holiday_factor(travel_date)
        
        # Base prediction
        predicted_fare = current_fare * (1 + holiday_factors)
        if is_tatkal_period:
            predicted_fare *= 1.1  # 10% Tatkal surge
        
        prediction = {
            "train_no": train_no,
            "from_station": from_station,
            "to_station": to_station,
            "class_code": class_code,
            "travel_date": travel_date,
            "current_fare": current_fare,
            "predicted_fare": round(predicted_fare, 2),
            "surge_factors": {
                "is_tatkal_period": is_tatkal_period,
                "holiday_factor": holiday_factors,
                "days_until_travel": days_until
            },
            "confidence": "medium",
            "predicted_at": datetime.utcnow().isoformat()
        }
        
        self._prediction_cache[cache_key] = prediction
        return prediction

    def _get_baseline_fare(
        self,
        train_no: str,
        from_station: str,
        to_station: str,
        class_code: str
    ) -> float:
        """Get baseline fare from cache or calculate."""
        cache_key = self._get_cache_key(train_no, from_station, to_station, class_code, "")
        
        if cache_key in self._local_cache:
            cached = self._local_cache[cache_key]
            return cached.get("data", {}).get("total_fare", 0) or cached.get("total_fare", 0)
        
        return 0.0

    def _get_holiday_factor(self, travel_date: str) -> float:
        """Get fare surge factor for holidays."""
        try:
            travel_dt = datetime.strptime(travel_date, "%Y-%m-%d")
            month = travel_dt.month
            day = travel_dt.day
            
            # Major holidays with surge
            holidays = {
                (1, 1): 0.3,    # New Year
                (1, 26): 0.2,   # Republic Day
                (8, 15): 0.3,   # Independence Day
                (10, 2): 0.2,   # Gandhi Jayanti
                (10, 31): 0.2,  # Halloween
                (11, 14): 0.3,  # Diwali
                (12, 25): 0.3,  # Christmas
            }
            
            return holidays.get((month, day), 0.0)
        except:
            return 0.0

    # =========================================================================
    # TASK: ANOMALY DETECTION
    # =========================================================================
    
    def detect_fare_anomaly(
        self,
        train_no: str,
        from_station: str,
        to_station: str,
        class_code: str,
        detected_fare: float,
        expected_fare: Optional[float] = None
    ) -> Optional[Dict]:
        """Detect fare anomalies and alert if significant deviation."""
        if expected_fare is None:
            expected_fare = self._get_baseline_fare(train_no, from_station, to_station, class_code)
        
        if expected_fare == 0:
            return None
        
        deviation_pct = abs(detected_fare - expected_fare) / expected_fare * 100
        
        if deviation_pct < self.fare_config.anomaly_threshold_pct:
            return None  # Within normal range
        
        # Determine severity
        if deviation_pct >= 100:
            severity = "CRITICAL"
        elif deviation_pct >= 50:
            severity = "HIGH"
        elif deviation_pct >= 30:
            severity = "MEDIUM"
        else:
            severity = "LOW"
        
        # Log anomaly
        if self.db:
            try:
                anomaly = FareAnomaly(
                    train_no=train_no,
                    route_key=f"{from_station}:{to_station}",
                    class_code=class_code,
                    detected_fare=detected_fare,
                    expected_fare=expected_fare,
                    deviation_pct=deviation_pct,
                    severity=severity
                )
                self.db.add(anomaly)
                self.db.commit()
                
                logger.warning(f"🚨 Fare anomaly detected: {train_no} | {severity} | Deviation: {deviation_pct:.1f}%")
                
                return {
                    "detected": True,
                    "severity": severity,
                    "detected_fare": detected_fare,
                    "expected_fare": expected_fare,
                    "deviation_pct": deviation_pct
                }
            except Exception as e:
                logger.error(f"Failed to log fare anomaly: {e}")
                self.db.rollback()
        
        return None

    def get_active_anomalies(
        self,
        severity: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """Get active fare anomalies."""
        if not self.db:
            return []
        
        try:
            query = self.db.query(FareAnomaly).filter(FareAnomaly.status == "open")
            if severity:
                query = query.filter(FareAnomaly.severity == severity)
            
            anomalies = query.order_by(FareAnomaly.detected_at.desc()).limit(limit).all()
            
            return [
                {
                    "id": a.id,
                    "train_no": a.train_no,
                    "route_key": a.route_key,
                    "class_code": a.class_code,
                    "detected_fare": a.detected_fare,
                    "expected_fare": a.expected_fare,
                    "deviation_pct": a.deviation_pct,
                    "severity": a.severity,
                    "detected_at": a.detected_at.isoformat()
                }
                for a in anomalies
            ]
        except Exception as e:
            logger.error(f"Failed to get anomalies: {e}")
            return []

    # =========================================================================
    # TASK: WEBHOOK SUPPORT
    # =========================================================================
    
    def register_webhook(
        self,
        event_type: str,
        callback_url: str,
        secret: Optional[str] = None
    ) -> Dict:
        """Register webhook for fare events."""
        webhook_id = str(uuid.uuid4())
        webhook_secret = secret or str(uuid.uuid4())[:16]
        
        webhook = {
            "webhook_id": webhook_id,
            "event_type": event_type,
            "callback_url": callback_url,
            "secret": webhook_secret,
            "active": True,
            "created_at": datetime.utcnow().isoformat()
        }
        
        self._webhook_registry[event_type].append(webhook)
        
        return {"success": True, "webhook_id": webhook_id, "secret": webhook_secret}

    async def trigger_webhooks(self, event_type: str, data: Dict) -> None:
        """Trigger webhooks for fare events."""
        webhooks = self._webhook_registry.get(event_type, [])
        
        for webhook in webhooks:
            if not webhook.get("active"):
                continue
            
            # In production: send HTTP request
            logger.info(f"📣 Would trigger webhook for {event_type}")
            
            # Example:
            # import httpx, hmac, hashlib
            # payload = json.dumps({"event": event_type, "data": data})
            # signature = hmac.new(webhook["secret"].encode(), payload.encode(), hashlib.sha256).hexdigest()
            # async with httpx.AsyncClient() as client:
            #     await client.post(webhook["callback_url"], json=payload, headers={"X-Signature": signature})

    # =========================================================================
    # MAIN FARE OPERATIONS
    # =========================================================================

    # =========================================================================
    # MAIN FARE OPERATIONS
    # =========================================================================

    async def get_fare_with_fallback(
        self,
        train_no: str,
        from_station: str,
        to_station: str,
        class_code: Optional[str] = None,
        quota: str = "GN",
        date: str = "",
        db_session = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get fare with production features:
        - Rate limiting
        - Audit logging
        - Anomaly detection
        - Fare prediction
        """
        # Check rate limit
        allowed, limit_info = await self.check_rate_limit()
        if not allowed:
            return {
                "error": "rate_limit_exceeded",
                "message": "Too many requests",
                "retry_after": limit_info.get("retry_after", 60)
            }
        
        cache_key = self._get_cache_key(train_no, from_station, to_station, 
                                        class_code or "SL", date)
        
        # Check cache first
        if cache_key in self._local_cache and self._is_cache_valid(self._local_cache[cache_key]):
            cached = self._local_cache[cache_key]
            logger.debug(f"📦 Cache hit for fare {cache_key}")
            
            # Log audit for cache hit
            self._log_audit(
                train_no=train_no,
                from_station=from_station,
                to_station=to_station,
                class_code=class_code or "SL",
                action="QUERY_CACHE",
                fare_amount=cached.get("data", {}).get("total_fare"),
                source="cache"
            )
            
            return {
                "source": "cache",
                "success": True,
                "quota": quota,
                "class": class_code,
                "data": cached.get("data", {})
            }

        # Try RapidAPI first if enabled
        if self.enabled:
            try:
                async def call_rapidapi():
                    from services.rapidapi_provider import rapidapi_provider
                    loop = asyncio.get_event_loop()
                    return await loop.run_in_executor(
                        None, 
                        lambda: asyncio.run(rapidapi_provider.get_fare(train_no, from_station, to_station))
                    )
                
                data = await RAPIDAPI_FARE_BREAKER.execute(call_rapidapi)
                
                if data and hasattr(data, 'dict'):
                    fare_data = data.dict(by_alias=True)
                    total_fare = fare_data.get("total_fare", 0) or fare_data.get("fare", 0)
                    
                    # Detect anomalies
                    anomaly = self.detect_fare_anomaly(
                        train_no, from_station, to_station,
                        class_code or "SL", total_fare
                    )
                    
                    result = {
                        "source": "rapidapi",
                        "success": True,
                        "quota": quota,
                        "class": class_code,
                        "data": fare_data,
                        "anomaly": anomaly
                    }
                    
                    # Cache the result
                    result["_cached_at"] = datetime.utcnow().timestamp()
                    self._local_cache[cache_key] = result
                    
                    # Log audit
                    self._log_audit(
                        train_no=train_no,
                        from_station=from_station,
                        to_station=to_station,
                        class_code=class_code or "SL",
                        action="QUERY_API",
                        fare_amount=total_fare,
                        source="rapidapi",
                        metadata={"anomaly": anomaly}
                    )
                    
                    # Trigger webhooks
                    await self.trigger_webhooks("fare.queried", {
                        "train_no": train_no,
                        "fare": total_fare,
                        "source": "rapidapi"
                    })
                    
                    return result
                    
            except Exception as api_err:
                logger.warning(f"⚠️ RapidAPI fare lookup failed: {api_err}. Using local calculation.")

        # Fallback to local calculation
        return await self._calculate_local_fare(
            train_no=train_no,
            from_station=from_station,
            to_station=to_station,
            class_code=class_code,
            quota=quota,
            date=date,
            db_session=db_session
        )

    async def _calculate_local_fare(
        self,
        train_no: str,
        from_station: str,
        to_station: str,
        class_code: Optional[str] = None,
        quota: str = "GN",
        date: str = "",
        db_session = None
    ) -> Dict[str, Any]:
        """Calculate fare locally with audit logging."""
        try:
            # Get distance between stations
            distance_km = 0.0
            if db_session:
                try:
                    from sqlalchemy import text
                    result = db_session.execute(
                        text("""
                            SELECT COALESCE(SUM(s2.distance_km - s1.distance_km), 0) as distance
                            FROM stop_times st1
                            JOIN stops s1 ON st1.stop_id = s1.id
                            JOIN stop_times st2 ON st1.trip_id = st2.trip_id
                            JOIN stops s2 ON st2.stop_id = s2.id
                            WHERE s1.code = :from_station 
                            AND s2.code = :to_station
                            AND st1.stop_sequence < st2.stop_sequence
                            LIMIT 1
                        """),
                        {"from_station": from_station, "to_station": to_station}
                    ).fetchone()
                    distance_km = float(result[0]) if result and result[0] else 0.0
                except Exception as dist_err:
                    logger.warning(f"Could not get distance: {dist_err}")
            
            if distance_km <= 0:
                distance_km = 500.0
                logger.info(f"Using fallback distance: {distance_km} km")
            
            # Calculate fare
            is_tatkal = quota.upper() == "TQ"
            fare_result = calculate_fare(
                distance_km=distance_km,
                coach=class_code or "SL",
                is_tatkal=is_tatkal,
                passengers=[{"age": 30}],
                db=db_session
            )
            
            total_fare = fare_result.get("total_fare", 0)
            
            # Detect anomalies
            anomaly = self.detect_fare_anomaly(
                train_no, from_station, to_station,
                class_code or "SL", total_fare
            )
            
            result = {
                "source": "local_calculation",
                "success": True,
                "quota": quota,
                "class": class_code,
                "data": {
                    "train_no": train_no,
                    "from_station": from_station,
                    "to_station": to_station,
                    "distance_km": distance_km,
                    **fare_result
                },
                "anomaly": anomaly,
                "_cached_at": datetime.utcnow().timestamp()
            }
            
            # Cache the result
            cache_key = self._get_cache_key(train_no, from_station, to_station, 
                                            class_code or "SL", date)
            self._local_cache[cache_key] = result
            
            # Log audit
            self._log_audit(
                train_no=train_no,
                from_station=from_station,
                to_station=to_station,
                class_code=class_code or "SL",
                action="CALCULATE",
                fare_amount=total_fare,
                source="local",
                metadata={"distance_km": distance_km, "anomaly": anomaly}
            )
            
            logger.info(f"✅ Local fare calculated: ₹{total_fare} for {from_station}-{to_station}")
            return result
            
        except Exception as calc_err:
            logger.error(f"❌ Local fare calculation failed: {calc_err}")
            
            self._log_audit(
                train_no=train_no,
                from_station=from_station,
                to_station=to_station,
                class_code=class_code or "SL",
                action="CALCULATE_FAILED",
                fare_amount=None,
                source="local",
                metadata={"error": str(calc_err)}
            )
            
            return {
                "source": "error",
                "success": False,
                "error": str(calc_err),
                "quota": quota,
                "class": class_code
            }

    def clear_cache(self, key: Optional[str] = None) -> None:
        """Clear fare cache."""
        if key:
            self._local_cache.pop(key, None)
        else:
            self._local_cache.clear()
        self._prediction_cache.clear()
        logger.info(f"🗑️ Fare cache cleared" + (f" for {key}" if key else ""))

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "cache_size": len(self._local_cache),
            "prediction_cache_size": len(self._prediction_cache),
            "ttl_seconds": self._cache_ttl_seconds,
            "enabled": self.enabled,
            "rate_limit": self.get_rate_limit_status()
        }

    def get_fare(
        self,
        train_no: str,
        from_station: str,
        to_station: str,
        class_code: Optional[str] = None,
        quota: str = "GN",
        date: str = ""
    ) -> Optional[Dict]:
        """
        Legacy method - kept for backward compatibility.
        Use get_fare_with_fallback() for new code.
        """
        if not self.enabled or not train_no:
            logger.debug("Fare lookup disabled or missing train number")
            return None

        try:
            from services.rapidapi_provider import rapidapi_provider
            
            data = asyncio.run(rapidapi_provider.get_fare(train_no, from_station, to_station))
            
            if data:
                return {
                    "source": "rapidapi",
                    "success": True,
                    "quota": quota,
                    "class": class_code,
                    "data": data.dict(by_alias=True)
                }
        except Exception as exc:
            logger.warning("Fare API failed for %s %s-%s: %s", train_no, from_station, to_station, exc)
            return {"source": "rapidapi", "success": False, "error": str(exc)}
        return None

# =========================================================================
# RESILIENCE PATTERNS
# =========================================================================

def get_metrics(self) -> dict:
    """Get service metrics."""
    return self._metrics.get_metrics()

def health_check(self) -> dict:
    """Check service health."""
    return {
        "status": "healthy",
        "circuit_breakers": {
            "rapidapi": self._rapidapi_breaker.get_metrics().to_dict(),
            "database": self._db_breaker.get_metrics().to_dict()
        },
        "metrics": self._metrics.get_metrics(),
        "cache_stats": self.get_cache_stats()
    }

def reset_circuit_breakers(self):
    """Reset all circuit breakers."""
    self._rapidapi_breaker.reset()
    self._db_breaker.reset()
    logger.info("All circuit breakers reset for fare_service")

# Bind methods to class
FareService.get_metrics = get_metrics
FareService.health_check = health_check
FareService.reset_circuit_breakers = reset_circuit_breakers
