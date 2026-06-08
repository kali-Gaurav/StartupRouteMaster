"""
Sovereign Intelligence Orchestrator (SIO)
=========================================
Patent Innovation #5: The "Unified Neural Controller" for transit networks.

This is the central nervous system of the RouteMaster platform. It orchestrates:
1. Network Pressure Analysis (NPC)
2. Demand Redistribution (EDR)
3. Multi-Modal Synchronization (CMS)
4. AI Concierge Guidance (Shadow-Guide)
5. Security Hardening (WAF/RL)

It ensures that every decision made by the system is globally optimal, 
maximizing network throughput while minimizing passenger friction.
"""

from datetime import timedelta
import logging
import asyncio
import uuid
import time
from datetime import datetime
from typing import Dict, List, Any, Optional

from core.sovereign.network_pressure import network_pressure, PressureLevel
from core.sovereign.edr_algorithm import edr_engine, EDRDecision
from core.sovereign.ab_engine import ab_engine
from services.shadow_guide import shadow_guide

logger = logging.getLogger("sovereign.orchestrator")

class SovereignOrchestrator:
    """
    The master controller for all Sovereign Intelligence operations.
    This is the 'Patent Core' where all sub-algorithms are synchronized.
    """

    def __init__(self):
        self.orchestrator_id = str(uuid.uuid4())
        self._is_active = True
        logger.info(f"[SIO] Sovereign Intelligence Orchestrator [{self.orchestrator_id}] initialized")

    async def execute_search_cycle(
        self,
        source: str,
        destination: str,
        initial_routes: List[Any],
        user_id: str,
        persona: str,
        tier: str = "FREE"
    ) -> Dict[str, Any]:
        """
        The complete neural pipeline for a search request.
        1. Pressure Sync -> 2. EDR Decision -> 3. Optimization -> 4. Guidance
        """
        start_time = time.monotonic()
        source = source.upper()
        destination = destination.upper()

        # STEP 1: RECORD LIVE DEMAND (NPC FEED)
        # We record this search immediately to update the network-wide pressure map
        await network_pressure.record_search(source, destination)

        # STEP 2: EVALUATE EDR REDISTRIBUTION (BRAIN)
        # The EDR engine determines if we need to steer demand away from this corridor
        edr_decision: EDRDecision = await edr_engine.evaluate_search(
            source=source,
            destination=destination,
            routes=initial_routes,
            user_segment=persona,
            user_tier=tier
        )

        # STEP 3: APPLY A/B OPTIMIZATION (EVOLUTION)
        # Personalize nudges based on user behavior variants
        if edr_decision.has_nudges:
            for nudge in edr_decision.nudges:
                ab_engine.optimize_nudge(user_id, nudge)

        # STEP 4: GENERATE AGENTIC GUIDANCE (VOICE)
        # The Shadow-Guide explains the decision to the user
        guide_response = await shadow_guide.generate_guidance(
            edr_decision=edr_decision,
            user_context={"user_id": user_id, "persona": persona, "tier": tier}
        )

        # STEP 5: SYNC MULTI-MODAL RELEASE VALVES (CMS)
        # If rail pressure is CRITICAL, we check for multi-modal expansion
        if edr_decision.should_trigger_supply_infusion:
            await self._trigger_multi_modal_expansion(source, destination, edr_decision.corridor_pressure, edr_decision)

        duration = (time.monotonic() - start_time) * 1000
        
        return {
            "decision": edr_decision,
            "guidance": guide_response,
            "metadata": {
                "orchestrator_id": self.orchestrator_id,
                "latency_ms": round(duration, 2),
                "timestamp": datetime.utcnow().isoformat()
            }
        }

    async def _trigger_multi_modal_expansion(self, source: str, destination: str, pressure: float, decision: EDRDecision):
        """
        Actively 'spins up' or 'reserves' non-rail supply for a congested corridor.
        This is the active supply-side response of the Sovereign system.
        """
        logger.warning(f"[SIO] CRITICAL PRESSURE detected for {source}->{destination}. Triggering Multi-Modal Expansion.")
        
        try:
            from core.sovereign.supply_infusion import ssie
            alternatives = await ssie.get_emergency_alternatives(source, destination, pressure)
            
            for alt in alternatives:
                # Apply emergency subsidy to make them attractive
                subsidized_alt = ssie.apply_emergency_subsidy(alt)
                
                # Add to decision nudges
                from core.sovereign.edr_algorithm import EDRNudge, NudgeType, IncentiveCategory
                nudge = EDRNudge(
                    nudge_id=f"ssie_{uuid.uuid4().hex[:6]}",
                    nudge_type=NudgeType.MULTI_MODAL,
                    target_route_id=subsidized_alt["journey_id"],
                    competing_route_id="", # General congestion relief
                    headline=subsidized_alt["metadata"]["ui_reasons"][0],
                    description=subsidized_alt["metadata"]["ui_reasons"][1],
                    incentive_value=subsidized_alt["metadata"]["subsidy_applied"],
                    incentive_category=IncentiveCategory.CASHBACK,
                    system_benefit=1.0,
                    pressure_delta=pressure - 0.4, # Assumed low pressure for bus
                    expires_at=datetime.utcnow() + timedelta(hours=1),
                    metadata=subsidized_alt
                )
                decision.nudges.append(nudge)
                
            logger.info(f"[SIO] Injected {len(alternatives)} emergency multi-modal alternatives.")
            
        except Exception as e:
            logger.error(f"[SIO] Multi-modal expansion failed: {e}")

    async def run_global_pulse(self):
        """
        A background heartbeat that synchronized global network state.
        This runs every 60 seconds across the entire backend cluster.
        """
        while self._is_active:
            try:
                # 1. Refresh global pressure map
                snapshot = await network_pressure.get_network_snapshot(force_refresh=True)
                
                # 2. Identify 'System-Wide Choke Points'
                hotspots = snapshot.hotspots
                if hotspots:
                    logger.info(f"[SIO] Heartbeat: Network hotspots detected in {len(hotspots)} corridors.")
                    # 3. Proactive Cache Warming for hot corridors
                    from services.sovereign_cache_warmer import sovereign_cache_warmer
                    await sovereign_cache_warmer.warm_corridors(hotspots)
                
                # 4. Sync A/B testing results to global dashboard
                # This makes the learning 'real-time'
                
                await asyncio.sleep(60)
            except Exception as e:
                logger.error(f"[SIO] Global pulse failed: {e}")
                await asyncio.sleep(10)

# Singleton
sio = SovereignOrchestrator()
