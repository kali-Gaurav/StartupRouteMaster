from services.agents.gateway_agent import gateway_switcher_agent
import logging
import asyncio
import gc
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI

from database.session import initialize_database_pools, _dispose_all_pools
from services.vault_service import pnr_vault
from services.multi_layer_cache import multi_layer_cache
from services.scraper_sentinel import scraper_sentinel
from services.storage_sync import r2_sync_manager
from core.container import container
from utils.http_client import HttpClientManager
from core.nexus.bootstrapper import nexus_boot
from core.nexus.node import NexusNode
from services.finance.ingestion_worker import ingestion_worker
from services.cache_warming_service import schedule_cache_warming
from guardian_ai.monitoring_loop import guardian_loop

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
    
    # [Task 1.3 & 1.10] Layer 1: Security Perimeter (P0)
    from core.nexus.security.node import security_node
    nexus_boot.register(security_node)

    # [Task 5.1 & 10.1] Layer 2: Performance & Data Fabric
    from core.nexus.cache.node import cache_node
    from core.nexus.database.node import database_node
    nexus_boot.register(cache_node)
    nexus_boot.register(database_node)
    
    # [Task 4.2 & 6.2] Layer 3: Integrity & Discovery
    from core.nexus.financial.node import financial_node
    from core.nexus.scraper.node import scraper_node
    nexus_boot.register(financial_node)
    nexus_boot.register(scraper_node)
    
    # [Task 7.10] Layer 4: Intelligence & Optimizer
    from core.nexus.rl.node import rl_node
    nexus_boot.register(rl_node)
    
    # [Task 8.10 & 9.10] Layer 5: Search & Real-time Graph
    from core.nexus.search.node import search_node
    from core.nexus.transit.reconciler import transit_node
    nexus_boot.register(search_node)
    nexus_boot.register(transit_node)

    # 2. 🚀 [NEXUS DETERMINISTIC BOOT] Task 1.4 & 10.1
    logger.info("🚀 [NEXUS] Initiating Deterministic Core Bootstrap (V3-Fiber Protocol)...")
    
    # [Task 126 Alignment] Production R2 Sync Pull: 
    # Ephemeral VPS (Railway) starts with clean state; must pull DB from R2.
    from database.config import Config
    if Config.ENVIRONMENT == "production":
        skip_sync = os.getenv("SKIP_BOOT_SYNC", "false").lower() == "true"
        if not skip_sync:
            logger.info("[NEXUS:PRODUCTION] Pulling persistent data from Cloudflare R2...")
            try:
                # Synchronize databases before starting the core nodes
                await r2_sync_manager.full_sync_down()
                logger.info("✅ [NEXUS] R2 Synchronization Complete.")
            except Exception as e:
                logger.warning(f" [NEXUS] R2 Sync-Down failed. Booting with local/fallback state: {e}")
        else:
            logger.info("⏩ [NEXUS] SKIP_BOOT_SYNC is active. Skipping R2 Pull.")

    success = await nexus_boot.bootstrap()
    
    if not success:
        logger.critical(" [NEXUS] MASTER BOOT FAILED. Entering SAFE_MODE.")
        # Optional: Force some standby states to keep API alive during DEGRADED mode
    else:
        logger.info(f"✅ [NEXUS] Operational Readiness: {nexus_boot.state.value} (Fiber Spine Active).")
        
        # [NEW] Initialize Route Engine (Core Search Orchestration)
        try:
            from core.unified_route_engine import init_route_engine
            success = await init_route_engine()
            if success:
                logger.info("🚀 [ROUTE_ENGINE] Initialized and ready for searches.")
            else:
                logger.warning("⚠️ [ROUTE_ENGINE] Initialization degraded - continuing with limited search.")
        except Exception as e:
            logger.warning(f"⚠️ [ROUTE_ENGINE] Init error (non-critical): {e}")
        
        # [Task 151] Start Smart Search Pre-Warmer (Background)
        from services.search_prewarmer import search_prewarmer
        asyncio.create_task(search_prewarmer.start_background_loop())
        logger.info("🌤️ [NEXUS:DASHBOARD] Smart Search Pre-Warmer online (Background).")

        # [Group 3 & 4] Start FinOps Ingestion & Cache Warming
        from services.emergency.db_sentinel import db_sentinel_agent
        from core.nexus.financial.parity import financial_parity_agent
        from services.agents.growth_agent import growth_agent_swarm
        from services.agents.inventory_gc_agent import inventory_gc_agent
        from services.agents.bailiff_agent import bailiff_agent
        from services.agents.narrator_agent import narrator_agent
        from services.agents.recovery_agent import recovery_agent
        from services.agents.pnr_importer_agent import pnr_importer_agent
        from services.agents.settlement_agent import rapid_settlement_agent
        from services.agents.reconciliation_agent import reconciliation_agent
        from services.agents.replica_lag_agent import replica_lag_agent
        from services.agents.load_shedder_agent import load_shedder_agent
        from services.agents.social_ingestor_agent import social_ingestor_agent
        from services.agents.last_mile_agent import last_mile_agent
        from services.agents.fx_agent import fx_agent
        
        # [G4.4.1] Absolute Priority 1: Self-Heal & Restoration
        await recovery_agent.run_cold_start_sequence()
        
        asyncio.create_task(ingestion_worker.start())
        asyncio.create_task(schedule_cache_warming())
        asyncio.create_task(db_sentinel_agent.run_pulse())
        asyncio.create_task(financial_parity_agent.pulse())
        asyncio.create_task(growth_agent_swarm.run_automation_loop())
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
        
        # [Phase 3/4] Start Knowledge Hydrator (Real-time Delay Sync)
        from core.knowledge.hydrator import knowledge_hydrator
        asyncio.create_task(knowledge_hydrator.start())
        logger.info("🧠 [NEXUS] Knowledge Hydrator online (Real-time Hydration active).")

        # [G8.1.1] Universal Provider Initialization
        try:
            from services.providers.bus_provider import bus_provider # Auto-registers
            from services.providers.multimodal_mocks import flight_p, taxi_p # Auto-registers
            logger.info("🔌 [NEXUS] Multimodal Providers (Bus, Flight, Taxi) online.")
        except Exception as e:
            logger.error(f"⚠️ [PROVIDER_BOOT] Failed to init multimodal adapters: {e}")
            
        # [G2.4.1] Global Tax & Compliance Node
        from services.agents.compliance_agents import TaxEngineAgent
        tax_engine = TaxEngineAgent()
        asyncio.create_task(tax_engine.execute())
        # Narrator is passive but available in the swarm
        logger.info("💰 [NEXUS] FinOps, ⚡ Warming, 🛡️ DB Pulse, ⚖️ Auditor & 📈 Growth Swarm online.")
        
        # [Agent Swarm] Boot all business agents
        try:
            from services.agents.registry import register_all_agents
            from services.agents.orchestrator import swarm
            register_all_agents()
            await swarm.boot_all()
            logger.info(f"🤖 [AGENT SWARM] {len(swarm.get_all_agents())} agents online.")
        except Exception as e:
            logger.warning(f"⚠️ [AGENT SWARM] Boot warning (non-critical): {e}")
        
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
            from core.unified_route_engine import shutdown_route_engine
            await shutdown_route_engine()
            logger.info("🚀 [ROUTE_ENGINE] Shut down complete.")
        except Exception as e:
            logger.warning(f"⚠️ [ROUTE_ENGINE] Shutdown warning: {e}")

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
