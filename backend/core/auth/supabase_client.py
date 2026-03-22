import logging
from supabase import create_client, Client
from database.config import Config

logger = logging.getLogger(__name__)

def get_supabase_client() -> Client:
    """
    Initialize and return a Supabase client.
    Prioritizes SERVICE_KEY for administrative backend actions.
    """
    url = Config.SUPABASE_URL
    key = Config.SUPABASE_SERVICE_KEY or Config.SUPABASE_KEY

    if not url or not key:
        logger.error("Supabase URL or Key missing in configuration.")
        raise ValueError("Supabase configuration is incomplete.")

    try:
        client = create_client(url, key)
        return client
    except Exception as e:
        logger.critical(f"Failed to initialize Supabase client: {e}")
        raise

# Singleton instance for general use
supabase: Client = get_supabase_client()
