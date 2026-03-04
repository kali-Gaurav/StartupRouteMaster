import os
from dotenv import load_dotenv
import logging
from pathlib import Path

# Load .env from backend directory explicitly
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path, override=True)

class Config:
    # System Mode (Read from environment, default to False for production readiness)
    OFFLINE_MODE = os.getenv("OFFLINE_MODE", "false").lower() in ("1", "true", "yes")

    # Supabase Configuration
    SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
    SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
    
    # Database Configuration (Railway / Supabase Postgres)
    DATABASE_URL = os.getenv("DATABASE_URL", "")
    READ_DATABASE_URL = os.getenv("READ_DATABASE_URL", "")
    
    # Connection Pool Settings
    DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "20"))
    DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "10"))
    DB_POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "1800"))
    DB_POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))
    
    # Redis Configuration (Upstash / Cloud Redis)
    REDIS_URL = os.getenv("REDIS_URL", "")
    REDIS_SESSION_EXPIRY_SECONDS = int(os.getenv("REDIS_SESSION_EXPIRY_SECONDS", "3600"))
    REDIS_VERSION_PREFIX = os.getenv("REDIS_VERSION_PREFIX", "v1")
    REDIS_SNAPSHOT_ENABLED = os.getenv("REDIS_SNAPSHOT_ENABLED", "true").lower() in ("1", "true", "yes")
    REDIS_INFRASTRUCTURE_TTL = int(os.getenv("REDIS_INFRASTRUCTURE_TTL", "172800"))
    
    # JWT & Auth
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "changeme")
    JWT_REFRESH_EXPIRATION_DAYS = int(os.getenv("JWT_REFRESH_EXPIRATION_DAYS", "30"))
    
    # Payment Gateways
    RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
    RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
    PAYMENT_GATEWAY = os.getenv("PAYMENT_GATEWAY", "razorpay")
    
    # Admin & Security
    ADMIN_API_TOKEN = os.getenv("ADMIN_API_TOKEN", "default_token_change_me")
    GRAPH_HMAC_SECRET = os.getenv("GRAPH_HMAC_SECRET", "")
    
    # Cache & Search Limits
    CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "3600"))
    MAX_TRANSFERS = int(os.getenv("MAX_TRANSFERS", "3"))
    MAX_SEARCH_RESULTS = int(os.getenv("MAX_SEARCH_RESULTS", "10"))
    PARETO_LIMIT = int(os.getenv("PARETO_LIMIT", "3"))
    
    # Transfer Windows (minutes)
    TRANSFER_WINDOW_MIN = int(os.getenv("TRANSFER_WINDOW_MIN", "15"))
    TRANSFER_WINDOW_MAX = int(os.getenv("TRANSFER_WINDOW_MAX", "720"))
    
    # Phase 3: Transfer Intelligence (TODO #19)
    # Additional buffer added to minimum transfer times to handle typical delays.
    DELAY_BUFFER_MINUTES = int(os.getenv("DELAY_BUFFER_MINUTES", "15"))
    
    # Transfer graph enrichment
    NEARBY_TRANSFER_RADIUS_KM = float(os.getenv("NEARBY_TRANSFER_RADIUS_KM", "1.25"))
    KEY_HUB_TRANSFER_PAIRS = os.getenv("KEY_HUB_TRANSFER_PAIRS", "NDLS:NZM,BCT:SBC,CSMT:KYN")
    PLATFORM_TRANSFER_JUNCTIONS = os.getenv("PLATFORM_TRANSFER_JUNCTIONS", "NDLS,BCT,CSMT,NZM")
    PLATFORM_TRANSFER_EDGE_COUNT = int(os.getenv("PLATFORM_TRANSFER_EDGE_COUNT", "4"))
    
    # RAPTOR Sampling & Dominance
    RAPTOR_DEFAULT_INITIAL_DEPARTURES = int(os.getenv("RAPTOR_DEFAULT_INITIAL_DEPARTURES", "200"))
    RAPTOR_DEFAULT_ONWARD_DEPARTURES = int(os.getenv("RAPTOR_DEFAULT_ONWARD_DEPARTURES", "100"))
    RAPTOR_DEFAULT_STOP_SAMPLING_INTERVAL = int(os.getenv("RAPTOR_DEFAULT_STOP_SAMPLING_INTERVAL", "5"))
    RAPTOR_MAX_INITIAL_DEPARTURES = int(os.getenv("RAPTOR_MAX_INITIAL_DEPARTURES", "600"))
    RAPTOR_MAX_ONWARD_DEPARTURES = int(os.getenv("RAPTOR_MAX_ONWARD_DEPARTURES", "400"))
    RAPTOR_MAX_STOP_SAMPLING_INTERVAL = int(os.getenv("RAPTOR_MAX_STOP_SAMPLING_INTERVAL", "30"))
    DISABLE_DOMINANCE_PRUNING = os.getenv("DISABLE_DOMINANCE_PRUNING", "false").lower() in ("1", "true", "yes")

    # Turbo / FastRouter tuning
    TURBO_TIME_WINDOW_MINUTES = int(os.getenv("TURBO_TIME_WINDOW_MINUTES", "720"))

    # RAPTOR diagnostics
    RAPTOR_DEBUG = os.getenv("RAPTOR_DEBUG", "false").lower() in ("1", "true", "yes")

    # Fallback tuning
    ROUTE_ENGINE_RAPTOR_FALLBACK_MIN_FAST_ROUTES = int(os.getenv("ROUTE_ENGINE_RAPTOR_FALLBACK_MIN_FAST_ROUTES", "-1"))

    # Route Scoring Weights
    FEASIBILITY_WEIGHT_TIME = float(os.getenv("FEASIBILITY_WEIGHT_TIME", "1.0"))
    FEASIBILITY_WEIGHT_COST = float(os.getenv("FEASIBILITY_WEIGHT_COST", "0.01"))
    FEASIBILITY_WEIGHT_COMFORT = float(os.getenv("FEASIBILITY_WEIGHT_COMFORT", "0.5"))
    FEASIBILITY_WEIGHT_TRANSFERS = float(os.getenv("FEASIBILITY_WEIGHT_TRANSFERS", "5.0"))
    NIGHT_LAYOVER_PENALTY = float(os.getenv("NIGHT_LAYOVER_PENALTY", "1.0"))
    FEASIBILITY_WEIGHT_DELAY = float(os.getenv("FEASIBILITY_WEIGHT_DELAY", "0.1"))
    ROUTE_RELIABILITY_WEIGHT = float(os.getenv("ROUTE_RELIABILITY_WEIGHT", "0.0"))

    # ML Model paths (Resolved relative to backend root)
    _base = Path(__file__).resolve().parent.parent
    _ml_base = _base / "core" / "ml_models"
    ROUTE_RANKING_MODEL_PATH = str(_ml_base / os.getenv("ROUTE_RANKING_MODEL_PATH", "route_ranking_model.pkl"))
    DELAY_PREDICTOR_MODEL_PATH = str(_ml_base / os.getenv("DELAY_PREDICTOR_MODEL_PATH", "delay_predictor_model.pkl"))
    TATKAL_DEMAND_MODEL_PATH = str(_ml_base / os.getenv("TATKAL_DEMAND_MODEL_PATH", "tatkal_demand_model.pkl"))

    # Kafka Configuration
    KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "")
    KAFKA_ENABLE_EVENTS = os.getenv("KAFKA_ENABLE_EVENTS", "false").lower() in ("1", "true", "yes")
    KAFKA_REQUEST_TIMEOUT_MS = int(os.getenv("KAFKA_REQUEST_TIMEOUT_MS", "5000"))

    # External APIs
    RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")
    RAPIDAPI_HOST = os.getenv("RAPIDAPI_HOST", "irctc1.p.rapidapi.com")
    RAPIDAPI_PREFERRED_VERSION = os.getenv("RAPIDAPI_PREFERRED_VERSION", "")
    LIVE_SEAT_API = os.getenv("LIVE_SEAT_API", None)
    LIVE_FARES_API = os.getenv("LIVE_FARES_API", None)
    LIVE_DELAY_API = os.getenv("LIVE_DELAY_API", None)
    LIVE_BOOKING_API = os.getenv("LIVE_BOOKING_API", None)
    
    # Real-time / NTES
    LIVE_STATUS_BASE_URL = os.getenv("LIVE_STATUS_BASE_URL", "https://rappid.in/apis/train.php")
    ENABLE_LIVE_STATUS = os.getenv("ENABLE_LIVE_STATUS", "true").lower() in ("1", "true", "yes")
    ENABLE_SEAT_VERIFICATION = os.getenv("ENABLE_SEAT_VERIFICATION", "true").lower() in ("1", "true", "yes")
    ENABLE_FARE_VERIFICATION = os.getenv("ENABLE_FARE_VERIFICATION", "true").lower() in ("1", "true", "yes")
    VERIFICATION_CACHE_TTL = int(os.getenv("VERIFICATION_CACHE_TTL", "180"))
    REALTIME_API_URL = os.getenv("REALTIME_API_URL", "")
    NTES_API_KEY = os.getenv("NTES_API_KEY", "")
    NTES_BASE_URL = os.getenv("NTES_BASE_URL", "")
    GPS_API_ENDPOINT = os.getenv("GPS_API_ENDPOINT", "")
    
    # Telegram Bot Configuration
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
    EMERGENCY_ADMIN_NUMBER = os.getenv("EMERGENCY_ADMIN_NUMBER", "+91-ADMIN-DEFAULT")
    
    # Timeouts & Retries
    LIVE_API_TIMEOUT_MS = int(os.getenv("LIVE_API_TIMEOUT_MS", "5000"))
    LIVE_API_RETRY_COUNT = int(os.getenv("LIVE_API_RETRY_COUNT", "2"))
    EXTERNAL_API_TIMEOUT_MS = int(os.getenv("EXTERNAL_API_TIMEOUT_MS", "500"))
    SIMULATE_AVAILABILITY_CHECK_FAILURE_RATE = float(os.getenv("SIMULATE_AVAILABILITY_CHECK_FAILURE_RATE", "0.1"))

    # Route Engine configuration
    ROUTE_GRAPH_REDIS_KEY = os.getenv("ROUTE_GRAPH_REDIS_KEY", "route_engine:graph")
    ROUTEENGINE_ASYNC_WARMUP = os.getenv("ROUTEENGINE_ASYNC_WARMUP", "true").lower() in ("1", "true", "yes")
    USE_NEW_ROUTING_ENGINE = os.getenv("USE_NEW_ROUTING_ENGINE", "true").lower() in ("1", "true", "yes")
    ROUTE_ENGINE_LOG_BOTH = os.getenv("ROUTE_ENGINE_LOG_BOTH", "false").lower() in ("1", "true", "yes")

    # Engine workflow toggles
    ROUTE_ENGINE_ENABLE_TURBO = os.getenv("ROUTE_ENGINE_ENABLE_TURBO", "true").lower() in ("1", "true", "yes")
    ROUTE_ENGINE_ENABLE_FAST_ROUTER = os.getenv("ROUTE_ENGINE_ENABLE_FAST_ROUTER", "true").lower() in ("1", "true", "yes")
    ROUTE_ENGINE_ENABLE_HYBRID_RAPTOR_FALLBACK = os.getenv("ROUTE_ENGINE_ENABLE_HYBRID_RAPTOR_FALLBACK", "true").lower() in ("1", "true", "yes")

    # Reconciliation & Health
    INVENTORY_RECONCILIATION_INTERVAL_SECONDS = int(os.getenv("INVENTORY_RECONCILIATION_INTERVAL_SECONDS", "900"))
    PAYMENT_RECONCILIATION_INTERVAL_MINUTES = int(os.getenv("PAYMENT_RECONCILIATION_INTERVAL_MINUTES", "15"))
    PARTNER_HEALTH_CHECK_INTERVAL_MINUTES = int(os.getenv("PARTNER_HEALTH_CHECK_INTERVAL_MINUTES", "5"))

    # Booking configuration
    BOOKING_ENABLED = os.getenv("BOOKING_ENABLED", "true").lower() in ("1", "true", "yes")
    
    # Environment
    ENVIRONMENT = os.getenv("ENVIRONMENT", "production")
    DEBUG = os.getenv("DEBUG", "false").lower() in ("1", "true", "yes") or ENVIRONMENT == "development"
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    # RouteMaster Agent
    RMA_URL = os.getenv("RMA_URL", "http://routemaster_agent:8008")
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

    # Circuit Breakers
    OPENROUTER_CIRCUIT_BREAKER_FAILURE_THRESHOLD = int(os.getenv("OPENROUTER_CIRCUIT_BREAKER_FAILURE_THRESHOLD", "5"))
    OPENROUTER_CIRCUIT_BREAKER_RECOVERY_TIMEOUT = int(os.getenv("OPENROUTER_CIRCUIT_BREAKER_RECOVERY_TIMEOUT", "30"))
    OPENROUTER_CIRCUIT_BREAKER_EXPECTED_EXCEPTIONS = tuple(os.getenv("OPENROUTER_CIRCUIT_BREAKER_EXPECTED_EXCEPTIONS", "httpx.RequestError").split(','))
    
    RAZORPAY_CIRCUIT_BREAKER_FAILURE_THRESHOLD = int(os.getenv("RAZORPAY_CIRCUIT_BREAKER_FAILURE_THRESHOLD", "5"))
    RAZORPAY_CIRCUIT_BREAKER_RECOVERY_TIMEOUT = int(os.getenv("RAZORPAY_CIRCUIT_BREAKER_RECOVERY_TIMEOUT", "30"))
    RAZORPAY_CIRCUIT_BREAKER_EXPECTED_EXCEPTIONS = tuple(os.getenv("RAZORPAY_CIRCUIT_BREAKER_EXPECTED_EXCEPTIONS", "httpx.RequestError,httpx.HTTPStatusError").split(','))

    PARTNER_CIRAKER_FAILURE_THRESHOLD = int(os.getenv("PARTNER_CIRCUIT_BREAKER_FAILURE_THRESHOLD", "3"))
    PARTNER_CIRCUIT_BREAKER_RECOVERY_TIMEOUT = int(os.getenv("PARTNER_CIRCUIT_BREAKER_RECOVERY_TIMEOUT", "60"))
    PARTNER_CIRCUIT_BREAKER_EXPECTED_EXCEPTIONS = tuple(os.getenv("PARTNER_CIRCUIT_BREAKER_EXPECTED_EXCEPTIONS", "httpx.RequestError,httpx.HTTPStatusError,httpx.TimeoutException").split(','))

    @classmethod
    def get_mode(cls) -> str:
        """Get current system mode: OFFLINE, HYBRID, or ONLINE"""
        if cls.OFFLINE_MODE:
            return "OFFLINE"

        has_fares = bool(cls.LIVE_FARES_API)
        has_delays = bool(cls.LIVE_DELAY_API)
        has_seats = bool(cls.LIVE_SEAT_API)

        if has_fares and has_delays and has_seats:
            return "ONLINE"
        elif has_fares or has_delays or has_seats:
            return "HYBRID"
        else:
            return "OFFLINE"

    @classmethod
    def validate(cls):
        """Validate critical configuration presence."""
        if not cls.SUPABASE_URL or not cls.SUPABASE_KEY:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set (for Auth)")
        
        if not cls.DATABASE_URL:
            if cls.OFFLINE_MODE:
                logger = logging.getLogger(__name__)
                logger.warning("DATABASE_URL not set but OFFLINE_MODE enabled.")
            else:
                raise ValueError("DATABASE_URL must be set (Railway Postgres)")

        if not cls.REDIS_URL and not cls.OFFLINE_MODE:
            raise ValueError("REDIS_URL must be set (Upstash Redis)")
        
        if not cls.SUPABASE_SERVICE_KEY:
            logger = logging.getLogger(__name__)
            logger.warning("SUPABASE_SERVICE_KEY not provided; using anon key.")
