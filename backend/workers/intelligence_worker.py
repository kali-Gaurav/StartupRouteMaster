from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import signal
from typing import List, Optional
from datetime import datetime

from config import get_bootstrap_settings
from database.session import initialize_database_pools
from utils.structured_logging import setup_logging
from core.route_engine.shadow_orchestrator import shadow_orchestrator

setup_logging()
logger = logging.getLogger("routemaster.intelligence_worker")

def install_signal_handlers(stop_event: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()

    def _shutdown() -> None:
        logger.info("intelligence_worker_shutdown_signal_received")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _shutdown)
        except NotImplementedError:
            logger.debug("intelligence_worker_signal_handler_not_supported: %s", sig)

async def run_ghost_search_supervisor(stop_event: asyncio.Event) -> None:
    """
    Supervises the Shadow Intelligence Orchestrator's Ghost Search loop.
    """
    logger.info("🧠 [INTELLIGENCE:WORKER] Ghost Search Supervisor started.")
    
    # We create a task for the loop so we can cancel it on stop
    loop_task = asyncio.create_task(shadow_orchestrator.run_ghost_search_loop())
    
    try:
        await stop_event.wait()
    finally:
        logger.info("🧠 [INTELLIGENCE:WORKER] Stopping Ghost Search Loop...")
        loop_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await loop_task
        logger.info("🧠 [INTELLIGENCE:WORKER] Ghost Search Loop stopped.")

async def run_intelligence_worker() -> None:
    await initialize_database_pools()

    stop_event = asyncio.Event()
    install_signal_handlers(stop_event)

    tasks: List[asyncio.Task] = [
        asyncio.create_task(run_ghost_search_supervisor(stop_event), name="ghost_search_supervisor"),
    ]

    try:
        await stop_event.wait()
    except asyncio.CancelledError:
        stop_event.set()
        raise
    finally:
        stop_event.set()
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        logger.info("intelligence_worker_shutdown_complete")

async def main() -> None:
    logger.info("intelligence_worker_starting")
    try:
        await run_intelligence_worker()
    except Exception as exc:
        logger.exception("intelligence_worker_fatal_error: %s", exc)
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("intelligence_worker_interrupted")
