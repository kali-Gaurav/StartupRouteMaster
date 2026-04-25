"""
Agent Swarm Registry
=====================
Registers all business agents with the orchestrator.
Called during application lifespan boot.
"""
from services.agents import pricing_dynamic_agent
import logging
import asyncio
from services.agents.orchestrator import swarm

logger = logging.getLogger("agent.registry")


def register_all_agents():
    """Register every business agent with the swarm orchestrator."""
    
    # --- Finance Agents ---
    from services.agents.finance_agents import (
        RevenueAgent, FraudDetectionAgent, ReconciliationAgent, SettlementAgent
    )
    swarm.register(RevenueAgent())
    swarm.register(FraudDetectionAgent())
    swarm.register(ReconciliationAgent())
    swarm.register(SettlementAgent())

    # --- Safety & Guardian Agents ---
    from services.agents.guardian_agent import GuardianAgent
    swarm.register(GuardianAgent())

    # --- Operations Agents ---
    from services.agents.operations_agents import (
        BookingOpsAgent, InventoryAgent, SOSResponseAgent, QualityAssuranceAgent, MultiModalAgent
    )
    swarm.register(BookingOpsAgent())
    swarm.register(InventoryAgent())
    swarm.register(SOSResponseAgent())
    swarm.register(QualityAssuranceAgent())
    swarm.register(MultiModalAgent())

    # --- Growth Agents ---
    from services.agents.growth_agents import (
        UserGrowthAgent, EngagementAgent, CampaignAgent, ReferralAgent
    )
    swarm.register(UserGrowthAgent())
    swarm.register(EngagementAgent())
    swarm.register(CampaignAgent())
    swarm.register(ReferralAgent())

    # --- Infrastructure Agents ---
    from services.agents.infrastructure_agents import (
        SystemHealthAgent, DatabaseAgent, CacheAgent, DeploymentAgent, SecurityAgent
    )
    from services.agents.security_agent import SecurityGuardianAgent
    from services.agents.compliance_agents import ComplianceAgent, TaxEngineAgent
    from services.emergency.db_sentinel import db_sentinel_agent
    from core.nexus.financial.parity import financial_parity_agent
    from services.agents.growth_agent import growth_agent_swarm
    from services.agents.inventory_gc_agent import inventory_gc_agent
    from services.agents.bailiff_agent import bailiff_agent
    from services.agents.narrator_agent import narrator_agent
    from services.agents.gateway_agent import gateway_switcher_agent
    from services.agents.arbitrage_agent import arbitrage_agent
    from services.agents.pnr_importer_agent import pnr_importer_agent
    from services.agents.settlement_agent import rapid_settlement_agent
    from services.agents.recovery_agent import recovery_agent
    from services.agents.reconciliation_agent import reconciliation_agent
    from services.agents.replica_lag_agent import replica_lag_agent
    from services.agents.load_shedder_agent import load_shedder_agent
    from services.agents.social_ingestor_agent import social_ingestor_agent
    from services.agents.last_mile_agent import last_mile_agent
    from services.agents.fx_agent import fx_agent
    # nexus_explorer is now handled by MultiModalAgent in operations_agents
    
    swarm.register(SystemHealthAgent())
    swarm.register(DatabaseAgent())
    swarm.register(CacheAgent())
    swarm.register(DeploymentAgent())
    swarm.register(SecurityAgent())
    swarm.register(SecurityGuardianAgent())
    swarm.register(db_sentinel_agent)
    swarm.register(financial_parity_agent)
    swarm.register(growth_agent_swarm)
    swarm.register(inventory_gc_agent)
    swarm.register(pnr_importer_agent)
    swarm.register(rapid_settlement_agent)
    swarm.register(recovery_agent)
    swarm.register(reconciliation_agent)
    swarm.register(replica_lag_agent)
    swarm.register(load_shedder_agent)
    swarm.register(social_ingestor_agent)
    swarm.register(last_mile_agent)
    swarm.register(fx_agent)

    # --- Support Agents ---
    from services.agents.support_agents import (
        SupportTriageAgent, NotificationAgent, FeedbackAnalyzerAgent
    )
    swarm.register(SupportTriageAgent())
    swarm.register(NotificationAgent())
    swarm.register(FeedbackAnalyzerAgent())

    # --- Analytics Agents ---
    from services.agents.analytics_agents import (
        PredictiveAnalyticsAgent, ReportGeneratorAgent, CompetitorIntelAgent,
        SeatOptimizationAgent
    )
    swarm.register(PredictiveAnalyticsAgent())
    swarm.register(ReportGeneratorAgent())
    swarm.register(CompetitorIntelAgent())
    swarm.register(SeatOptimizationAgent())

    # --- Iron-6 Engineering Agents ---
    from services.agents.engineering_agents import (
        VanguardAgent, AriadneAgent, GuandaoAgent, ChronosAgent, ForgeAgent, AegisAgent
    )
    swarm.register(VanguardAgent())
    swarm.register(AriadneAgent())
    swarm.register(GuandaoAgent())
    swarm.register(ChronosAgent())
    swarm.register(ForgeAgent())
    swarm.register(AegisAgent())

    swarm.register(ComplianceAgent())
    swarm.register(TaxEngineAgent())

    # --- [Generation 9] Monetization & Conversion ---
    from services.agents.fomo_agent import fomo_agent
    from services.agents.upsell_agent import upsell_agent
    from services.agents.demand_forecasting_agent import get_demand_forecasting_agent
    from services.agents.cancellation_prediction_agent import cancellation_prediction_agent
    from services.agents.overbooking_agent import overbooking_agent

    swarm.register(fomo_agent)
    swarm.register(pricing_dynamic_agent)
    swarm.register(upsell_agent)
    
    # Registration of Phase 5 Agents
    from database.session import SessionLocal
    with SessionLocal() as db:
        swarm.register(get_demand_forecasting_agent(db))
    swarm.register(cancellation_prediction_agent)
    swarm.register(overbooking_agent)
    swarm.register(arbitrage_agent)

    # --- Phase 7: Real-time Hydration ---
    from services.agents.live_hydration_agent import LiveHydrationAgent
    from services.knowledge_graph_service import get_knowledge_graph
    swarm.register(LiveHydrationAgent(kg=get_knowledge_graph()))

    # --- [Generation 10] Titan Hardening ---
    from services.agents.chaos_agent import chaos_agent
    from services.agents.shadow_deploy_agent import shadow_deploy_agent
    from services.agents.chargeback_shield_agent import chargeback_shield_agent
    from services.agents.admin_intel_agent import admin_intel_agent
    swarm.register(chaos_agent)
    swarm.register(shadow_deploy_agent)
    swarm.register(chargeback_shield_agent)
    swarm.register(admin_intel_agent)

    total = len(swarm.get_all_agents())
    logger.info(f"[Registry] OK: {total} agents registered across {len(swarm.get_categories())} categories")
    return total
