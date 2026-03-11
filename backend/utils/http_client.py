import aiohttp
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class HttpClientManager:
    _session: Optional[aiohttp.ClientSession] = None

    @classmethod
    async def get_session(cls) -> aiohttp.ClientSession:
        if cls._session is None or cls._session.closed:
            logger.info("Creating global aiohttp ClientSession")
            timeout = aiohttp.ClientTimeout(total=15)
            headers = {
                "User-Agent": "RouteMaster-Production/2.6 (RailwayRouting; EthicalScraping)",
                "Accept": "application/json",
                "Connection": "keep-alive"
            }
            cls._session = aiohttp.ClientSession(timeout=timeout, headers=headers)
        return cls._session

    @classmethod
    async def close_session(cls):
        if cls._session and not cls._session.closed:
            logger.info("Closing global aiohttp ClientSession")
            await cls._session.close()
            cls._session = None

# For backward compatibility or easy access
async def get_global_session() -> aiohttp.ClientSession:
    return await HttpClientManager.get_session()
