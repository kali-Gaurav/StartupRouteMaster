import asyncio
import logging
from abc import ABC, abstractmethod
from typing import List, Optional
from enum import Enum

logger = logging.getLogger("nexus.node")

class NodeStatus(Enum):
    """Internal Node Status."""
    PENDING = "PENDING"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    FAILED = "FAILED"
    STOPPING = "STOPPING"
    HALTED = "HALTED"

class NexusNode(ABC):
    """
    [Task 1.2] Base Lifecycle Protocol.
    All services seeking integration with the Nexus Fiber must implement this.
    """
    def __init__(self, name: str, critical: bool = True, dependencies: List[str] = None):
        self.name = name
        self.critical = critical  # If True, failure triggers SAFE_MODE [Task 1.5]
        self.dependencies = dependencies if dependencies else []
        self.status = NodeStatus.PENDING
        self._retry_count = 0
        self._max_retries = 3     # [Task 1.5] Health Gate threshold

    @abstractmethod
    async def on_start(self):
        """Logic to initialize the service."""
        pass

    @abstractmethod
    async def on_stop(self):
        """Logic to shut down the service gracefully."""
        pass

    async def start(self) -> bool:
        """Internal wrapper with retry logic [Task 1.5]"""
        self.status = NodeStatus.STARTING
        
        for attempt in range(1, self._max_retries + 1):
            try:
                logger.info(f"[NEXUS:{self.name}] Initialization (Attempt {attempt})...")
                # Every service must implement on_start as idempotent if possible
                await self.on_start()
                self.status = NodeStatus.RUNNING
                logger.info(f"[NEXUS:{self.name}] State: RUNNING.")
                return True
                
            except Exception as e:
                self._retry_count = attempt
                logger.warning(f"[NEXUS:{self.name}] Boot Error: {e}")
                if attempt < self._max_retries:
                    await asyncio.sleep(0.5 * attempt) # Incremental Backoff
        
        self.status = NodeStatus.FAILED
        logger.critical(f"[NEXUS:{self.name}] CRITICAL BOOT FAILURE after {self._max_retries} attempts.")
        return False

    async def stop(self) -> bool:
        """Internal wrapper for graceful stop."""
        if self.status in [NodeStatus.HALTED, NodeStatus.PENDING]:
            return True
            
        self.status = NodeStatus.STOPPING
        try:
            await self.on_stop()
            self.status = NodeStatus.HALTED
            logger.info(f"[NEXUS:{self.name}] State: HALTED.")
            return True
        except Exception as e:
            logger.error(f"[NEXUS:{self.name}] Shutdown Error: {e}")
            return False
