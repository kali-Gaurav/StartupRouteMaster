#!/usr/bin/env python3
"""
Startup script for analytics consumer service

Phase 4 - Step 1: Run analytics consumer as background service
"""

import asyncio
import logging
import os
import sys
from signal import signal, SIGINT, SIGTERM

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.services.analytics_consumer import start_analytics_consumer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    """Run analytics consumer service"""
    logger.info("Starting Railway Analytics Consumer Service...")

    # Handle graceful shutdown
    shutdown_event = asyncio.Event()

    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        shutdown_event.set()

    signal(SIGINT, signal_handler)
    signal(SIGTERM, signal_handler)

    try:
        # Start consumer
        consumer_task = asyncio.create_task(start_analytics_consumer())

        # Wait for shutdown signal
        await shutdown_event.wait()

        # Cancel consumer task
        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            pass

    except Exception as e:
        logger.error(f"Service error: {e}")
        raise
    finally:
        logger.info("Analytics Consumer Service stopped")

if __name__ == "__main__":
    asyncio.run(main())