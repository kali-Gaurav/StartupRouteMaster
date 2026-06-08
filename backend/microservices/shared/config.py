from database.config import Config as DatabaseConfig
import os

class Config(DatabaseConfig):
    # Microservice URLs (For inter-service communication)
    ROUTE_SERVICE_URL = os.getenv("ROUTE_SERVICE_URL", "http://route-service:8001")
    SEARCH_SERVICE_URL = os.getenv("SEARCH_SERVICE_URL", "http://search-service:8002")
    ML_SERVICE_URL = os.getenv("ML_SERVICE_URL", "http://ml-service:8003")
    AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth-service:8006")
    GATEWAY_URL = os.getenv("GATEWAY_URL", "http://gateway:8000")
    CORS_ALLOWED_ORIGINS = os.getenv("CORS_ALLOWED_ORIGINS", "*").split(",")
