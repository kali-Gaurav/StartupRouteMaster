import httpx
from supabase import create_client
from database.config import Config

# Ultimate monkeypatch for httpx.Client to ignore the 'proxy' argument
# which is incorrectly passed by some versions of the supabase/gotrue library.
_original_httpx_init = httpx.Client.__init__

def _patched_httpx_init(self, *args, **kwargs):
    if 'proxy' in kwargs:
        # If httpx doesn't like 'proxy', it might want 'proxies' or nothing.
        # However, the error says 'proxy' is unexpected.
        kwargs.pop('proxy')
    return _original_httpx_init(self, *args, **kwargs)

httpx.Client.__init__ = _patched_httpx_init

# choose appropriate key (service-level if available)
key = Config.SUPABASE_SERVICE_KEY or Config.SUPABASE_KEY

supabase = create_client(
    Config.SUPABASE_URL,
    key
)
