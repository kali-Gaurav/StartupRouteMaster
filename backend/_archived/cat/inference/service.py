"""
Inference Service for the Contextual Availability Transformer (CAT) system.
FastAPI-based service for real-time availability predictions.
"""

import asyncio
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from contextlib import asynccontextmanager
from collections import defaultdict
import threading

import torch
from fastapi import FastAPI, HTTPException, Depends, Header, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse, Response
from pydantic import BaseModel, Field
import redis

from ..config import settings
from ..models.transformer import CATModel, create_cat_model
from ..preprocessing.encoders import TensorPreprocessor
from ..data_collection.collector import DataCollector, create_data_collector
from ..models.schemas import (
    AvailabilityPrediction, PredictionRequest, BatchPredictionRequest,
    BatchPredictionResponse, ServiceHealth, HealthStatus, LocationInfo,
    ContributingFactor
)
from .auth import (
    Authenticator,
    AuthType,
    Permission,
    ClientPermissions,
    RateLimiter,
    AuditLogger,
    get_audit_logger,
    get_rate_limiter,
    get_authenticator
)
from .middleware import (
    RequestLoggingMiddleware,
    RequestTimingMiddleware,
    MetricsMiddleware
)
from .cache_manager import (
    PredictionCache,
    CacheManager,
    CacheConfig,
    create_prediction_cache,
    create_cache_manager
)
from .model_manager import ModelManager, create_model_manager
from ..reliability import (
    HealthChecker,
    MetricsCollector,
    AlertManager,
    CircuitBreaker,
    create_circuit_breaker
)
from ..scalability import (
    StatelessInferenceService,
    ConnectionPoolConfig,
    ConnectionPool,
    GracefulShutdownManager,
    create_connection_pool,
    AutoscalingConfig,
    KubernetesAutoscaler,
    ScalingMetrics,
    create_autoscaler,
    CanaryConfig,
    CanaryDeployment,
    create_canary_deployment
)

logger = logging.getLogger(__name__)

# Initialize security components
_audit_logger = get_audit_logger()
_authenticator = get_authenticator()
_rate_limiter = get_rate_limiter()

# Initialize reliability components
_health_checker: Optional[HealthChecker] = None
_metrics_collector: Optional[MetricsCollector] = None
_alert_manager: Optional[AlertManager] = None
_circuit_breaker: Optional[CircuitBreaker] = None


class PredictionCache:
    """
    Redis-based cache for predictions.
    
    Reduces latency for repeated requests and supports TTL-based expiration.
    """
    
    def __init__(self, redis_url: str = None, ttl_seconds: int = None):
        """
        Initialize the prediction cache.
        
        Args:
            redis_url: Redis connection URL
            ttl_seconds: Cache TTL in seconds
        """
        self.redis_url = redis_url or settings.redis_url
        self.ttl = ttl_seconds or settings.prediction_cache_ttl_seconds
        self._client = None
        self._local_cache: Dict[str, Tuple[Any, datetime]] = {}
        self._local_cache_ttl = 60  # 1 minute for local cache
        
        if self.redis_url:
            try:
                self._client = redis.from_url(self.redis_url, decode_responses=True)
                logger.info(f"Redis cache initialized at {self.redis_url}")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}. Using local cache only.")
        else:
            logger.info("Using local cache only (no Redis configured)")
    
    def _get_cache_key(self, location_id: str, prediction_time: datetime) -> str:
        """Generate a cache key for a prediction request."""
        time_str = prediction_time.isoformat()
        return f"{settings.redis_cache_prefix}pred:{location_id}:{time_str}"
    
    def get(self, location_id: str, prediction_time: datetime) -> Optional[AvailabilityPrediction]:
        """
        Get a cached prediction.
        
        Args:
            location_id: Location identifier
            prediction_time: Time of prediction
            
        Returns:
            Cached prediction or None if not found/expired
        """
        cache_key = self._get_cache_key(location_id, prediction_time)
        now = datetime.utcnow()
        
        # Check local cache first
        if cache_key in self._local_cache:
            cached_value, timestamp = self._local_cache[cache_key]
            if (now - timestamp).seconds < self._local_cache_ttl:
                logger.debug(f"Local cache hit for {cache_key}")
                return cached_value
        
        # Check Redis
        if self._client:
            try:
                cached_data = self._client.get(cache_key)
                if cached_data:
                    import json
                    data = json.loads(cached_data)
                    prediction = AvailabilityPrediction(**data)
                    
                    # Update local cache
                    self._local_cache[cache_key] = (prediction, now)
                    
                    logger.debug(f"Redis cache hit for {cache_key}")
                    return prediction
            except Exception as e:
                logger.warning(f"Redis get failed: {e}")
        
        return None
    
    def set(
        self,
        location_id: str,
        prediction_time: datetime,
        prediction: AvailabilityPrediction
    ) -> None:
        """
        Cache a prediction.
        
        Args:
            location_id: Location identifier
            prediction_time: Time of prediction
            prediction: Prediction to cache
        """
        cache_key = self._get_cache_key(location_id, prediction_time)
        now = datetime.utcnow()
        
        # Update local cache
        self._local_cache[cache_key] = (prediction, now)
        
        # Update Redis
        if self._client:
            try:
                import json
                data = prediction.model_dump()
                # Convert datetime to string for JSON
                data["prediction_time"] = data["prediction_time"].isoformat() if isinstance(data["prediction_time"], datetime) else data["prediction_time"]
                self._client.setex(cache_key, self.ttl, json.dumps(data))
                logger.debug(f"Cached prediction for {cache_key}")
            except Exception as e:
                logger.warning(f"Redis set failed: {e}")
    
    def invalidate(self, location_id: str = None) -> None:
        """
        Invalidate cached predictions.
        
        Args:
            location_id: Specific location to invalidate (or all if None)
        """
        if location_id:
            # Invalidate specific location
            keys_to_delete = [k for k in self._local_cache.keys() if f":{location_id}:" in k]
            for key in keys_to_delete:
                del self._local_cache[key]
        else:
            # Invalidate all
            self._local_cache.clear()
        
        if self._client and location_id:
            try:
                pattern = f"{settings.redis_cache_prefix}pred:{location_id}:*"
                keys = self._client.keys(pattern)
                if keys:
                    self._client.delete(*keys)
            except Exception as e:
                logger.warning(f"Redis invalidate failed: {e}")
    
    def clear(self) -> None:
        """Clear all cached predictions."""
        self.invalidate()
    
    def get_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return {
            "local_cache_size": len(self._local_cache),
            "ttl_seconds": self.ttl
        }


class RateLimiter:
    """
    Simple rate limiter for API requests.
    
    Uses a sliding window algorithm to limit requests per client.
    """
    
    def __init__(self, requests_per_minute: int = None):
        """
        Initialize the rate limiter.
        
        Args:
            requests_per_minute: Maximum requests per minute
        """
        self.max_requests = requests_per_minute or settings.rate_limit_requests_per_minute
        self._requests: Dict[str, List[float]] = defaultdict(list)
        self._lock = threading.Lock()
    
    def _cleanup_old_requests(self, client_id: str, now: float) -> None:
        """Remove requests older than 1 minute."""
        cutoff = now - 60.0
        self._requests[client_id] = [
            t for t in self._requests[client_id] if t > cutoff
        ]
    
    def is_allowed(self, client_id: str = "default") -> Tuple[bool, int]:
        """
        Check if a request is allowed.
        
        Args:
            client_id: Client identifier (e.g., API key or IP)
            
        Returns:
            Tuple of (is_allowed, remaining_requests)
        """
        now = time.time()
        
        with self._lock:
            self._cleanup_old_requests(client_id, now)
            
            if len(self._requests[client_id]) < self.max_requests:
                self._requests[client_id].append(now)
                remaining = self.max_requests - len(self._requests[client_id])
                return True, remaining
            else:
                remaining = 0
                return False, remaining
    
    def get_remaining(self, client_id: str = "default") -> int:
        """Get remaining requests for a client."""
        now = time.time()
        self._cleanup_old_requests(client_id, now)
        return max(0, self.max_requests - len(self._requests[client_id]))


# Global instances
_cache: Optional[PredictionCache] = None
_cache_manager: Optional[CacheManager] = None
_model_manager: Optional[ModelManager] = None
_rate_limiter: Optional[RateLimiter] = None
_model: Optional[CATModel] = None
_preprocessor: Optional[TensorPreprocessor] = None
_collector: Optional[DataCollector] = None
_start_time: datetime = datetime.utcnow()
_predictions_count = 0

# Scalability components
_connection_pool: Optional[ConnectionPool] = None
_shutdown_manager: Optional[GracefulShutdownManager] = None
_autoscaler: Optional[KubernetesAutoscaler] = None
_canary_deployment: Optional[CanaryDeployment] = None


def get_health_checker() -> HealthChecker:
    """Get the global health checker instance."""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker(
            model_available=lambda: _model is not None and hasattr(_model, 'transformer'),
            data_collector_available=lambda: _collector is not None,
            external_apis_available=lambda: True  # Would check actual API connectivity
        )
    return _health_checker


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def get_alert_manager() -> AlertManager:
    """Get the global alert manager instance."""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager


def get_circuit_breaker() -> CircuitBreaker:
    """Get the global circuit breaker instance."""
    global _circuit_breaker
    if _circuit_breaker is None:
        _circuit_breaker = create_circuit_breaker(
            failure_threshold=5,
            recovery_timeout_seconds=30.0,
            name="external_api"
        )
    return _circuit_breaker


def get_cache() -> PredictionCache:
    """Get the global cache instance."""
    global _cache
    if _cache is None:
        _cache = create_prediction_cache()
    return _cache


def get_cache_manager() -> CacheManager:
    """Get the global cache manager instance."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = create_cache_manager()
    return _cache_manager


def get_model_manager() -> ModelManager:
    """Get the global model manager instance."""
    global _model_manager
    if _model_manager is None:
        _model_manager = create_model_manager()
        # Attach cache manager for automatic invalidation
        cache_manager = get_cache_manager()
        _model_manager.set_cache_manager(cache_manager)
    return _model_manager


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


def get_connection_pool() -> ConnectionPool:
    """Get the global connection pool instance."""
    global _connection_pool
    if _connection_pool is None:
        _connection_pool = create_connection_pool(
            ConnectionPoolConfig(
                max_connections=100,
                max_keepalive_connections=20
            )
        )
    return _connection_pool


def get_shutdown_manager() -> GracefulShutdownManager:
    """Get the global shutdown manager instance."""
    global _shutdown_manager
    if _shutdown_manager is None:
        _shutdown_manager = GracefulShutdownManager(shutdown_timeout=30.0)
    return _shutdown_manager


def get_autoscaler() -> KubernetesAutoscaler:
    """Get the global autoscaler instance."""
    global _autoscaler
    if _autoscaler is None:
        _autoscaler = create_autoscaler(
            AutoscalingConfig(
                min_replicas=2,
                max_replicas=10,
                target_request_rate=100.0,
                target_p95_latency=0.150,
                target_cpu_utilization=70.0,
                target_memory_utilization=80.0
            )
        )
    return _autoscaler


def get_canary_deployment() -> CanaryDeployment:
    """Get the global canary deployment instance."""
    global _canary_deployment
    if _canary_deployment is None:
        _canary_deployment = create_canary_deployment(
            CanaryConfig(
                initial_traffic_percentage=10.0,
                step_traffic_percentage=10.0,
                error_rate_threshold=5.0,
                latency_threshold_ms=250.0
            )
        )
    return _canary_deployment


async def get_model() -> CATModel:
    """Get the global model instance."""
    global _model
    if _model is None:
        _model = create_cat_model()
        # Try to load pretrained weights
        checkpoint_path = "checkpoints/best_model.pt"
        if os.path.exists(checkpoint_path):
            _model.load_state_dict(torch.load(checkpoint_path, map_location='cpu'))
            logger.info("Loaded pretrained model weights")
        _model.eval()
    return _model


def get_preprocessor() -> TensorPreprocessor:
    """Get the global preprocessor instance."""
    global _preprocessor
    if _preprocessor is None:
        _preprocessor = TensorPreprocessor(device='cpu')
    return _preprocessor


async def get_collector() -> DataCollector:
    """Get the global data collector instance."""
    global _collector
    if _collector is None:
        _collector = await create_data_collector()
    return _collector


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global _cache, _cache_manager, _model_manager
    global _collector, _model, _preprocessor, _rate_limiter, _start_time
    global _health_checker, _metrics_collector, _alert_manager, _circuit_breaker
    global _connection_pool, _shutdown_manager, _autoscaler, _canary_deployment
    
    # Initialize security components
    global _tls_context, _secrets_manager, _input_validator, _audit_logger
    
    # Initialize reliability components
    global _health_checker, _metrics_collector, _alert_manager, _circuit_breaker
    
    # Initialize scalability components
    global _connection_pool, _shutdown_manager, _autoscaler, _canary_deployment
    
    # Startup
    logger.info("Starting CAT Inference Service...")
    _start_time = datetime.utcnow()
    
    # Initialize cache and cache manager
    _cache = create_prediction_cache()
    _cache_manager = create_cache_manager(cache=_cache)
    
    # Initialize model manager with cache integration
    _model_manager = create_model_manager()
    _model_manager.set_cache_manager(_cache_manager)
    
    _rate_limiter = RateLimiter()
    _preprocessor = TensorPreprocessor(device='cpu')
    _collector = await create_data_collector()
    _model = create_cat_model()
    
    # Initialize reliability components
    _health_checker = HealthChecker(
        model_available=lambda: _model is not None and hasattr(_model, 'transformer'),
        data_collector_available=lambda: _collector is not None,
        external_apis_available=lambda: True
    )
    _metrics_collector = MetricsCollector()
    _alert_manager = AlertManager()
    _circuit_breaker = create_circuit_breaker(
        failure_threshold=5,
        recovery_timeout_seconds=30.0,
        name="external_api"
    )
    
    # Initialize scalability components
    _connection_pool = create_connection_pool(
        ConnectionPoolConfig(
            max_connections=100,
            max_keepalive_connections=20
        )
    )
    _shutdown_manager = GracefulShutdownManager(shutdown_timeout=30.0)
    _autoscaler = create_autoscaler(
        AutoscalingConfig(
            min_replicas=2,
            max_replicas=10,
            target_request_rate=100.0,
            target_p95_latency=0.150,
            target_cpu_utilization=70.0,
            target_memory_utilization=80.0
        )
    )
    _canary_deployment = create_canary_deployment(
        CanaryConfig(
            initial_traffic_percentage=10.0,
            step_traffic_percentage=10.0,
            error_rate_threshold=5.0,
            latency_threshold_ms=250.0
        )
    )
    
    # Try to load pretrained model
    checkpoint_path = "checkpoints/best_model.pt"
    if os.path.exists(checkpoint_path):
        try:
            _model.load_state_dict(torch.load(checkpoint_path, map_location='cpu'))
            logger.info("Loaded pretrained model weights")
        except Exception as e:
            logger.warning(f"Failed to load model weights: {e}")
    
    _model.eval()
    logger.info("CAT Inference Service started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down CAT Inference Service...")
    if _collector:
        await _collector.close()
    if _connection_pool:
        await _connection_pool.close()
    logger.info("CAT Inference Service stopped")


# Create FastAPI application
app = FastAPI(
    title="Contextual Availability Transformer API",
    description="Real-time availability predictions using Transformer-based machine learning",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Security Middleware
class SecurityMiddleware:
    """Middleware for security checks on incoming requests."""
    
    def __init__(self, app):
        self.app = app
        self.validator = InputValidator()
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Get request data
        request = Request(scope)
        
        # Check request size
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > self.validator.MAX_REQUEST_SIZE:
                    from fastapi.responses import JSONResponse
                    response = JSONResponse(
                        status_code=413,
                        content={"detail": "Request size exceeds limit"}
                    )
                    await response(scope, receive, send)
                    return
            except ValueError:
                pass
        
        # Continue to next middleware
        await self.app(scope, receive, send)


# Add security middleware
app.add_middleware(SecurityMiddleware)


def verify_api_key(x_api_key: str = Header(None)) -> str:
    """Verify API key for authentication."""
    auth_type, client_id, permissions = _authenticator.authenticate(x_api_key=x_api_key)
    return client_id


def verify_credentials() -> Tuple[AuthType, str, Optional[ClientPermissions]]:
    """
    Verify API key or OAuth token for authentication.
    
    Returns:
        Tuple of (auth_type, client_id, permissions)
    """
    return _authenticator.authenticate(
        x_api_key=Header(None),
        authorization=Header(None)
    )


def check_rate_limit(client_id: str = "default") -> Dict[str, str]:
    """Check rate limit and return headers."""
    is_allowed, remaining, headers = _rate_limiter.is_allowed(client_id)
    
    if not is_allowed:
        # Audit log: rate limit exceeded
        _audit_logger.log_rate_limit_event(
            client_id=client_id,
            auth_type=AuthType.NONE,
            request_count=_rate_limiter._default_limit,
            limit=_rate_limiter._default_limit
        )
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Try again in a minute. Remaining: {remaining}",
            headers=headers
        )
    
    return headers


def check_rate_limit_with_permissions(
    client_id: str,
    permissions: ClientPermissions = None
) -> Dict[str, str]:
    """Check rate limit with client-specific limits."""
    limit = permissions.rate_limit_override if permissions else None
    is_allowed, remaining, headers = _rate_limiter.is_allowed(client_id, limit)
    
    if not is_allowed:
        # Audit log: rate limit exceeded
        _audit_logger.log_rate_limit_event(
            client_id=client_id,
            auth_type=AuthType.NONE,
            request_count=limit or _rate_limiter._default_limit,
            limit=limit or _rate_limiter._default_limit
        )
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Try again in a minute. Remaining: {remaining}",
            headers=headers
        )
    
    return headers


def require_permission(permission: Permission, location_id: str = None):
    """
    Dependency that requires a specific permission.
    
    Args:
        permission: Required permission
        location_id: Optional location ID to check access for
    """
    async def check(
        credentials: Tuple[AuthType, str, Optional[ClientPermissions]] = Depends(verify_credentials)
    ) -> Tuple[AuthType, str, Optional[ClientPermissions]]:
        auth_type, client_id, permissions = credentials
        
        _authenticator.authorize(
            client_id=client_id,
            permission=permission,
            location_id=location_id,
            auth_type=auth_type
        )
        
        return credentials
    
    return check


# Request/Response Models
class PredictRequest(BaseModel):
    """Request model for single prediction."""
    location_id: str = Field(..., description="Location ID to predict")
    prediction_time: datetime = Field(..., description="Time to predict availability for")
    context_hours: int = Field(default=24, ge=1, le=168, description="Hours of context data")


class BatchPredictRequest(BaseModel):
    """Request model for batch predictions."""
    predictions: List[PredictRequest] = Field(..., min_length=1, max_length=100)


class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str
    model_loaded: bool
    data_freshness_seconds: float
    last_prediction_time: Optional[str]
    uptime_seconds: float
    cache_stats: Dict[str, int]
    rate_limit_remaining: int


class LocationListResponse(BaseModel):
    """Response model for location list."""
    locations: List[LocationInfo]
    total_count: int


# Endpoints
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint for liveness and readiness probes.
    """
    global _predictions_count
    
    model = await get_model()
    cache = get_cache()
    limiter = get_rate_limiter()
    health_checker = get_health_checker()
    
    now = datetime.utcnow()
    uptime = (now - _start_time).total_seconds()
    
    # Run health checks (synchronous)
    health_result = health_checker.run_health_checks()
    
    # Check model status
    model_loaded = model is not None and hasattr(model, 'transformer')
    
    # Get cache stats and convert to expected format
    raw_cache_stats = cache.get_stats()
    cache_stats = {
        "hits": raw_cache_stats.get("hits", 0),
        "misses": raw_cache_stats.get("misses", 0),
        "sets": raw_cache_stats.get("sets", 0),
        "invalidations": raw_cache_stats.get("invalidations", 0),
        "local_cache_size": raw_cache_stats.get("local_cache_size", 0),
        "ttl_seconds": raw_cache_stats.get("ttl_seconds", 300),
        "hit_rate_percent": raw_cache_stats.get("hit_rate_percent", 0.0)
    }
    
    # Get rate limit remaining
    rate_limit_remaining = limiter.get_remaining()
    
    # Determine health status based on health checker result
    if health_result.status == HealthStatus.HEALTHY:
        status = HealthStatus.HEALTHY
    else:
        status = health_result.status
    
    return HealthResponse(
        status=status.value,
        model_loaded=model_loaded,
        data_freshness_seconds=0.0,
        last_prediction_time=None,
        uptime_seconds=uptime,
        cache_stats=cache_stats,
        rate_limit_remaining=rate_limit_remaining
    )


@app.get("/health/ready")
async def health_readiness_check():
    """
    Health readiness check endpoint.
    
    Verifies that the service is ready to handle requests.
    """
    model = await get_model()
    health_checker = get_health_checker()
    
    # Run health checks (synchronous)
    health_result = health_checker.run_health_checks()
    
    if model is None or health_result.status != HealthStatus.HEALTHY:
        raise HTTPException(status_code=503, detail="Service not ready")
    
    return {"status": "ready"}


@app.get("/ready")
async def readiness_check():
    """
    Readiness check endpoint.
    
    Verifies that the service is ready to handle requests.
    """
    model = await get_model()
    
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    return {"status": "ready"}


@app.post("/predict", response_model=AvailabilityPrediction)
async def predict_availability(
    request: PredictRequest,
    credentials: Tuple[AuthType, str, Optional[ClientPermissions]] = Depends(verify_credentials)
):
    """
    Get availability prediction for a location and time.
    
    Returns the predicted availability probability, confidence interval,
    and contributing factors.
    """
    global _predictions_count
    
    auth_type, client_id, permissions = credentials
    
    # Audit log: request received
    _audit_logger.log_prediction_request(
        location_id=request.location_id,
        prediction_time=request.prediction_time,
        context_hours=request.context_hours,
        client_id=client_id
    )
    
    # Check rate limit with client-specific limit
    rate_limit_headers = check_rate_limit_with_permissions(client_id, permissions)
    
    start_time = time.time()
    
    # Check cache
    cache = get_cache()
    cached = cache.get(request.location_id, request.prediction_time)
    if cached:
        logger.debug(f"Cache hit for {request.location_id}")
        
        # Audit log: cached response
        _audit_logger.log_prediction_response(
            location_id=request.location_id,
            prediction_time=request.prediction_time,
            probability=cached.probability,
            confidence_lower=cached.confidence_interval[0],
            confidence_upper=cached.confidence_interval[1],
            processing_time_ms=(time.time() - start_time) * 1000
        )
        
        return cached
    
    # Get model and components
    model = await get_model()
    collector = await get_collector()
    preprocessor = get_preprocessor()
    
    # Fetch contextual data
    contextual_data = await collector.fetch_contextual_data(
        location_id=request.location_id,
        prediction_time=request.prediction_time,
        context_hours=request.context_hours
    )
    
    # Preprocess
    if contextual_data.historical_availability.records:
        pred_time = contextual_data.historical_availability.records[-1].timestamp
    else:
        pred_time = request.prediction_time
    
    (
        event_emb, weather_emb,
        historical_seq, temporal_enc
    ) = preprocessor.preprocess(
        contextual_data.event_calendar,
        contextual_data.weather,
        contextual_data.historical_availability,
        pred_time
    )
    
    model_input = preprocessor.create_model_input(
        event_emb, weather_emb, historical_seq, temporal_enc
    )
    
    # Generate prediction
    with torch.no_grad():
        output = model(model_input.unsqueeze(0))
    
    # Create prediction object
    prediction = AvailabilityPrediction(
        probability=output["probability"].item(),
        confidence_interval=(
            output["confidence_lower"].item(),
            output["confidence_upper"].item()
        ),
        contributing_factors=output.get("contributing_factors", []),
        location_id=request.location_id,
        prediction_time=request.prediction_time.isoformat() if isinstance(request.prediction_time, datetime) else str(request.prediction_time),
        model_version=settings.model_version
    )
    
    # Cache prediction
    cache.set(request.location_id, request.prediction_time, prediction)
    
    _predictions_count += 1
    
    elapsed_ms = (time.time() - start_time) * 1000
    logger.info(f"Prediction for {request.location_id} completed in {elapsed_ms:.1f}ms")
    
    # Record metrics
    metrics = get_metrics_collector()
    metrics.record_request()
    metrics.record_inference_latency(elapsed_ms / 1000)
    metrics.set_model_loaded(model is not None and hasattr(model, 'transformer'))
    
    # Check latency and create alert if needed
    alert_manager = get_alert_manager()
    alert = alert_manager.check_latency(elapsed_ms)
    if alert:
        logger.warning(f"Latency alert: {alert.title}")
    
    # Audit log: response sent
    _audit_logger.log_prediction_response(
        location_id=request.location_id,
        prediction_time=request.prediction_time,
        probability=prediction.probability,
        confidence_lower=prediction.confidence_interval[0],
        confidence_upper=prediction.confidence_interval[1],
        processing_time_ms=elapsed_ms
    )
    
    # Add rate limit headers to response
    response = JSONResponse(content=prediction.model_dump())
    response.headers.update(rate_limit_headers)
    return response


@app.post("/predict/batch", response_model=BatchPredictionResponse)
async def batch_predict(
    request: BatchPredictRequest,
    credentials: Tuple[AuthType, str, Optional[ClientPermissions]] = Depends(verify_credentials)
):
    """
    Get availability predictions for multiple locations and times.
    
    Processes predictions in parallel for efficiency.
    """
    global _predictions_count
    
    auth_type, client_id, permissions = credentials
    
    # Audit log: batch request received
    for pred_request in request.predictions:
        _audit_logger.log_prediction_request(
            location_id=pred_request.location_id,
            prediction_time=pred_request.prediction_time,
            context_hours=pred_request.context_hours,
            client_id=client_id
        )
    
    # Check rate limit with client-specific limit
    rate_limit_headers = check_rate_limit_with_permissions(client_id, permissions)
    
    start_time = time.time()
    
    # Get components
    model = await get_model()
    collector = await get_collector()
    preprocessor = get_preprocessor()
    cache = get_cache()
    
    predictions = []
    cached_count = 0
    
    # Process each request
    for pred_request in request.predictions:
        # Check cache first
        cached = cache.get(pred_request.location_id, pred_request.prediction_time)
        if cached:
            predictions.append(cached)
            cached_count += 1
            continue
        
        # Fetch contextual data
        contextual_data = await collector.fetch_contextual_data(
            location_id=pred_request.location_id,
            prediction_time=pred_request.prediction_time,
            context_hours=pred_request.context_hours
        )
        
        # Preprocess
        if contextual_data.historical_availability.records:
            pred_time = contextual_data.historical_availability.records[-1].timestamp
        else:
            pred_time = pred_request.prediction_time
        
        try:
            (
                event_emb, weather_emb,
                historical_seq, temporal_enc
            ) = preprocessor.preprocess(
                contextual_data.event_calendar,
                contextual_data.weather,
                contextual_data.historical_availability,
                pred_time
            )
            
            model_input = preprocessor.create_model_input(
                event_emb, weather_emb, historical_seq, temporal_enc
            )
            
            # Generate prediction
            with torch.no_grad():
                output = model(model_input.unsqueeze(0))
            
            prediction = AvailabilityPrediction(
                probability=output["probability"].item(),
                confidence_interval=(
                    output["confidence_lower"].item(),
                    output["confidence_upper"].item()
                ),
                contributing_factors=output.get("contributing_factors", []),
                location_id=pred_request.location_id,
                prediction_time=pred_request.prediction_time.isoformat() if isinstance(pred_request.prediction_time, datetime) else str(pred_request.prediction_time),
                model_version=settings.model_version
            )
            
            # Cache prediction
            cache.set(pred_request.location_id, pred_request.prediction_time, prediction)
            predictions.append(prediction)
            _predictions_count += 1
            
        except Exception as e:
            logger.error(f"Prediction failed for {pred_request.location_id}: {e}")
            # Return a fallback prediction
            predictions.append(AvailabilityPrediction(
                probability=0.5,
                confidence_interval=(0.3, 0.7),
                contributing_factors=[],
                location_id=pred_request.location_id,
                prediction_time=str(pred_request.prediction_time),
                model_version=settings.model_version
            ))
    
    total_time_ms = (time.time() - start_time) * 1000
    
    # Audit log: batch response sent
    for pred in predictions:
        _audit_logger.log_prediction_response(
            location_id=pred.location_id,
            prediction_time=pred.prediction_time if isinstance(pred.prediction_time, datetime) else datetime.fromisoformat(pred.prediction_time),
            probability=pred.probability,
            confidence_lower=pred.confidence_interval[0],
            confidence_upper=pred.confidence_interval[1],
            processing_time_ms=total_time_ms / max(len(predictions), 1)
        )
    
    return BatchPredictionResponse(
        predictions=predictions,
        total_time_ms=total_time_ms,
        cached_count=cached_count
    )


async def generate_predictions_stream(
    location_id: str,
    start_time: datetime,
    interval_seconds: int,
    duration_seconds: int
):
    """
    Generator function for streaming predictions.
    
    Yields prediction results at configured intervals.
    
    Args:
        location_id: Location ID to predict
        start_time: Start time for predictions
        interval_seconds: Interval between predictions
        duration_seconds: Total duration to stream
    """
    model = await get_model()
    collector = await get_collector()
    preprocessor = get_preprocessor()
    cache = get_cache()
    
    start = time.time()
    current_time = start_time
    
    while (time.time() - start) < duration_seconds:
        # Check cache first
        cached = cache.get(location_id, current_time)
        if cached:
            # Audit log: cached response
            _audit_logger.log_prediction_response(
                location_id=location_id,
                prediction_time=current_time,
                probability=cached.probability,
                confidence_lower=cached.confidence_interval[0],
                confidence_upper=cached.confidence_interval[1]
            )
            yield f"data: {cached.model_dump_json()}\n\n"
            await asyncio.sleep(interval_seconds)
            current_time = current_time + timedelta(seconds=interval_seconds)
            continue
        
        # Fetch contextual data
        try:
            contextual_data = await collector.fetch_contextual_data(
                location_id=location_id,
                prediction_time=current_time,
                context_hours=24
            )
            
            # Preprocess
            if contextual_data.historical_availability.records:
                pred_time = contextual_data.historical_availability.records[-1].timestamp
            else:
                pred_time = current_time
            
            (
                event_emb, weather_emb,
                historical_seq, temporal_enc
            ) = preprocessor.preprocess(
                contextual_data.event_calendar,
                contextual_data.weather,
                contextual_data.historical_availability,
                pred_time
            )
            
            model_input = preprocessor.create_model_input(
                event_emb, weather_emb, historical_seq, temporal_enc
            )
            
            # Generate prediction
            with torch.no_grad():
                output = model(model_input.unsqueeze(0))
            
            prediction = AvailabilityPrediction(
                probability=output["probability"].item(),
                confidence_interval=(
                    output["confidence_lower"].item(),
                    output["confidence_upper"].item()
                ),
                contributing_factors=output.get("contributing_factors", []),
                location_id=location_id,
                prediction_time=current_time.isoformat(),
                model_version=settings.model_version
            )
            
            # Cache prediction
            cache.set(location_id, current_time, prediction)
            
            # Audit log: response sent
            _audit_logger.log_prediction_response(
                location_id=location_id,
                prediction_time=current_time,
                probability=prediction.probability,
                confidence_lower=prediction.confidence_interval[0],
                confidence_upper=prediction.confidence_interval[1]
            )
            
            yield f"data: {prediction.model_dump_json()}\n\n"
            
        except Exception as e:
            logger.error(f"Streaming prediction failed: {e}")
            
            # Audit log: error
            _audit_logger.log_prediction_error(
                location_id=location_id,
                prediction_time=current_time,
                error_type="streaming_error",
                error_message=str(e)
            )
            
            yield f"data: {{\"error\": \"{str(e)}\"}}\n\n"
        
        await asyncio.sleep(interval_seconds)
        current_time = current_time + timedelta(seconds=interval_seconds)
    
    yield "data: [DONE]\n\n"


@app.get("/predict/stream")
async def stream_predictions(
    location_id: str,
    start_time: datetime,
    interval_seconds: int = 60,
    duration_seconds: int = 3600,
    credentials: Tuple[AuthType, str, Optional[ClientPermissions]] = Depends(verify_credentials)
):
    """
    Stream availability predictions using Server-Sent Events (SSE).
    
    Generates predictions at configured intervals for real-time updates.
    
    Args:
        location_id: Location ID to predict
        start_time: Start time for predictions
        interval_seconds: Interval between predictions (default: 60s)
        duration_seconds: Total duration to stream (default: 3600s = 1 hour)
    """
    auth_type, client_id, permissions = credentials
    
    # Audit log: stream request received
    _audit_logger.log_prediction_request(
        location_id=location_id,
        prediction_time=start_time,
        context_hours=24,
        client_id=client_id
    )
    
    # Check rate limit with client-specific limit
    rate_limit_headers = check_rate_limit_with_permissions(client_id, permissions)
    
    return StreamingResponse(
        generate_predictions_stream(
            location_id=location_id,
            start_time=start_time,
            interval_seconds=interval_seconds,
            duration_seconds=duration_seconds
        ),
        media_type="text/event-stream"
    )


@app.get("/locations", response_model=LocationListResponse)
async def list_locations():
    """
    List all available locations.
    
    Returns information about locations that can be queried for predictions.
    """
    # In a real implementation, this would query the location registry
    # For now, return sample locations
    locations = []
    
    for i in range(10):
        locations.append(LocationInfo(
            location_id=f"downtown_parking_{i:04d}",
            name=f"Downtown Parking Location {i}",
            capacity=500,
            latitude=40.7128 + (i * 0.01),
            longitude=-74.0060 + (i * 0.01),
            is_active=True
        ))
    
    return LocationListResponse(locations=locations, total_count=len(locations))


@app.post("/cache/invalidate")
async def invalidate_cache(location_id: str = None):
    """
    Invalidate cached predictions.
    
    If location_id is provided, only that location's cache is cleared.
    Otherwise, all cached predictions are cleared.
    """
    cache = get_cache()
    invalidated = cache.invalidate(location_id)
    
    return {
        "status": "success",
        "message": f"Cache cleared for {location_id or 'all locations'}",
        "invalidated_count": invalidated
    }


@app.get("/cache/stats")
async def get_cache_stats():
    """
    Get cache statistics.
    
    Returns cache hit/miss rates and other metrics.
    """
    cache = get_cache()
    stats = cache.get_stats()
    # Return simplified stats for API response
    return {
        "hits": stats.get("hits", 0),
        "misses": stats.get("misses", 0),
        "sets": stats.get("sets", 0),
        "invalidations": stats.get("invalidations", 0),
        "hit_rate_percent": stats.get("hit_rate_percent", 0.0),
        "local_cache_size": stats.get("local_cache_size", 0),
        "ttl_seconds": stats.get("ttl_seconds", 300)
    }


@app.post("/model/hot-swap")
async def hot_swap_model(
    new_version: str = None,
    new_stage: str = "Staging"
):
    """
    Hot-swap to a new model version.
    
    This will load the new model, test it, and switch traffic.
    Cache is automatically invalidated on successful swap.
    
    Args:
        new_version: Specific version to swap to (optional)
        new_stage: Stage of the new version
    """
    model_manager = get_model_manager()
    
    success, message = model_manager.hot_swap(
        new_version=new_version,
        new_stage=new_stage
    )
    
    if success:
        return {
            "status": "success",
            "message": message,
            "cache_invalidated": True
        }
    else:
        raise HTTPException(status_code=400, detail=message)


@app.post("/model/rollback")
async def rollback_model():
    """
    Rollback to the previous production model.
    
    Cache is automatically invalidated on successful rollback.
    """
    model_manager = get_model_manager()
    
    success, message = model_manager.rollback()
    
    if success:
        return {
            "status": "success",
            "message": message,
            "cache_invalidated": True
        }
    else:
        raise HTTPException(status_code=400, detail=message)


@app.get("/model/status")
async def get_model_status():
    """
    Get current model status.
    
    Returns information about loaded model versions and cache status.
    """
    model_manager = get_model_manager()
    cache_manager = get_cache_manager()
    
    return {
        "model_manager": model_manager.get_status(),
        "cache_manager": cache_manager.get_stats()
    }


@app.get("/metrics")
async def get_metrics():
    """
    Get service metrics.
    
    Returns Prometheus-formatted metrics for monitoring.
    """
    metrics = get_metrics_collector()
    
    # Export in Prometheus format
    prometheus_metrics = metrics.export_prometheus()
    
    return Response(
        content=prometheus_metrics,
        media_type="text/plain; charset=utf-8"
    )


@app.get("/metrics/json")
async def get_metrics_json():
    """
    Get service metrics in JSON format.
    
    Returns metrics summary for programmatic access.
    """
    metrics = get_metrics_collector()
    return metrics.get_summary()


@app.get("/health/details")
async def health_details():
    """
    Get detailed health check information.
    
    Returns comprehensive health status for all components.
    """
    health_checker = get_health_checker()
    return health_checker.get_health_details()


@app.get("/alerts")
async def get_alerts():
    """
    Get current alerts.
    
    Returns list of active alerts.
    """
    alert_manager = get_alert_manager()
    return alert_manager.get_active_alerts()


@app.get("/alerts/summary")
async def get_alerts_summary():
    """
    Get alert summary.
    
    Returns summary of alert status.
    """
    alert_manager = get_alert_manager()
    return alert_manager.get_summary()


@app.get("/scalability/health")
async def scalability_health():
    """
    Get scalability component health.
    
    Returns health status for horizontal scaling, autoscaling, and canary deployment.
    """
    connection_pool = get_connection_pool()
    shutdown_manager = get_shutdown_manager()
    autoscaler = get_autoscaler()
    canary = get_canary_deployment()
    
    return {
        "connection_pool": connection_pool.get_stats(),
        "shutdown_manager": shutdown_manager.get_stats(),
        "autoscaler": autoscaler.get_stats(),
        "canary_deployment": canary.get_metrics()
    }


@app.get("/scalability/autoscaling/spec")
async def autoscaling_spec():
    """
    Get Kubernetes autoscaling specification.
    
    Returns HPA spec for deployment.
    """
    autoscaler = get_autoscaler()
    return autoscaler.get_kubernetes_hpa_spec()


@app.get("/scalability/autoscaling/recommendation")
async def autoscaling_recommendation():
    """
    Get autoscaling recommendation based on current metrics.
    
    Returns recommended scaling action.
    """
    autoscaler = get_autoscaler()
    metrics = ScalingMetrics(
        request_rate=100.0,  # Example value
        p50_latency=0.100,
        p95_latency=0.150,
        p99_latency=0.200,
        queue_depth=5,
        cpu_utilization=50.0,
        memory_utilization=60.0,
        gpu_utilization=70.0
    )
    return autoscaler.get_scaling_recommendation(metrics)


@app.get("/scalability/canary/status")
async def canary_status():
    """
    Get canary deployment status.
    
    Returns current canary deployment state and metrics.
    """
    canary = get_canary_deployment()
    return canary.get_metrics()


@app.get("/scalability/canary/traffic-split")
async def canary_traffic_split():
    """
    Get current canary traffic split.
    
    Returns traffic distribution between baseline and canary.
    """
    canary = get_canary_deployment()
    return canary.get_traffic_split()


@app.post("/scalability/canary/record-baseline")
async def record_canary_baseline(success: bool = True, latency_ms: float = 100.0):
    """
    Record a baseline deployment request for canary comparison.
    
    Args:
        success: Whether the request succeeded
        latency_ms: Request latency in milliseconds
    """
    canary = get_canary_deployment()
    canary.record_baseline_request(success, latency_ms)
    return {"status": "success"}


@app.post("/scalability/canary/record-canary")
async def record_canary_request(success: bool = True, latency_ms: float = 100.0):
    """
    Record a canary deployment request for comparison.
    
    Args:
        success: Whether the request succeeded
        latency_ms: Request latency in milliseconds
    """
    canary = get_canary_deployment()
    canary.record_canary_request(success, latency_ms)
    return {"status": "success"}


@app.post("/scalability/canary/evaluate-step")
async def evaluate_canary_step():
    """
    Evaluate the current canary step and determine next action.
    
    Returns evaluation results and recommended action.
    """
    canary = get_canary_deployment()
    return canary.evaluate_step()


def create_inference_service() -> FastAPI:
    """
    Factory function to create the inference service FastAPI app.
    
    Returns:
        Configured FastAPI application
    """
    return app


class CATInferenceService:
    """
    Main inference service class for the CAT system.
    
    Provides a high-level interface for availability predictions
    with caching, rate limiting, model management, and scalability features.
    """
    
    def __init__(
        self,
        model: CATModel = None,
        preprocessor: TensorPreprocessor = None,
        collector: DataCollector = None,
        cache: PredictionCache = None,
        rate_limiter: RateLimiter = None,
        connection_pool: ConnectionPool = None,
        shutdown_manager: GracefulShutdownManager = None,
        autoscaler: KubernetesAutoscaler = None,
        canary_deployment: CanaryDeployment = None
    ):
        """
        Initialize the inference service.
        
        Args:
            model: CAT model instance
            preprocessor: Tensor preprocessor instance
            collector: Data collector instance
            cache: Prediction cache instance
            rate_limiter: Rate limiter instance
            connection_pool: Connection pool for external APIs
            shutdown_manager: Graceful shutdown manager
            autoscaler: Kubernetes autoscaler
            canary_deployment: Canary deployment manager
        """
        self.model = model
        self.preprocessor = preprocessor or TensorPreprocessor()
        self.collector = collector
        self.cache = cache or PredictionCache()
        self.rate_limiter = rate_limiter or RateLimiter()
        self.connection_pool = connection_pool or create_connection_pool()
        self.shutdown_manager = shutdown_manager or GracefulShutdownManager()
        self.autoscaler = autoscaler or create_autoscaler()
        self.canary_deployment = canary_deployment or create_canary_deployment()
        self._start_time = datetime.utcnow()
        self._predictions_count = 0
    
    async def initialize(self) -> None:
        """Initialize the service components."""
        if self.model is None:
            self.model = create_cat_model()
            self.model.eval()
        
        if self.collector is None:
            self.collector = await create_data_collector()
    
    async def predict(
        self,
        location_id: str,
        prediction_time: datetime,
        context_hours: int = 24
    ) -> AvailabilityPrediction:
        """
        Get availability prediction for a location and time.
        
        Args:
            location_id: Location ID to predict
            prediction_time: Time to predict availability for
            context_hours: Hours of context data
            
        Returns:
            Availability prediction
        """
        # Check cache
        cached = self.cache.get(location_id, prediction_time)
        if cached:
            return cached
        
        # Fetch contextual data
        contextual_data = await self.collector.fetch_contextual_data(
            location_id=location_id,
            prediction_time=prediction_time,
            context_hours=context_hours
        )
        
        # Preprocess
        if contextual_data.historical_availability.records:
            pred_time = contextual_data.historical_availability.records[-1].timestamp
        else:
            pred_time = prediction_time
        
        (
            event_emb, weather_emb,
            historical_seq, temporal_enc
        ) = self.preprocessor.preprocess(
            contextual_data.event_calendar,
            contextual_data.weather,
            contextual_data.historical_availability,
            pred_time
        )
        
        model_input = self.preprocessor.create_model_input(
            event_emb, weather_emb, historical_seq, temporal_enc
        )
        
        # Generate prediction
        with torch.no_grad():
            output = self.model(model_input.unsqueeze(0))
        
        prediction = AvailabilityPrediction(
            probability=output["probability"].item(),
            confidence_interval=(
                output["confidence_lower"].item(),
                output["confidence_upper"].item()
            ),
            contributing_factors=output.get("contributing_factors", []),
            location_id=location_id,
            prediction_time=prediction_time.isoformat(),
            model_version=settings.model_version
        )
        
        # Cache prediction
        self.cache.set(location_id, prediction_time, prediction)
        self._predictions_count += 1
        
        return prediction
    
    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics."""
        now = datetime.utcnow()
        uptime = (now - self._start_time).total_seconds()
        
        return {
            "predictions_total": self._predictions_count,
            "uptime_seconds": uptime,
            "predictions_per_second": self._predictions_count / max(uptime, 1),
            "cache_stats": self.cache.get_stats()
        }
    
    async def close(self) -> None:
        """Clean up resources."""
        if self.collector:
            await self.collector.close()
        if self.connection_pool:
            await self.connection_pool.close()
    
    async def record_prediction_for_scaling(self, success: bool, latency_ms: float) -> None:
        """
        Record a prediction for scaling and canary metrics.
        
        Args:
            success: Whether the prediction succeeded
            latency_ms: Prediction latency in milliseconds
        """
        # Record for autoscaling metrics
        self.autoscaler.update_metrics(ScalingMetrics(
            request_rate=1.0,  # Per-request rate
            p50_latency=latency_ms / 1000.0,
            p95_latency=latency_ms / 1000.0,
            p99_latency=latency_ms / 1000.0,
            queue_depth=0,
            cpu_utilization=50.0,
            memory_utilization=60.0,
            gpu_utilization=70.0
        ))
        
        # Record for canary deployment
        if self.canary_deployment.should_route_to_canary():
            self.canary_deployment.record_canary_request(success, latency_ms)
        else:
            self.canary_deployment.record_baseline_request(success, latency_ms)
    
    def get_scalability_stats(self) -> Dict[str, Any]:
        """Get scalability component statistics."""
        return {
            "connection_pool": self.connection_pool.get_stats(),
            "shutdown_manager": self.shutdown_manager.get_stats(),
            "autoscaler": self.autoscaler.get_stats(),
            "canary_deployment": self.canary_deployment.get_metrics()
        }


# Run with: uvicorn service:app --host 0.0.0.0 --port 8000
if __name__ == "__main__":
    import uvicorn
    
    logging.basicConfig(level=logging.INFO)
    
    uvicorn.run(
        "service:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False
    )