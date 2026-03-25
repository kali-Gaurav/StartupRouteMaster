import abc
import asyncio
import logging
from typing import List, Optional
from datetime import datetime

logger = logging.getLogger("nexus.node")

class NexusNode(abc.ABC):
    """
    [Task 1.2/1.3] A service module that can be managed by the Nexus State-Graph.
    Every core tool (Scrapers, DB, Ledger) inherits from this.
    """
    
    def __init__(self, name: str, dependencies: List[str] = None):
        self._name = name
        self._dependencies = dependencies or []
        self._start_time = None
        self._healthy = False
        self._last_error = None
        self._status = "IDLE" # IDLE, READY, FAILED, STOPPING
        
    @property
    def name(self) -> str:
        return self._name
        
    @property
    def dependencies(self) -> List[str]:
        return self._dependencies
        
    @property
    def is_healthy(self) -> bool:
        return self._healthy
        
    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    @abc.abstractmethod
    async def on_start(self):
        """Initialisation logic of the service."""
        pass
        
    @abc.abstractmethod
    async def on_stop(self):
        """Teardown logic of the service."""
        pass
        
    async def start(self):
        """Main starting entry point with instrumentation."""
        logger.info(f"🆕 [BOOT] Starting Node: {self._name}...")
        try:
            self._start_time = datetime.utcnow()
            await self.on_start()
            self._healthy = True
            self._status = "READY"
            logger.info(f"✅ [READY] Node: {self._name} initialized successfully.")
        except Exception as e:
            self._healthy = False
            self._status = "FAILED"
            self._last_error = str(e)
            logger.error(f"🛑 [BOOT FAILED] Node: {self._name} | Error: {e}")
            raise
            
    async def stop(self):
        """Teardown logic with instrumentation."""
        logger.info(f"🔌 [STOP] Stopping Node: {self._name}...")
        try:
            await self.on_stop()
            self._healthy = False
            self._status = "STOPPED"
        except Exception as e:
            logger.error(f"⚠️ [STOP ERROR] Node: {self._name} | Error: {e}")
            raise
