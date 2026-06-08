from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import signal
from typing import List, Optional

import psutil

from config import get_bootstrap_settings
from database.session import initialize_database_pools
from services.sync_service import HeartbeatScheduler
from utils.structured_logging import setup_logging


setup_logging()
logger = logging.getLogger("routemaster.worker")


def configure_cpu_affinity() -> None:
    try:
        process = psutil.Process(os.getpid())
        process.cpu_affinity([0])
        logger.info("worker_cpu_affinity_configured")
    except Exception as exc:
        logger.warning("worker_cpu_affinity_skipped: %s", exc)


def install_signal_handlers(stop_event: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()

    def _shutdown() -> None:
        logger.info("worker_shutdown_signal_received")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _shutdown)
        except NotImplementedError:
            logger.debug("worker_signal_handler_not_supported: %s", sig)


async def run_agent_swarm(stop_event: asyncio.Event) -> None:
    settings = get_bootstrap_settings()
    if not settings.enable_worker_swarm:
        logger.info("worker_swarm_disabled")
        return

    try:
        from services.agents.orchestrator import AgentOrchestrator
    except Exception as exc:
        logger.warning("worker_swarm_unavailable: %s", exc)
        return

    orchestrator = AgentOrchestrator()
    logger.info("worker_swarm_started")

    while not stop_event.is_set():
        try:
            results = await orchestrator.execute_all()
            logger.info("worker_swarm_cycle_complete agents=%s", len(results))
        except Exception as exc:
            logger.exception("worker_swarm_cycle_failed: %s", exc)

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=300)
        except asyncio.TimeoutError:
            continue


async def poke_watchdog() -> None:
    try:
        from core.nexus.watchdog import nexus_watchdog

        nexus_watchdog.poke("background_worker")
    except Exception as exc:
        logger.debug("worker_watchdog_unavailable: %s", exc)


async def run_watchdog_loop(stop_event: asyncio.Event) -> None:
    settings = get_bootstrap_settings()
    if not settings.enable_worker_watchdog:
        logger.info("worker_watchdog_disabled")
        return

    logger.info("worker_watchdog_started")
    while not stop_event.is_set():
        await poke_watchdog()
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=15)
        except asyncio.TimeoutError:
            continue


async def run_scheduler(stop_event: asyncio.Event) -> None:
    scheduler = HeartbeatScheduler()
    scheduler_task = asyncio.create_task(scheduler.start(), name="heartbeat_scheduler")
    logger.info("worker_scheduler_started")

    try:
        await stop_event.wait()
    finally:
        scheduler.stop()
        scheduler_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await scheduler_task
        logger.info("worker_scheduler_stopped")


async def run_worker() -> None:
    configure_cpu_affinity()
    await initialize_database_pools()

    stop_event = asyncio.Event()
    install_signal_handlers(stop_event)

    tasks: List[asyncio.Task] = [
        asyncio.create_task(run_scheduler(stop_event), name="worker_scheduler_supervisor"),
        asyncio.create_task(run_agent_swarm(stop_event), name="worker_agent_swarm"),
        asyncio.create_task(run_watchdog_loop(stop_event), name="worker_watchdog"),
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
        logger.info("worker_shutdown_complete")


async def main() -> None:
    logger.info("worker_starting")
    try:
        await run_worker()
    except Exception as exc:
        logger.exception("worker_fatal_error: %s", exc)
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("worker_interrupted")
