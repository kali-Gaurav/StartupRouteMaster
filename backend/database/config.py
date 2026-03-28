import os
import logging
from pathlib import Path
from typing import Any, Dict
from dotenv import load_dotenv

# Load .env from backend root
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

logger = logging.getLogger("routemaster.config")

class ConfigMeta(type):
    """Metaclass to handle lazy attribute access for the Config class."""
    def __getattr__(cls, name):
        return cls._instance._get_env(name)

class Config(metaclass=ConfigMeta):
    """
    Task 3: Consolidated Lazy Configuration.
    Optimized for VPS: Loads environment variables only on first access.
    """
    _cache: Dict[str, Any] = {}
    BASE_DIR = str(Path(__file__).resolve().parent.parent)
    _base_path = Path(BASE_DIR)
    
    # [User Request] Reverted to Project-Relative Storage
    DATA_DIR = os.path.join(BASE_DIR, "database")
    _data_path = Path(DATA_DIR)
    
    # Determine if we are in SLIM_MODE (VPS optimized)
    SLIM_MODE = os.getenv("SLIM_MODE", "true").lower() in ("1", "true", "yes")
    ENVIRONMENT = os.getenv("ENVIRONMENT", "production").lower()
    
    # Task 41: Performance Paths (Now within project directory)
    MEMMAP_DIR = os.path.join(DATA_DIR, "memmap")
    SNAPSHOT_DIR = os.path.join(DATA_DIR, "snapshots")
    DB_DIR = DATA_DIR # Root database folder

    @classmethod
    def _get_env(cls, key: str, default: Any = None, cast_type: type = str) -> Any:
        if key in cls._cache:
            return cls._cache[key]
        
        val = os.getenv(key)
        if val is None:
            # Handle special cases for SLIM_MODE defaults
            if key == "DB_POOL_SIZE": default = 5 if cls.SLIM_MODE else 20
            if key == "DB_MAX_OVERFLOW": default = 2 if cls.SLIM_MODE else 10
            if cls.SLIM_MODE and key in ("KAFKA_ENABLE_EVENTS", "REDIS_SNAPSHOT_ENABLED"): default = False
            res = default
        else:
            if cast_type == bool or isinstance(default, bool):
                res = val.lower() in ("1", "true", "yes")
            else:
                try:
                    res = cast_type(val)
                except (ValueError, TypeError):
                    res = default
        
        cls._cache[key] = res
        return res

    @classmethod
    def GET_SQLALCHEMY_URL(cls, db_type: str = "user", is_async: bool = True) -> str:
        url = cls._get_env("DATABASE_URL", "")
        
        # Simplified path resolution using project DIR
        def resolve_db_path(filename):
            return Path(cls.DB_DIR) / filename
            
        # Transit DB [Task 121]
        if db_type == "transit":
            db_path = resolve_db_path("transit_graph.db")
            if is_async: return f"sqlite+aiosqlite:///{db_path}"
            return f"sqlite:///{db_path}"

        if url and (cls.ENVIRONMENT == "production" or "postgresql" in url):
            if is_async and "postgresql" in url:
                if "asyncpg" not in url:
                    url = url.replace("postgresql://", "postgresql+asyncpg://")
                # [Issue 7] asyncpg doesn't support query-param sslmode consistently across environments
                # We strip it here and handle it in session.py connect_args
                if "?" in url:
                    url = url.split("?")[0]
            
            # [Task 2] Standard Postgres Sync handling (psycopg2)
            elif "postgresql" in url and "sslmode" not in url:
                separator = "&" if "?" in url else "?"
                url = f"{url}{separator}sslmode=require"
            
            return url
        
        filename = "user_store.db" if db_type == "user" else "transit_graph.db"
        db_path = resolve_db_path(filename)
        
        # [Issue 7] Sanitize SQLite URL: Strip query params (like sslmode) that break aiosqlite/sqlite3
        if is_async:
            return f"sqlite+aiosqlite:///{db_path}"
        return f"sqlite:///{db_path}"

    @classmethod
    def get_mode(cls) -> str:
        if cls._get_env("OFFLINE_MODE", False): return "OFFLINE"
        has_fares = bool(cls._get_env("LIVE_FARES_API", None))
        has_delays = bool(cls._get_env("LIVE_DELAY_API", None))
        has_seats = bool(cls._get_env("LIVE_SEAT_API", None))
        return "ONLINE" if (has_fares and has_delays and has_seats) else "HYBRID" if (has_fares or has_delays) else "OFFLINE"

    @classmethod
    def validate(cls):
        if cls.ENVIRONMENT != "production": return
        critical = [
            "DATABASE_URL", "REDIS_URL", "SUPABASE_URL", "SUPABASE_KEY", 
            "RAPIDAPI_KEY", "RAPIDAPI_HOST",
            "CLOUDFLARE_R2_ACCOUNT_ID", "CLOUDFLARE_R2_ACCESS_KEY_ID", "CLOUDFLARE_R2_SECRET_ACCESS_KEY"
        ]
        missing = [key for key in critical if not cls._get_env(key)]
        if missing: logger.error(f"❌ CRITICAL CONFIG MISSING: {', '.join(missing)}")

# Setup a dummy instance for the metaclass __getattr__ to work on the class itself
Config._instance = Config
