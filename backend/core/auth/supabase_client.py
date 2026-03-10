import httpx
from supabase import create_client
from database.config import Config

# choose appropriate key (service-level if available)
key = Config.SUPABASE_SERVICE_KEY or Config.SUPABASE_KEY

supabase = create_client(
    Config.SUPABASE_URL,
    key
)
