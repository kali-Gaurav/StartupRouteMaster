"""
Tests for Route Engine Evolution Features

Tests for:
- SSE Progressive Route Delivery
- Query Plan Optimizer (QPO)
- Transfer Intelligence Score (TIS)
- Corridor Safety Bus
- Unified Route Service
"""

import pytest
from datetime import datetime, time, date
from unittest.mock import Mock, AsyncMock, patch
import json

# Import the modules under test
from backend.services.routing.query_plan_optimizer import (
    QueryPlanOptimizer,
    QueryPlan,
    QueryContext,
    SearchDepth,
    DatabaseTarget,
    HubPriority
)
from backend.services.routing.transfer_intelligence import (
    TransferIntelligenceService,
    TransferScore,
    JourneyTransferScore,
    RiskLevel
)
from backend.services.routing.corridor_safety_bus import (
    CorridorSafetyBus,
    CorridorSafetyStatus,
    SafetyEvent,
    SafetyEventType,
    SafetyLevel
)


class TestQueryPlanOptimizer:
    """Tests for Query Plan Optimizer"""
    
    @pytest.fixture
    def optimizer(self):
        """Create a QPO instance without route engine"""
        return QueryPlanOptimizer()
    
    @pytest.fixture
    def sample_context(self):
        """Create a sample query context"""
        return QueryContext(
            source="NDLS",
            destination="BCT",
            travel_date="2026-05-15",
            travel_time=time(10, 0),
            require_ac=False,
            is_peak_hour=False
        )
    
    @pytest.mark.asyncio
    async def test_create_query_plan(self, optimizer, sample_context):
        """Test creating a query plan"""
        plan = await optimizer.create_query_plan(sample_context)
        
        assert plan is not None
        assert plan.query_id is not None
        assert plan.search_depth in [SearchDepth.DIRECT_ONLY, SearchDepth.ONE_TRANSFER]
        assert plan.database_target in [DatabaseTarget.PRIMARY, DatabaseTarget.READ_REPLICA]
        assert plan.estimated_latency_ms > 0
        assert 0.0 <= plan.confidence <= 1.0
        assert len(plan.reasoning) > 0
    
    @pytest.mark.asyncio
    async def test_search_depth_popular_corridor(self, optimizer):
        """Test search depth for popular corridor"""
        context = QueryContext(
            source="NDLS",
            destination="BCT",
            travel_date="2026-05-15"
        )
        
        plan = await optimizer.create_query_plan(context)
        
        # Popular corridor should prefer direct routes
        assert plan.search_depth in [SearchDepth.DIRECT_ONLY, SearchDepth.ONE_TRANSFER]
    
    @pytest.mark.asyncio
    async def test_search_depth_non_hub(self, optimizer):
        """Test search depth for non-hub stations"""
        context = QueryContext(
            source="ABC",
            destination="XYZ",
            travel_date="2026-05-15"
        )
        
        plan = await optimizer.create_query_plan(context)
        
        # Non-hub stations likely need transfers
        assert plan.search_depth in [
            SearchDepth.ONE_TRANSFER,
            SearchDepth.TWO_TRANSFERS
        ]
    
    def test_estimate_latency_direct(self, optimizer):
        """Test latency estimation for direct routes"""
        context = QueryContext(
            source="NDLS",
            destination="BCT",
            travel_date="2026-05-15"
        )
        
        plan = optimizer._estimate_latency(
            SearchDepth.DIRECT_ONLY,
            DatabaseTarget.PRIMARY,
            context
        )
        
        # Direct routes should be faster
        assert plan < 500
    
    def test_estimate_latency_peak_hour(self, optimizer):
        """Test latency estimation during peak hours"""
        context = QueryContext(
            source="NDLS",
            destination="BCT",
            travel_date="2026-05-15",
            is_peak_hour=True
        )
        
        peak_latency = optimizer._estimate_latency(
            SearchDepth.DIRECT_ONLY,
            DatabaseTarget.PRIMARY,
            context
        )
        
        non_peak_context = QueryContext(
            source="NDLS",
            destination="BCT",
            travel_date="2026-05-15",
            is_peak_hour=False
        )
        
        non_peak_latency = optimizer._estimate_latency(
            SearchDepth.DIRECT_ONLY,
            DatabaseTarget.PRIMARY,
            non_peak_context
        )
        
        # Peak hours should have higher latency
        assert peak_latency > non_peak_latency
    
    def test_calculate_confidence(self, optimizer):
        """Test confidence calculation"""
        context = QueryContext(
            source="NDLS",
            destination="BCT",
            travel_date="2026-05-15"
        )
        
        hub_priorities = [
            HubPriority(
                station_code="NDLS",
                station_name="New Delhi",
                priority=0.9,
                historical_traffic=50000,
                transfer_success_rate=0.85
            )
        ]
        
        confidence = optimizer._calculate_confidence(context, hub_priorities)
        
        assert 0.0 <= confidence <= 1.0
        assert confidence > 0.5  # Should have decent confidence for popular corridor


class TestTransferIntelligenceService:
    """Tests for Transfer Intelligence Score"""
    
    @pytest.fixture
    def tis_service(self):
        """Create a TIS service instance"""
        return TransferIntelligenceService()
    
    @pytest.mark.asyncio
    async def test_calculate_transfer_score(self, tis_service):
        """Test calculating transfer score"""
        score = await tis_service.calculate_transfer_score(
            transfer_station="NDLS",
            arrival_train="12001",
            departure_train="12002",
            connection_time_minutes=30
        )
        
        assert score is not None
        assert score.transfer_station == "NDLS"
        assert score.arrival_train == "12001"
        assert score.departure_train == "12002"
        assert score.connection_time_minutes == 30
        assert 0.0 <= score.tis_score <= 100.0
        assert score.risk_level in [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH]
    
    @pytest.mark.asyncio
    async def test_good_connection_high_score(self, tis_service):
        """Test that good connections get high scores"""
        score = await tis_service.calculate_transfer_score(
            transfer_station="NDLS",
            arrival_train="12001",
            departure_train="12002",
            connection_time_minutes=45  # Good buffer time
        )
        
        assert score.tis_score >= 60  # Should be decent
        assert score.risk_level in [RiskLevel.LOW, RiskLevel.MEDIUM]
    
    @pytest.mark.asyncio
    async def test_poor_connection_low_score(self, tis_service):
        """Test that poor connections get low scores"""
        score = await tis_service.calculate_transfer_score(
            transfer_station="NDLS",
            arrival_train="12001",
            departure_train="12002",
            connection_time_minutes=10  # Very short buffer
        )
        
        assert score.tis_score < 70  # Should be lower
        assert score.risk_level in [RiskLevel.MEDIUM, RiskLevel.HIGH]
    
    def test_get_transfer_indicator_low_risk(self, tis_service):
        """Test visual indicator for low risk"""
        transfer_score = TransferScore(
            transfer_station="NDLS",
            arrival_train="12001",
            departure_train="12002",
            connection_time_minutes=30,
            tis_score=85.0,
            risk_level=RiskLevel.LOW,
            historical_success_rate=0.85
        )
        
        indicator = tis_service.get_transfer_indicator(transfer_score)
        
        assert indicator["color"] == "green"
        assert indicator["icon"] == "✅"
        assert indicator["label"] == "Good Connection"
    
    def test_get_transfer_indicator_high_risk(self, tis_service):
        """Test visual indicator for high risk"""
        transfer_score = TransferScore(
            transfer_station="NDLS",
            arrival_train="12001",
            departure_train="12002",
            connection_time_minutes=10,
            tis_score=40.0,
            risk_level=RiskLevel.HIGH,
            historical_success_rate=0.45
        )
        
        indicator = tis_service.get_transfer_indicator(transfer_score)
        
        assert indicator["color"] == "red"
        assert indicator["icon"] == "❌"
        assert indicator["label"] == "High Risk"
    
    @pytest.mark.asyncio
    async def test_score_journey_no_transfers(self, tis_service):
        """Test scoring a journey with no transfers"""
        # Create a mock journey with no transfers
        journey = Mock()
        journey.segments = []
        
        score = await tis_service.score_journey(journey)
        
        assert score.overall_score == 100.0
        assert score.risk_level == RiskLevel.LOW
        assert len(score.transfer_details) == 0


class TestCorridorSafetyBus:
    """Tests for Corridor Safety Bus"""
    
    @pytest.fixture
    def safety_bus(self):
        """Create a safety bus instance"""
        return CorridorSafetyBus(route_engine=None)
    
    @pytest.mark.asyncio
    async def test_publish_safety_event(self, safety_bus):
        """Test publishing a safety event"""
        event = SafetyEvent(
            event_id="evt-001",
            event_type=SafetyEventType.CORRIDOR_ALERT,
            corridor="NDLS-BCT",
            stations=["NDLS", "BCT"],
            severity=SafetyLevel.MODERATE,
            description="Heavy crowd expected",
            start_time=datetime.utcnow(),
            end_time=None
        )
        
        await safety_bus.publish_safety_event(event)
        
        assert event.event_id in safety_bus._active_events
        
        # Check corridor status was updated
        status = await safety_bus.get_corridor_safety("NDLS", "BCT")
        assert status.active_events >= 1
        assert status.safety_score < 1.0  # Should be reduced
    
    @pytest.mark.asyncio
    async def test_resolve_safety_event(self, safety_bus):
        """Test resolving a safety event"""
        event = SafetyEvent(
            event_id="evt-002",
            event_type=SafetyEventType.STATION_ALERT,
            corridor="NDLS-BCT",
            stations=["NDLS"],
            severity=SafetyLevel.LOW,
            description="Minor incident",
            start_time=datetime.utcnow(),
            end_time=None
        )
        
        await safety_bus.publish_safety_event(event)
        resolved = await safety_bus.resolve_safety_event(event.event_id)
        
        assert resolved is True
        assert event.event_id not in safety_bus._active_events
    
    @pytest.mark.asyncio
    async def test_get_corridor_safety_unknown_corridor(self, safety_bus):
        """Test getting safety for unknown corridor"""
        status = await safety_bus.get_corridor_safety("ABC", "XYZ")
        
        # Unknown corridor should be neutral
        assert status.safety_score == 1.0
        assert status.active_events == 0
    
    def test_get_active_events(self, safety_bus):
        """Test getting active events"""
        # Initially empty
        events = safety_bus.get_active_events()
        assert len(events) == 0


class TestSafetyLevel:
    """Tests for Safety Level enum"""
    
    def test_safety_level_values(self):
        """Test SafetyLevel has all expected values"""
        assert SafetyLevel.CRITICAL == "critical"
        assert SafetyLevel.HIGH == "high"
        assert SafetyLevel.MODERATE == "moderate"
        assert SafetyLevel.LOW == "low"
        assert SafetyLevel.MINIMAL == "minimal"


class TestSafetyEventType:
    """Tests for Safety Event Type enum"""
    
    def test_event_types(self):
        """Test SafetyEventType has expected values"""
        assert SafetyEventType.STATION_ALERT == "station_alert"
        assert SafetyEventType.CORRIDOR_ALERT == "corridor_alert"
        assert SafetyEventType.ROUTE_DISRUPTION == "route_disruption"
        assert SafetyEventType.WEATHER_WARNING == "weather_warning"


class TestRiskLevel:
    """Tests for Risk Level enum"""
    
    def test_risk_level_values(self):
        """Test RiskLevel has expected values"""
        assert RiskLevel.LOW == "low"
        assert RiskLevel.MEDIUM == "medium"
        assert RiskLevel.HIGH == "high"
        assert RiskLevel.UNKNOWN == "unknown"


class TestQueryContext:
    """Tests for Query Context"""
    
    def test_query_context_creation(self):
        """Test creating a query context"""
        context = QueryContext(
            source="NDLS",
            destination="BCT",
            travel_date="2026-05-15"
        )
        
        assert context.source == "NDLS"
        assert context.destination == "BCT"
        assert context.travel_date == "2026-05-15"
        assert context.require_ac is False
        assert context.is_peak_hour is False
    
    def test_query_context_with_preferences(self):
        """Test query context with preferences"""
        context = QueryContext(
            source="NDLS",
            destination="BCT",
            travel_date="2026-05-15",
            require_ac=True,
            is_peak_hour=True,
            max_price=2000.0
        )
        
        assert context.require_ac is True
        assert context.is_peak_hour is True
        assert context.max_price == 2000.0


class TestHubPriority:
    """Tests for Hub Priority"""
    
    def test_hub_priority_creation(self):
        """Test creating a hub priority"""
        hub = HubPriority(
            station_code="NDLS",
            station_name="New Delhi",
            priority=0.9,
            historical_traffic=50000,
            transfer_success_rate=0.85
        )
        
        assert hub.station_code == "NDLS"
        assert hub.priority == 0.9
        assert hub.historical_traffic == 50000


class TestSearchDepth:
    """Tests for Search Depth enum"""
    
    def test_search_depth_values(self):
        """Test SearchDepth has expected values"""
        assert SearchDepth.DIRECT_ONLY.value == "direct"
        assert SearchDepth.ONE_TRANSFER.value == "one_transfer"
        assert SearchDepth.TWO_TRANSFERS.value == "two_transfers"
        assert SearchDepth.MULTI_TRANSFER.value == "multi_transfer"


class TestDatabaseTarget:
    """Tests for Database Target enum"""
    
    def test_database_target_values(self):
        """Test DatabaseTarget has expected values"""
        assert DatabaseTarget.READ_REPLICA.value == "read_replica"
        assert DatabaseTarget.PRIMARY.value == "primary"
        assert DatabaseTarget.CACHE_ONLY.value == "cache_only"


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])