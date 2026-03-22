
import os
from dotenv import load_dotenv
import logging
from pathlib import Path

# Load .env from backend root directory
# Current file is in backend/microservices/shared/config.py
# .env is in backend/.env
env_path = Path(__file__).resolve().parent.parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path, override=True)

class Config:
    # Path Configuration
    BASE_DIR = str(Path(__file__).resolve().parent.parent.parent.parent)
    _base = Path(BASE_DIR)

    # Environment
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    # Supabase Configuration
    SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
    SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
    SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")
    
    # Database Configuration
    DATABASE_URL = os.getenv("DATABASE_URL", "")
    READ_DATABASE_URL = os.getenv("READ_DATABASE_URL", "")
    
    # Redis Configuration
    REDIS_URL = os.getenv("REDIS_URL", "")
    
    # JWT & Auth
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "changeme")
    
    # Microservice URLs (For inter-service communication)
    ROUTE_SERVICE_URL = os.getenv("ROUTE_SERVICE_URL", "http://route-service:8001")
    SEARCH_SERVICE_URL = os.getenv("SEARCH_SERVICE_URL", "http://search-service:8002")
    ML_SERVICE_URL = os.getenv("ML_SERVICE_URL", "http://ml-service:8003")
    AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth-service:8006")
    GATEWAY_URL = os.getenv("GATEWAY_URL", "http://gateway:8000")

    # Shared settings
    CORS_ALLOWED_ORIGINS = os.getenv("CORS_ALLOWED_ORIGINS", "*").split(",")
