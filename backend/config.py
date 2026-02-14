import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
    DATABASE_URL = os.getenv("DATABASE_URL", "")
    READ_DATABASE_URL = os.getenv("READ_DATABASE_URL", "") # New: for read replicas
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_SESSION_EXPIRY_SECONDS = int(os.getenv("REDIS_SESSION_EXPIRY_SECONDS", "3600"))
    REDIS_VERSION_PREFIX = os.getenv("REDIS_VERSION_PREFIX", "v1")

    RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
    RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")

    ADMIN_API_TOKEN = os.getenv("ADMIN_API_TOKEN", "default_token_change_me")

    CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "3600"))
    MAX_TRANSFERS = int(os.getenv("MAX_TRANSFERS", "3"))
    TRANSFER_WINDOW_MIN = int(os.getenv("TRANSFER_WINDOW_MIN", "15"))
    TRANSFER_WINDOW_MAX = int(os.getenv("TRANSFER_WINDOW_MAX", "720")) # 12 hours
    MAX_SEARCH_RESULTS = int(os.getenv("MAX_SEARCH_RESULTS", "10"))

    # Pareto / multi-option search
    PARETO_LIMIT = int(os.getenv("PARETO_LIMIT", "3"))

    # Redis graph storage + HMAC signing
    GRAPH_HMAC_SECRET = os.getenv("GRAPH_HMAC_SECRET", "")
    ROUTE_GRAPH_REDIS_KEY = os.getenv("ROUTE_GRAPH_REDIS_KEY", "route_engine:graph")

    # Background warm-up (async) to reduce cold-start latency
    ROUTEENGINE_ASYNC_WARMUP = os.getenv("ROUTEENGINE_ASYNC_WARMUP", "true").lower() in ("1", "true", "yes")

    # External real-time provider (used by hybrid fallback)
    REALTIME_API_URL = os.getenv("REALTIME_API_URL", "")
    EXTERNAL_API_TIMEOUT_MS = int(os.getenv("EXTERNAL_API_TIMEOUT_MS", "500")) # New: Timeout for external API calls
    SIMULATE_AVAILABILITY_CHECK_FAILURE_RATE = float(os.getenv("SIMULATE_AVAILABILITY_CHECK_FAILURE_RATE", "0.1")) # New: Simulate failure for availability checks

    # Inventory Reconciliation
    INVENTORY_RECONCILIATION_INTERVAL_SECONDS = int(os.getenv("INVENTORY_RECONCILIATION_INTERVAL_SECONDS", "900")) # 15 minutes

    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG")
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

    # Circuit Breaker settings for OpenRouter
    OPENROUTER_CIRCUIT_BREAKER_FAILURE_THRESHOLD = int(os.getenv("OPENROUTER_CIRCUIT_BREAKER_FAILURE_THRESHOLD", "5"))
    OPENROUTER_CIRCUIT_BREAKER_RECOVERY_TIMEOUT = int(os.getenv("OPENROUTER_CIRCUIT_BREAKER_RECOVERY_TIMEOUT", "30")) # seconds
    OPENROUTER_CIRCUIT_BREAKER_EXPECTED_EXCEPTIONS = tuple(os.getenv("OPENROUTER_CIRCUIT_BREAKER_EXPECTED_EXCEPTIONS", "httpx.RequestError").split(','))

    # Circuit Breaker settings for Razorpay
    RAZORPAY_CIRCUIT_BREAKER_FAILURE_THRESHOLD = int(os.getenv("RAZORPAY_CIRCUIT_BREAKER_FAILURE_THRESHOLD", "5"))
    RAZORPAY_CIRCUIT_BREAKER_RECOVERY_TIMEOUT = int(os.getenv("RAZORPAY_CIRCUIT_BREAKER_RECOVERY_TIMEOUT", "30")) # seconds
    RAZORPAY_CIRCUIT_BREAKER_EXPECTED_EXCEPTIONS = tuple(os.getenv("RAZORPAY_CIRCUIT_BREAKER_EXPECTED_EXCEPTIONS", "httpx.RequestError,httpx.HTTPStatusError").split(','))

    @classmethod
    def validate(cls):
        if not cls.SUPABASE_URL or not cls.SUPABASE_KEY:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")
