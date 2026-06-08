import asyncio
import logging
import time
from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock
import sys
import os
sys.path.append(os.path.join(os.getcwd(), "backend"))

from core.route_engine.orchestrator import UnifiedRoutingOrchestrator
from core.route_engine.constraints import RouteConstraints, DiscoveryModel
from core.route_engine.base import RoutingRequest, RoutingResponse
from core.data_utils.structures import Route, RouteSegment, Persona, TransferConnection

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("chaos-routing")

async def test_tis_failure_resilience():
    """
    [CHAOS] Test if orchestrator survives TIS service total failure.
    Should continue returning routes but log warnings.
    """
    logger.info("\n🧪 [CHAOS] Testing TIS Failure Resilience...")
    
    orchestrator = UnifiedRoutingOrchestrator()
    constraints = RouteConstraints(discovery_model=DiscoveryModel.BACKBONE, persona=Persona.COMFORT)
    
    # Mock some basic routes
    mock_routes = [
        Route(
            segments=[
                RouteSegment(trip_id=1, departure_stop_id=1, arrival_stop_id=2, departure_time="10:00", arrival_time="12:00", 
                             duration_minutes=120, distance_km=100, departure_code="NDLS", arrival_code="KOTA", fare=500.0,
                             train_name="Express", train_number="12345", service_mask=1, is_unconfirmed_allowed=False,
                             has_pantry=False, departure_platform="1", arrival_platform="2", metadata={}, stop_sequence=1,
                             reliability=1.0, from_station_name="Delhi", to_station_name="Kota"),
                RouteSegment(trip_id=2, departure_stop_id=2, arrival_stop_id=3, departure_time="12:30", arrival_time="15:00", 
                             duration_minutes=150, distance_km=150, departure_code="KOTA", arrival_code="BCT", fare=700.0,
                             train_name="Super", train_number="54321", service_mask=1, is_unconfirmed_allowed=False,
                             has_pantry=True, departure_platform="3", arrival_platform="4", metadata={}, stop_sequence=2,
                             reliability=1.0, from_station_name="Kota", to_station_name="Mumbai")
            ],
            transfers=[TransferConnection(
                station_id=2, 
                station_code="KOTA", 
                arrival_time=datetime.fromisoformat("2026-05-10T12:00:00"), 
                departure_time=datetime.fromisoformat("2026-05-10T12:30:00"), 
                duration_minutes=30,
                station_name="Kota Junction",
                facilities_score=0.8,
                safety_score=0.9,
                platform_from="2",
                platform_to="3",
                is_multi_station=False,
                transfer_type="WALK"
            )],
            total_duration=300, total_cost=1200.0, total_distance=250, score=100.0, reliability=1.0, 
            availability_probability=1.0, is_locked=False, is_featured=False, highlight_label=None, metadata={}, visited_stations={1,2,3},
            journey_id="jid_1"
        )
    ]

    with patch("database.session.SessionTransit", MagicMock()):
        with patch("core.route_engine.orchestrator.tis_service.score_transfer", side_effect=Exception("TIS DB Connection Timed Out")):
            # Mock engine to return our mock_routes
            mock_engine = MagicMock()
            mock_engine.find_routes = AsyncMock(return_value=RoutingResponse(
                engine_name="turbo_router", 
                routes=mock_routes, 
                latency_ms=10.0, 
                yield_count=len(mock_routes)
            ))
            orchestrator.engines = {"turbo_router": mock_engine}
            
            request = RoutingRequest(
                source_code="NDLS", 
                destination_code="BCT", 
                departure_date=datetime(2026, 5, 10), 
                constraints=constraints,
                metadata={"vya_enabled": False} # Return flat list
            )
            
            results = await orchestrator.search_all_tiers(request)
        
        if len(results) > 0:
            logger.info(f"✅ [CHAOS] Success: Orchestrator returned {len(results)} routes despite TIS failure.")
            # Check if TIS score was skipped or default was used
            tis_score = results[0].metadata.get("tis_score")
            if tis_score is None:
                logger.info("✅ [CHAOS] Correct: No TIS metadata present as expected.")
        else:
            logger.error("❌ [CHAOS] Failure: Orchestrator returned 0 routes during TIS failure.")

async def test_persona_penalty_scaling():
    """
    [CHAOS] Test if different personas receive different penalties for high-risk transfers.
    """
    logger.info("\n🧪 [CHAOS] Testing Persona Penalty Scaling...")
    
    orchestrator = UnifiedRoutingOrchestrator()
    
    def create_route():
        return Route(
            segments=[
                RouteSegment(trip_id=1, departure_stop_id=1, arrival_stop_id=2, departure_time="10:00", arrival_time="12:00", 
                             duration_minutes=120, distance_km=100, departure_code="NDLS", arrival_code="KOTA", fare=500.0,
                             train_name="Express", train_number="12345", service_mask=1, is_unconfirmed_allowed=False,
                             has_pantry=False, departure_platform="1", arrival_platform="2", metadata={}, stop_sequence=1,
                             reliability=1.0, from_station_name="Delhi", to_station_name="Kota"),
                RouteSegment(trip_id=2, departure_stop_id=2, arrival_stop_id=3, departure_time="12:05", arrival_time="15:00", 
                             duration_minutes=150, distance_km=150, departure_code="KOTA", arrival_code="BCT", fare=700.0,
                             train_name="Super", train_number="54321", service_mask=1, is_unconfirmed_allowed=False,
                             has_pantry=True, departure_platform="3", arrival_platform="4", metadata={}, stop_sequence=2,
                             reliability=1.0, from_station_name="Kota", to_station_name="Mumbai")
            ],
            transfers=[TransferConnection(
                station_id=2, 
                station_code="KOTA", 
                arrival_time=datetime.fromisoformat("2026-05-10T12:00:00"), 
                departure_time=datetime.fromisoformat("2026-05-10T12:05:00"), 
                duration_minutes=5,
                station_name="Kota Junction",
                facilities_score=0.8,
                safety_score=0.9,
                platform_from="2",
                platform_to="3",
                is_multi_station=False,
                transfer_type="WALK"
            )],
            total_duration=300, total_cost=1200.0, total_distance=250, score=100.0, reliability=1.0, 
            availability_probability=1.0, is_locked=False, is_featured=False, highlight_label=None, metadata={}, visited_stations={1,2,3},
            journey_id="test_jid"
        )

    # We need to mock the TIS service to return HIGH_RISK
    from core.route_engine.tis_service import TISResult, TransferRiskLevel
    mock_tis_res = TISResult(
        tis_score=0.2, 
        risk_level=TransferRiskLevel.HIGH_RISK, 
        buffer_minutes=5,
        ontime_probability=0.3, 
        congestion_factor=0.5,
        connection_success_rate=0.8,
        reasoning="Tight transfer"
    )
    
    # Test FAMILY Persona (Weight 5.0)
    constraints_family = RouteConstraints(persona=Persona.FAMILY)
    with patch("database.session.SessionTransit", MagicMock()):
        with patch("core.route_engine.orchestrator.tis_service.score_transfer", AsyncMock(return_value=mock_tis_res)):
            with patch("core.route_engine.orchestrator.tis_service.score_route_transfers", AsyncMock(return_value=(0.2, TransferRiskLevel.HIGH_RISK))):
                mock_engine = MagicMock()
                mock_engine.find_routes = AsyncMock(return_value=RoutingResponse(
                    engine_name="turbo_router", 
                    routes=[create_route()],
                    latency_ms=10.0,
                    yield_count=1
                ))
                orchestrator.engines = {"turbo_router": mock_engine}
                
                request = RoutingRequest(
                    source_code="NDLS", 
                    destination_code="BCT", 
                    departure_date=datetime(2026, 5, 10), 
                    constraints=constraints_family, 
                    metadata={"vya_enabled": False}
                )
                results_family = await orchestrator.search_all_tiers(request)
                score_family = results_family[0].score
                logger.info(f"Family Score (Weighted): {score_family}")

    # Test BUDGET Persona (Weight 1.0)
    constraints_budget = RouteConstraints(persona=Persona.BUDGET)
    with patch("database.session.SessionTransit", MagicMock()):
        with patch("core.route_engine.orchestrator.tis_service.score_transfer", AsyncMock(return_value=mock_tis_res)):
            with patch("core.route_engine.orchestrator.tis_service.score_route_transfers", AsyncMock(return_value=(0.2, TransferRiskLevel.HIGH_RISK))):
                mock_engine = MagicMock()
                mock_engine.find_routes = AsyncMock(return_value=RoutingResponse(
                    engine_name="turbo_router", 
                    routes=[create_route()],
                    latency_ms=10.0,
                    yield_count=1
                ))
                orchestrator.engines = {"turbo_router": mock_engine}
                
                request = RoutingRequest(
                    source_code="NDLS", 
                    destination_code="BCT", 
                    departure_date=datetime(2026, 5, 10), 
                    constraints=constraints_budget, 
                    metadata={"vya_enabled": False}
                )
                results_budget = await orchestrator.search_all_tiers(request)
                score_budget = results_budget[0].score
                logger.info(f"Budget Score (Weighted): {score_budget}")

    if score_family < score_budget:
        logger.info("✅ [CHAOS] Success: Family persona received a heavier penalty than Budget persona.")
    else:
        logger.error(f"❌ [CHAOS] Failure: Persona weighting logic not working correctly. Family: {score_family}, Budget: {score_budget}")

async def main():
    await test_tis_failure_resilience()
    await test_persona_penalty_scaling()

if __name__ == "__main__":
    asyncio.run(main())
