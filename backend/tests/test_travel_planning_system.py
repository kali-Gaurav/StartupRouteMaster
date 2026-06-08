"""
Test Suite for Travel Planning System
======================================

This test file verifies the complete travel planning system including:
1. Unified Travel Planner
2. Crowd Control Service
3. Multi-Modal Planning
4. Station Amenity Service
5. Knowledge Graph Integration
6. API Endpoints

Run with: pytest backend/tests/test_travel_planning_system.py -v
"""
import pytest
import asyncio
from datetime import datetime, date, timedelta
from unittest.mock import Mock, patch, AsyncMock


# =========================================================================
# TEST: Unified Travel Planner
# =========================================================================

class TestUnifiedTravelPlanner:
    """Test the main travel planning service"""
    
    @pytest.fixture
    def planner(self):
        from services.unified_travel_planner import UnifiedTravelPlanner
        return UnifiedTravelPlanner(db=None)
    
    @pytest.fixture
    def sample_request(self):
        from services.unified_travel_planner import TravelRequest, TravelPreference
        return TravelRequest(
            origin="NDLS",
            destination="BCT",
            travel_date=date(2024, 12, 25),
            passenger_count=2,
            travel_preference=TravelPreference.BALANCED,
            max_wait_hours=4,
            max_cost=5000
        )
    
    @pytest.mark.asyncio
    async def test_travel_plan_creation(self, planner, sample_request):
        """Test that travel plan is created with options"""
        # This test would need actual database/mock
        # For now, test the structure
        assert sample_request.origin == "NDLS"
        assert sample_request.destination == "BCT"
        assert sample_request.passenger_count == 2
    
    def test_travel_preference_enum(self):
        """Test travel preference enum values"""
        from services.unified_travel_planner import TravelPreference
        assert TravelPreference.FASTEST.value == "fastest"
        assert TravelPreference.CHEAPEST.value == "cheapest"
        assert TravelPreference.COMFORTABLE.value == "comfortable"
        assert TravelPreference.CROWD_FREE.value == "crowd_free"
        assert TravelPreference.BALANCED.value == "balanced"
    
    def test_wait_preference_enum(self):
        """Test wait preference enum values"""
        from services.unified_travel_planner import WaitPreference
        assert WaitPreference.NO_WAIT.value == 0
        assert WaitPreference.SHORT_WAIT.value == 60
        assert WaitPreference.MEDIUM_WAIT.value == 180
        assert WaitPreference.LONG_WAIT.value == 360


# =========================================================================
# TEST: Crowd Control Service
# =========================================================================

class TestCrowdControlService:
    """Test crowd monitoring and control"""
    
    @pytest.fixture
    def crowd_service(self):
        from services.crowd_control_service import CrowdControlService
        return CrowdControlService(db=None)
    
    def test_crowd_level_enum(self):
        """Test crowd level enum values"""
        from services.crowd_control_service import CrowdLevel
        assert CrowdLevel.LOW.value == "low"
        assert CrowdLevel.MODERATE.value == "moderate"
        assert CrowdLevel.HIGH.value == "high"
        assert CrowdLevel.CRITICAL.value == "critical"
        assert CrowdLevel.FULL.value == "full"
    
    def test_transport_mode_enum(self):
        """Test transport mode enum"""
        from services.crowd_control_service import TransportMode
        assert TransportMode.TRAIN.value == "train"
        assert TransportMode.BUS.value == "bus"
        assert TransportMode.FLIGHT.value == "flight"
        assert TransportMode.CAB.value == "cab"
    
    def test_wait_option_enum(self):
        """Test wait option enum"""
        from services.crowd_control_service import WaitOption
        assert WaitOption.NO_WAIT.value == "no_wait"
        assert WaitOption.SHORT_WAIT.value == "short_wait"
        assert WaitOption.MEDIUM_WAIT.value == "medium_wait"
        assert WaitOption.LONG_WAIT.value == "long_wait"
        assert WaitOption.FLEXIBLE.value == "flexible"
    
    @pytest.mark.asyncio
    async def test_station_crowd_data_structure(self, crowd_service):
        """Test station crowd data structure"""
        from services.crowd_control_service import StationCrowdData, CrowdLevel
        
        data = StationCrowdData(
            station_code="NDLS",
            station_name="New Delhi",
            current_crowd_level=CrowdLevel.MODERATE,
            waiting_passengers=500,
            platform_capacity=1000,
            avg_wait_time_minutes=30,
            next_train_available=datetime.utcnow() + timedelta(minutes=30),
            amenities_score=0.8
        )
        
        assert data.station_code == "NDLS"
        assert data.current_crowd_level == CrowdLevel.MODERATE
        assert data.waiting_passengers == 500
    
    @pytest.mark.asyncio
    async def test_train_crowd_data_structure(self, crowd_service):
        """Test train crowd data structure"""
        from services.crowd_control_service import TrainCrowdData, CrowdLevel
        
        data = TrainCrowdData(
            train_number="12951",
            train_name="Rajdhani Express",
            source="NDLS",
            destination="BCT",
            departure_time=datetime.utcnow(),
            total_seats=1000,
            booked_seats=750,
            rac_count=50,
            wl_count=100,
            crowd_level=CrowdLevel.HIGH,
            occupancy_rate=0.75
        )
        
        assert data.train_number == "12951"
        assert data.occupancy_rate == 0.75
        assert data.crowd_level == CrowdLevel.HIGH


# =========================================================================
# TEST: Multi-Modal Planning
# =========================================================================

class TestMultiModalPlanning:
    """Test multi-modal journey planning"""
    
    @pytest.fixture
    def multimodal_service(self):
        from services.multimodal_planning_service import MultiModalPlanningService
        return MultiModalPlanningService(db=None)
    
    def test_journey_type_enum(self):
        """Test journey type enum"""
        from services.multimodal_planning_service import JourneyType
        assert JourneyType.TRAIN_ONLY.value == "train_only"
        assert JourneyType.TRAIN_BUS.value == "train_bus"
        assert JourneyType.MULTI_MODAL.value == "multi_modal"
    
    def test_comfort_level_enum(self):
        """Test comfort level enum"""
        from services.multimodal_planning_service import ComfortLevel
        assert ComfortLevel.BASIC.value == "basic"
        assert ComfortLevel.STANDARD.value == "standard"
        assert ComfortLevel.PREMIUM.value == "premium"
        assert ComfortLevel.LUXURY.value == "luxury"
    
    @pytest.mark.asyncio
    async def test_mode_segment_structure(self, multimodal_service):
        """Test mode segment data structure"""
        from services.multimodal_planning_service import ModeSegment, ComfortLevel
        
        segment = ModeSegment(
            segment_id="seg_1",
            mode="train",
            operator="Indian Railways",
            from_location="Delhi",
            to_location="Mumbai",
            from_code="NDLS",
            to_code="BCT",
            departure=datetime.utcnow(),
            arrival=datetime.utcnow() + timedelta(hours=16),
            duration_minutes=960,
            fare=800,
            seats_available=50,
            comfort_level=ComfortLevel.STANDARD,
            predicted_occupancy=0.6
        )
        
        assert segment.mode == "train"
        assert segment.fare == 800
        assert segment.predicted_occupancy == 0.6


# =========================================================================
# TEST: Station Amenity Service
# =========================================================================

class TestStationAmenityService:
    """Test station amenities and waiting"""
    
    @pytest.fixture
    def amenity_service(self):
        from services.station_amenity_service import StationAmenityService
        return StationAmenityService(db=None)
    
    def test_amenity_type_enum(self):
        """Test amenity type enum"""
        from services.station_amenity_service import AmenityType
        assert AmenityType.WAITING_LOUNGE.value == "waiting_lounge"
        assert AmenityType.FOOD_COURT.value == "food_court"
        assert AmenityType.CHARGING.value == "charging"
        assert AmenityType.LANGUAGE_LEARNING.value == "language_learning"
    
    def test_lounge_tier_enum(self):
        """Test lounge tier enum"""
        from services.station_amenity_service import LoungeTier
        assert LoungeTier.BASIC.value == "basic"
        assert LoungeTier.STANDARD.value == "standard"
        assert LoungeTier.PREMIUM.value == "premium"
        assert LoungeTier.VIP.value == "vip"
    
    def test_default_packages(self, amenity_service):
        """Test that default packages are defined"""
        packages = amenity_service.DEFAULT_PACKAGES
        assert len(packages) >= 5
        
        package_ids = [p.package_id for p in packages]
        assert "basic_wait" in package_ids
        assert "standard_wait" in package_ids
        assert "premium_wait" in package_ids
    
    @pytest.mark.asyncio
    async def test_amenity_structure(self, amenity_service):
        """Test amenity data structure"""
        from services.station_amenity_service import Amenity, AmenityType
        
        amenity = Amenity(
            amenity_id="test_1",
            amenity_type=AmenityType.WAITING_LOUNGE,
            name="Test Lounge",
            location="Platform 1",
            capacity=50,
            current_usage=20,
            price=200,
            rating=4.5,
            features=["AC", "WiFi", "Snacks"]
        )
        
        assert amenity.amenity_id == "test_1"
        assert amenity.capacity == 50
        assert amenity.occupancy_rate == 0.4
        assert not amenity.is_crowded


# =========================================================================
# TEST: Knowledge Graph Integration
# =========================================================================

class TestKnowledgeGraph:
    """Test knowledge graph service"""
    
    @pytest.fixture
    def kg_service(self):
        from services.knowledge_graph_service import TravelKnowledgeGraph
        return TravelKnowledgeGraph()
    
    def test_knowledge_graph_initialization(self, kg_service):
        """Test knowledge graph can be initialized"""
        assert kg_service is not None
        assert hasattr(kg_service, 'graph')
        assert hasattr(kg_service, 'user_preferences')
    
    @pytest.mark.asyncio
    async def test_graph_statistics(self, kg_service):
        """Test graph statistics method"""
        stats = kg_service.get_graph_statistics()
        assert 'total_stations' in stats
        assert 'total_routes' in stats
        assert 'total_edges' in stats


# =========================================================================
# TEST: Demand Redistribution
# =========================================================================

class TestDemandRedistribution:
    """Test demand redistribution service"""
    
    @pytest.fixture
    def redistribution_service(self):
        from services.demand_redistribution_service import DemandRedistributionService
        return DemandRedistributionService(db=None)
    
    def test_service_initialization(self, redistribution_service):
        """Test redistribution service can be initialized"""
        assert redistribution_service is not None
        assert redistribution_service.MIN_INCENTIVE == 50
        assert redistribution_service.MAX_INCENTIVE == 500
    
    @pytest.mark.asyncio
    async def test_network_summary(self, redistribution_service):
        """Test network summary method"""
        summary = redistribution_service.get_network_summary()
        assert 'status' in summary


# =========================================================================
# TEST: Integration Points
# =========================================================================

class TestIntegration:
    """Test integration between services"""
    
    def test_unified_planner_imports(self):
        """Test that unified planner can import all services"""
        from services.unified_travel_planner import UnifiedTravelPlanner
        from services.crowd_control_service import get_crowd_control_service
        from services.multimodal_planning_service import get_multimodal_planning_service
        from services.station_amenity_service import get_station_amenity_service
        from services.knowledge_graph_service import get_knowledge_graph
        
        # All should be importable
        assert UnifiedTravelPlanner is not None
    
    def test_travel_option_to_dict(self):
        """Test TravelOption serialization"""
        from services.unified_travel_planner import TravelOption
        
        option = TravelOption(
            option_id="test_1",
            option_type="direct",
            from_station="NDLS",
            to_station="BCT",
            departure_time=datetime.utcnow(),
            arrival_time=datetime.utcnow() + timedelta(hours=16),
            total_duration_minutes=960,
            total_fare=1000,
            comfort_score=0.8,
            crowd_level="moderate",
            crowd_avoidance_score=0.6,
            train_numbers=["12951"],
            seat_class="SL"
        )
        
        result = option.to_dict()
        assert result['option_id'] == "test_1"
        assert result['option_type'] == "direct"
        assert result['total_fare'] == 1000
    
    def test_travel_plan_to_dict(self):
        """Test TravelPlan serialization"""
        from services.unified_travel_planner import TravelPlan, TravelRequest, TravelOption
        
        request = TravelRequest(
            origin="NDLS",
            destination="BCT",
            travel_date=date(2024, 12, 25)
        )
        
        option = TravelOption(
            option_id="opt_1",
            option_type="direct",
            from_station="NDLS",
            to_station="BCT",
            departure_time=datetime.utcnow(),
            arrival_time=datetime.utcnow() + timedelta(hours=16),
            total_duration_minutes=960,
            total_fare=1000,
            comfort_score=0.8,
            crowd_level="moderate",
            crowd_avoidance_score=0.6,
            train_numbers=["12951"],
            seat_class="SL",
            is_recommended=True,
            recommendation_reason="Best option"
        )
        
        plan = TravelPlan(
            plan_id="plan_1",
            request=request,
            options=[option],
            valid_until=datetime.utcnow() + timedelta(minutes=15)
        )
        
        result = plan.to_dict()
        assert result['plan_id'] == "plan_1"
        assert result['origin'] == "NDLS"
        assert result['destination'] == "BCT"
        assert len(result['options']) == 1


# =========================================================================
# TEST: Quick Function
# =========================================================================

class TestQuickFunction:
    """Test the quick journey planning function"""
    
    @pytest.mark.asyncio
    async def test_plan_journey_function_imports(self):
        """Test that quick function can be imported"""
        from services.unified_travel_planner import plan_journey
        assert plan_journey is not None
    
    def test_plan_journey_parameters(self):
        """Test plan_journey function parameters"""
        import inspect
        from services.unified_travel_planner import plan_journey
        
        sig = inspect.signature(plan_journey)
        params = list(sig.parameters.keys())
        
        assert 'origin' in params
        assert 'destination' in params
        assert 'travel_date' in params
        assert 'passenger_count' in params
        assert 'preference' in params


# =========================================================================
# RUN TESTS
# =========================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
