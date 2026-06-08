import logging
from supabase import create_client, Client
from database.config import Config

logger = logging.getLogger(__name__)

# Lazy initialization to avoid startup failures
_supabase_client: Client = None

def get_supabase_client() -> Client:
    """
    Initialize and return a Supabase client.
    Prioritizes SERVICE_KEY for administrative backend actions.
    """
    global _supabase_client
    
    if _supabase_client is not None:
        return _supabase_client
    
    url = Config.SUPABASE_URL
    key = Config.SUPABASE_SERVICE_KEY or Config.SUPABASE_KEY

    if not url or not key:
        logger.warning("Supabase URL or Key missing in configuration. Client will be unavailable.")
        return None

    try:
        _supabase_client = create_client(url, key)
        return _supabase_client
    except Exception as e:
        logger.critical(f"Failed to initialize Supabase client: {e}")
        return None

# Lazy singleton instance - only created when first accessed
class _SupabaseLazyLoader:
    def __getattr__(self, name):
        client = get_supabase_client()
        if client is None:
            raise ValueError("Supabase client is not configured. Set SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables.")
        return getattr(client, name)

supabase = _SupabaseLazyLoader()
