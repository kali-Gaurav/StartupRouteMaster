"""
Configuration for all external data providers.

This module loads settings from environment variables and provides
a single source of truth for configurations like API keys, base URLs,
and timeouts.
"""
import os

class ProviderConfig:
    # RapidAPI (irctc1.p.rapidapi.com)
    RAPIDAPI_KEY: str = os.getenv("RAPIDAPI_KEY", "")
    RAPIDAPI_HOST: str = os.getenv("RAPIDAPI_HOST", "irctc1.p.rapidapi.com")
    RAPIDAPI_BASE_URL: str = f"https://{RAPIDAPI_HOST}"

    # NTES Scraper (enquiry.indianrail.gov.in)
    NTES_BASE_URL: str = "https://enquiry.indianrail.gov.in/mntes/"

    # Rappid.in API
    RAPPID_IN_BASE_URL: str = "https://rappid.in/apis/"

    # Global settings
    DEFAULT_TIMEOUT: int = 15  # seconds

config = ProviderConfig()

# Module-level constants for convenience imports
DEFAULT_TIMEOUT = config.DEFAULT_TIMEOUT
