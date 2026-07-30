from services.agents.gateway_agent import gateway_switcher_agent
import logging
import asyncio
import gc
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI

from database.infrastructure.session import initialize_database_pools, _dispose_all_pools
from services.deprecated.vault_service import pnr_vault
from services.cache.multi_layer import multi_layer_cache
from services.scraper.sentinel import scraper_sentinel
from services.data.storage_sync import r2_sync_manager
from core.infrastructure.container import container
from utils.http_client import HttpClientManager
from core.nexus.bootstrapper import nexus_boot
from core.nexus.node import NexusNode
from services.finance.ingestion_worker import ingestion_worker
from services.cache.warmer_service import schedule_cache_warming
from guardian_ai.monitoring_loop import guardian_loop
from core.sovereign.network_pressure import network_pressure
from services.cache.sovereign_warmer import sovereign_cache_warmer

logger = logging.getLogger("nexus.lifespan")

# [Task 1.2] Custom Node Wrapper for existing providers
from typing import Optional, List

class GlobalServiceNode(NexusNode):
    def __init__(self, name: str, start_fn, stop_fn, critical=True, dependencies: Optional[List[str]] = None):
        super().__init__(name, critical=critical, dependencies=dependencies or [])
        self.start_fn = start_fn
        self.stop_fn = stop_fn
        
    async def on_start(self):
        await self.start_fn()
        
    async def on_stop(self):
        await self.stop_fn()

async def _nexus_background_boot(app: FastAPI):
    """
    [Instant Startup] Executes heavy initialization in the background 
    to allow the gateway to start accepting health checks instantly.
    """
    try:
        # 1. 📂 [LAZY NODE REGISTRATION]
        # Moving heavy imports and registrations here for instant startup
        from core.nexus.security.node import security_node
        from core.nexus.cache.node import cache_node
        from core.nexus.database.node import database_node
        from core.nexus.financial.node import financial_node
        from core.nexus.scraper.node import scraper_node
        from core.nexus.rl.node import rl_node
        from core.nexus.search.node import search_node
        from core.nexus.transit.reconciler import transit_node

        nexus_boot.register(security_node)
        nexus_boot.register(cache_node)
        nexus_boot.register(database_node)
        nexus_boot.register(financial_node)
        nexus_boot.register(scraper_node)
        nexus_boot.register(rl_node)
        nexus_boot.register(search_node)
        nexus_boot.register(transit_node)

        # [Task 126 Alignment] Production R2 Sync Pull: 
        from database.infrastructure.config import Config
        if Config.ENVIRONMENT == "production":
            skip_sync = os.getenv("SKIP_BOOT_SYNC", "false").lower() == "true"
            if not skip_sync:
                logger.info("[NEXUS:BACKGROUND] Pulling persistent data from Cloudflare R2...")
                try:
                    await r2_sync_manager.full_sync_down()
                    logger.info("✅ [NEXUS] R2 Synchronization Complete.")
                except Exception as e:
                    logger.warning(f" [NEXUS] R2 Sync-Down failed: {e}")

        # 2. 🚀 [NEXUS DETERMINISTIC BOOT]
        success = await nexus_boot.bootstrap()
        
        if not success:
            logger.critical(" [NEXUS] MASTER BOOT FAILED. Running in DEGRADED mode.")
        else:
            logger.info(f"✅ [NEXUS] Operational Readiness: {nexus_boot.state.value}")
            
            # [NEW] Initialize Route Engine
            try:
                from core.engines.route_engine import init_route_engine
                await init_route_engine()
                logger.info("🚀 [ROUTE_ENGINE] Initialized in background.")
            except Exception as e:
                logger.warning(f"⚠️ [ROUTE_ENGINE] Background init error: {e}")
            
            # [Task 151] Start Smart Search Pre-Warmer
            from services.search.prewarmer import search_prewarmer
            asyncio.create_task(search_prewarmer.start_background_loop())

            # [Agent Swarm] Boot all business agents
            try:
                from services.agents.registry import register_all_agents
                from services.agents.orchestrator import swarm
                register_all_agents()
                await swarm.boot_all()
                logger.info(f"🤖 [AGENT SWARM] {len(swarm.get_all_agents())} agents online.")
            except Exception as e:
                logger.warning(f"⚠️ [AGENT SWARM] Boot warning: {e}")

            # [Phase 3/4] Start FinOps Ingestion & Cache Warming
            asyncio.create_task(ingestion_worker.start())
            asyncio.create_task(schedule_cache_warming())
            
            # [G4.4.1] Absolute Priority 1: Self-Heal & Restoration
            from services.agents.recovery_agent import recovery_agent
            asyncio.create_task(recovery_agent.run_cold_start_sequence())

            # [Agent Pulses] 
            from core.nexus.financial.parity import financial_parity_agent
            from services.emergency.db_sentinel import db_sentinel_agent
            from services.agents.inventory_gc_agent import inventory_gc_agent
            from services.agents.bailiff_agent import bailiff_agent
            from services.agents.settlement_agent import rapid_settlement_agent
            from services.agents.reconciliation_agent import reconciliation_agent
            from services.agents.replica_lag_agent import replica_lag_agent
            from services.agents.load_shedder_agent import load_shedder_agent
            from services.agents.social_ingestor_agent import social_ingestor_agent
            from services.agents.last_mile_agent import last_mile_agent
            from services.agents.fx_agent import fx_agent
            from services.agents.compliance_agents import TaxEngineAgent

            asyncio.create_task(db_sentinel_agent.run_pulse())
            asyncio.create_task(financial_parity_agent.pulse())
            asyncio.create_task(inventory_gc_agent.pulse())
            asyncio.create_task(bailiff_agent.pulse())
            asyncio.create_task(gateway_switcher_agent.pulse())
            asyncio.create_task(rapid_settlement_agent.pulse())
            asyncio.create_task(reconciliation_agent.pulse())
            asyncio.create_task(replica_lag_agent.pulse())
            asyncio.create_task(load_shedder_agent.pulse())
            asyncio.create_task(social_ingestor_agent.pulse())
            asyncio.create_task(last_mile_agent.pulse())
            asyncio.create_task(fx_agent.pulse())
            
            tax_engine = TaxEngineAgent()
            asyncio.create_task(tax_engine.execute())

            # [SOVEREIGN] Start Network Pressure Heartbeat & Cache Warmer
            try:
                await network_pressure.refresh()
                app.state.npc_task = asyncio.create_task(npc_heartbeat_loop())
                await sovereign_cache_warmer.start()
                logger.info("⚡ [SOVEREIGN] Heartbeat and Cache Warmer online.")
            except Exception as e:
                logger.error(f"⚠️ [SOVEREIGN] Background init error: {e}")

            # [TELEGRAM] Boot Bot
            try:
                from telegram_bot.config import bot_config
                from telegram_bot.polling import polling_manager
                if bot_config.enabled and bot_config.mode == "POLLING":
                    asyncio.create_task(polling_manager.start())
                    logger.info("🤖 [TELEGRAM] Bot started in POLLING mode.")
            except Exception as e:
                logger.error(f"⚠️ [TELEGRAM] Failed to boot bot: {e}")

            # [Phase 3/4] Start Knowledge Hydrator
            from core.knowledge.hydrator import knowledge_hydrator
            asyncio.create_task(knowledge_hydrator.start())
            logger.info("🧠 [NEXUS] Knowledge Hydrator started in background.")

    except Exception as e:
        logger.error(f"🔥 [NEXUS] Fatal Background Boot Error: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    [Task 1.4-6] Nexus V3 Deterministic Lifespan.
    Manages the 'Nexus Fiber' deterministic boot sequence and atomic halt protocol.
    """
    # 1. Aggressive GC Tuning for VPS [Task 41]
    gc.set_threshold(400, 5, 5)

    # Increase default thread pool to prevent engine zombie-threads from starving searches.
    # Default pool = min(32, cpu+4) ≈ 12 threads; engines use asyncio.to_thread and can't be
    # cancelled, so they hold pool slots. 64 threads prevents queue starvation.
    from concurrent.futures import ThreadPoolExecutor
    loop = asyncio.get_event_loop()
    loop.set_default_executor(ThreadPoolExecutor(max_workers=64, thread_name_prefix="nexus_worker"))
    
    # 🚀 [NEXUS INSTANT STARTUP]
    logger.info("🚀 [NEXUS] Initiating Instant Startup (Waiting for First Request)...")
    
    yield
    
    # 3. --- ATOMIC SHUTDOWN PROTOCOL (Task 1.6) ---
    logger.warning("🔌 [NEXUS] SIGTERM/System Stop detected. Initiating Halt Sequence...")
    
    try:
        # [Phase 3/4] Stop Knowledge Hydrator
        from core.knowledge.hydrator import knowledge_hydrator
        await knowledge_hydrator.stop()
        logger.info("🧠 [NEXUS] Knowledge Hydrator shut down.")

        # [Agent Swarm] Graceful agent shutdown
        try:
            from services.agents.orchestrator import swarm
            await swarm.shutdown_all()
            logger.info("🤖 [AGENT SWARM] All agents shut down.")
        except Exception as e:
            logger.warning(f"⚠️ [AGENT SWARM] Shutdown warning: {e}")

        # [Route Engine] Graceful shutdown
        try:
            from core.engines.route_engine import shutdown_route_engine
            await shutdown_route_engine()
            logger.info("🚀 [ROUTE_ENGINE] Shut down complete.")
        except Exception as e:
            logger.warning(f"⚠️ [ROUTE_ENGINE] Shutdown warning: {e}")

        # [SOVEREIGN] Stop NPC Heartbeat
        if hasattr(app.state, "npc_task"):
            app.state.npc_task.cancel()
            logger.info("⚡ [SOVEREIGN] NPC Heartbeat shut down.")

        # [SOVEREIGN] Stop Cache Warmer
        await sovereign_cache_warmer.stop()

        try:
            from workers.orchestrator import stop_reconciliation_worker
            stop_reconciliation_worker()
            logger.info("🛠️ Reconciliation worker stopped.")
        except Exception as e:
            logger.warning(f"Failed to stop reconciliation worker: {e}")

        # [Guardian AI] Stop monitoring loop
        await guardian_loop.stop()
        
        # [Task 1.6] Reverse-Order Halt: Search -> Scraper -> DB -> Cache
        await nexus_boot.halt()
        
        # Cleanup remaining global systems
        await r2_sync_manager.full_sync_up()
        await container.shutdown_all()
        await HttpClientManager.close_session()
        
    except Exception as e:
        logger.error(f"⚠️ [NEXUS] Shutdown Halt Error: {e}")
        
    gc.collect()
    # Final Log Flush
    for handler in logging.getLogger().handlers:
        handler.flush()
    logger.info("🛑 [NEXUS] System-Wide Shutdown complete. Fiber Dismantled.")

async def npc_heartbeat_loop():
    """Periodic refresh of the Network Pressure Calculator (Sovereign Layer)."""
    while True:
        try:
            await asyncio.sleep(300) # Every 5 minutes
            await network_pressure.refresh()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"[NPC:HEARTBEAT] Refresh failed: {e}")
            await asyncio.sleep(30)
