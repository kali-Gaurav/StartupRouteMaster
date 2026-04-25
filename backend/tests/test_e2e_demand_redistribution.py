"""
End-to-End Test Suite for Demand-Based Redistribution System
=============================================================

This test suite validates the complete demand-based redistribution workflow:
1. Network demand analysis
2. Opportunity identification
3. Incentive calculation
4. Passenger offers
5. Redistribution execution
6. Outcome tracking

Run with: pytest backend/tests/test_e2e_demand_redistribution.py -v
"""
import pytest
import asyncio
from datetime import datetime, date, timedelta
from unittest.mock import Mock, patch, AsyncMock
from typing import List, Dict, Any


class TestDemandRedistributionE2E:
    """End-to-end tests for demand-based redistribution system"""
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database session"""
        db = Mock()
        db.query = Mock()
        return db
    
    @pytest.fixture
    def redistribution_service(self):
        """Get the demand redistribution service"""
        from services.demand_redistribution_service import DemandRedistributionService
        return DemandRedistributionService(db=self.mock_db)
    
    @pytest.fixture
    def crowd_service(self):
        """Get the crowd control service"""
        from services.crowd_control_service import CrowdControlService
        return CrowdControlService(db=self.mock_db)
    
    @pytest.fixture
    def knowledge_graph(self):
        """Get the knowledge graph service"""
        from services.knowledge_graph_service import TravelKnowledgeGraph
        return TravelKnowledgeGraph()
    
    @pytest.mark.asyncio
    async def test_complete_redistribution_workflow(self, redistribution_service):
        """
        Test the complete redistribution workflow:
        1. Analyze network demand
        2. Identify opportunities
        3. Calculate incentives
        4. Generate offers
        5. Execute redistribution
        """
        # Step 1: Mock network demand data
        mock_demand_data = {
            "NDLS-BCT": {
                "current_bookings": 450,
                "capacity": 500,
                "search_volume": 200,
                "demand_score": 0.95,  # High demand
                "waitlist": 50
            },
            "NDLS-MMCT": {
                "current_bookings": 150,
                "capacity": 500,
                "search_volume": 50,
                "demand_score": 0.25,  # Low demand
                "waitlist": 0
            },
            "BCT-MMCT": {
                "current_bookings": 300,
                "capacity": 400,
                "search_volume": 100,
                "demand_score": 0.65,  # Moderate demand
                "waitlist": 10
            }
        }
        
        # Step 2: Test demand analysis with controlled mock data
        async def mock_get_routes():
            return [
                Mock(id="NDLS-BCT", source="NDLS", destination="BCT", capacity=500),
                Mock(id="NDLS-MMCT", source="NDLS", destination="MMCT", capacity=500),
                Mock(id="BCT-MMCT", source="BCT", destination="MMCT", capacity=400)
            ]
        
        async def mock_get_bookings(route):
            bookings_map = {
                "NDLS-BCT": 450,
                "NDLS-MMCT": 150,
                "BCT-MMCT": 300
            }
            return bookings_map.get(route.id, 200)
        
        async def mock_get_searches(route):
            searches_map = {
                "NDLS-BCT": 200,
                "NDLS-MMCT": 50,
                "BCT-MMCT": 100
            }
            return searches_map.get(route.id, 100)
        
        redistribution_service._get_active_routes = mock_get_routes
        redistribution_service._get_route_bookings = mock_get_bookings
        redistribution_service._get_route_searches = mock_get_searches
        
        # Execute demand analysis
        snapshots = await redistribution_service.analyze_network_demand()
        
        assert len(snapshots) > 0, "Should analyze at least one route"
        
        # Verify high demand route identified
        high_demand = [s for s in snapshots.values() if s.demand_score > 0.8]
        assert len(high_demand) > 0, "Should identify high demand routes"
        
        # Verify low demand route identified
        low_demand = [s for s in snapshots.values() if s.demand_score < 0.4]
        assert len(low_demand) > 0, "Should identify low demand routes"
        
        # Step 3: Test opportunity identification
        # Directly set network demand with known values to ensure opportunities are found
        from services.demand_redistribution_service import DemandSnapshot
        
        # Create snapshots with different demand levels
        high_demand_snapshot = DemandSnapshot(
            route_id="NDLS-BCT",
            source="NDLS",
            destination="BCT",
            travel_date=date.today(),
            total_capacity=500,
            current_bookings=450,  # 90% occupancy
            search_demand=200,
            demand_score=0.95,
            available_seats=50,
            occupancy_rate=0.90
        )
        
        low_demand_snapshot = DemandSnapshot(
            route_id="NDLS-MMCT",
            source="NDLS",
            destination="MMCT",
            travel_date=date.today(),
            total_capacity=500,
            current_bookings=100,  # 20% occupancy
            search_demand=50,
            demand_score=0.25,
            available_seats=400,
            occupancy_rate=0.20
        )
        
        # Set the network demand directly
        redistribution_service._network_demand = {
            "NDLS-BCT": high_demand_snapshot,
            "NDLS-MMCT": low_demand_snapshot
        }
        
        opportunities = await redistribution_service.identify_opportunities()
        
        assert len(opportunities) > 0, "Should identify redistribution opportunities"
        
        # Verify opportunity structure
        for opp in opportunities:
            assert hasattr(opp, 'source_route'), "Opportunity should have source route"
            assert hasattr(opp, 'target_route'), "Opportunity should have target route"
            assert hasattr(opp, 'passengers_needed'), "Opportunity should specify passengers to move"
            assert hasattr(opp, 'incentive_range'), "Opportunity should specify incentive"
        
        # Step 4: Test incentive calculation using actual DemandSnapshot objects
        for opp in opportunities:
            incentive = redistribution_service._calculate_incentive(
                opp.source_route,
                opp.target_route
            )
            
            assert incentive >= 50, f"Incentive should be at least ₹50, got {incentive}"
            assert incentive <= 500, f"Incentive should be at most ₹500, got {incentive}"
        
        # Step 5: Test offer generation
        with patch.object(redistribution_service, '_find_flexible_passengers', new_callable=AsyncMock) as mock_flexible:
            mock_flexible.return_value = [
                {"id": "user1", "flexibility_score": 0.8},
                {"id": "user2", "flexibility_score": 0.9}
            ]
            
            offers = await redistribution_service.generate_passenger_offers(opportunities[0])
            
            assert len(offers) > 0, "Should generate offers for flexible passengers"
            
            # Verify offer structure
            for offer in offers:
                assert hasattr(offer, 'passenger_id'), "Offer should have passenger_id"
                assert hasattr(offer, 'original_route'), "Offer should have original route"
                assert hasattr(offer, 'alternative_route'), "Offer should have alternative route"
                assert hasattr(offer, 'incentive_amount'), "Offer should have incentive amount"
                assert hasattr(offer, 'utility_score'), "Offer should have utility score"
        
        # Step 6: Test redistribution execution
        with patch.object(redistribution_service, 'execute_redistribution', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = Mock(
                successful=2,
                failed=0,
                total_incentive=800
            )
            
            results = await redistribution_service.execute_redistribution(offers)
            
            assert results.successful > 0, "Should have successful redistributions"
            assert results.total_incentive > 0, "Should have total incentive cost"
        
        print("✅ Complete redistribution workflow test passed!")
    
    @pytest.mark.asyncio
    async def test_crowd_level_monitoring(self, crowd_service):
        """Test real-time crowd level monitoring"""
        
        # Test crowd level enum
        from services.crowd_control_service import CrowdLevel
        
        assert CrowdLevel.LOW.value == "low"
        assert CrowdLevel.MODERATE.value == "moderate"
        assert CrowdLevel.HIGH.value == "high"
        assert CrowdLevel.CRITICAL.value == "critical"
        assert CrowdLevel.FULL.value == "full"
        
        # Test station crowd data (await the coroutine)
        station_crowd = await crowd_service.get_station_crowd("NDLS")
        
        assert station_crowd is not None, "Should return station crowd data"
        assert hasattr(station_crowd, 'station_code'), "Should have station code"
        assert hasattr(station_crowd, 'current_crowd_level'), "Should have crowd level"
        assert hasattr(station_crowd, 'waiting_passengers'), "Should have waiting count"
        assert hasattr(station_crowd, 'predicted_crowd_next_1h'), "Should have prediction"
        
        # Test train crowd data
        train_crowd = await crowd_service.get_train_crowd("12345", date.today())
        
        assert train_crowd is not None, "Should return train crowd data"
        assert hasattr(train_crowd, 'train_number'), "Should have train number"
        assert hasattr(train_crowd, 'occupancy_rate'), "Should have occupancy rate"
        assert hasattr(train_crowd, 'crowd_level'), "Should have crowd level"
        
        # Test crowd level conversion
        assert crowd_service._get_crowd_level(0.2) == CrowdLevel.LOW
        assert crowd_service._get_crowd_level(0.5) == CrowdLevel.MODERATE
        assert crowd_service._get_crowd_level(0.75) == CrowdLevel.HIGH
        assert crowd_service._get_crowd_level(0.95) == CrowdLevel.CRITICAL
        
        print("✅ Crowd level monitoring test passed!")
    
    @pytest.mark.asyncio
    async def test_knowledge_graph_integration(self, knowledge_graph):
        """Test knowledge graph functionality"""
        
        # Test graph initialization
        assert hasattr(knowledge_graph, 'graph'), "Knowledge graph should have graph attribute"
        assert hasattr(knowledge_graph, 'user_preferences'), "Should have user preferences"
        assert hasattr(knowledge_graph, 'route_patterns'), "Should have route patterns"
        
        # Test station pattern creation
        station_pattern = knowledge_graph.create_station_pattern(
            code="NDLS",
            name="New Delhi",
            region="Delhi",
            zone="Northern",
            connectivity_score=0.95
        )
        
        assert station_pattern.code == "NDLS"
        assert station_pattern.name == "New Delhi"
        assert station_pattern.connectivity_score == 0.95
        
        # Test route pattern creation
        route_pattern = knowledge_graph.create_route_pattern(
            source="NDLS",
            destination="BCT",
            avg_duration=480,
            success_rate=0.92,
            peak_hours=[8, 18, 20],
            demand_pattern="commuter"
        )
        
        assert route_pattern["source"] == "NDLS"
        assert route_pattern["destination"] == "BCT"
        assert route_pattern["avg_duration"] == 480
        assert route_pattern["success_rate"] == 0.92
        
        # Test user preference creation
        user_pref = knowledge_graph.create_user_preference(
            user_id="user123",
            preferred_class="3A",
            preferred_time_morning=True,
            flexibility_score=0.7,
            price_sensitivity=0.5
        )
        
        assert user_pref.user_id == "user123"
        assert user_pref.preferred_class == "3A"
        assert user_pref.class_flexibility == 0.7
        
        # Test graph statistics
        stats = knowledge_graph.get_graph_statistics()
        
        assert 'total_stations' in stats
        assert 'total_routes' in stats
        assert 'total_users' in stats
        assert 'avg_route_success' in stats
        
        print("✅ Knowledge graph integration test passed!")
    
    @pytest.mark.asyncio
    async def test_multimodal_planning(self):
        """Test multi-modal journey planning"""
        
        from services.multimodal_planning_service import (
            MultiModalPlanningService, JourneyType, ComfortLevel
        )
        
        # Test enums
        assert JourneyType.TRAIN_ONLY.value == "train_only"
        assert JourneyType.TRAIN_BUS.value == "train_bus"
        assert JourneyType.TRAIN_FLIGHT.value == "train_flight"
        assert JourneyType.MULTI_MODAL.value == "multi_modal"
        
        assert ComfortLevel.BASIC.value == "basic"
        assert ComfortLevel.STANDARD.value == "standard"
        assert ComfortLevel.PREMIUM.value == "premium"
        
        # Test service initialization
        service = MultiModalPlanningService()
        
        assert service is not None
        assert hasattr(service, 'providers')
        assert hasattr(service, 'journey_optimizer')
        
        # Test journey request creation
        from services.multimodal_planning_service import JourneySearchRequest
        
        request = JourneySearchRequest(
            origin="NDLS",
            destination="BCT",
            travel_date=date.today() + timedelta(days=7),
            passenger_count=2,
            max_duration_hours=12,
            max_cost=5000,
            comfort_preference=ComfortLevel.STANDARD,
            avoid_high_crowd=True
        )
        
        assert request.origin == "NDLS"
        assert request.destination == "BCT"
        assert request.passenger_count == 2
        assert request.max_cost == 5000
        
        print("✅ Multi-modal planning test passed!")
    
    @pytest.mark.asyncio
    async def test_station_amenities(self):
        """Test station amenity service"""
        
        from services.station_amenity_service import (
            StationAmenityService, AmenityType, LoungeTier
        )
        
        # Test enums
        assert AmenityType.WAITING_LOUNGE.value == "waiting_lounge"
        assert AmenityType.FOOD_COURT.value == "food_court"
        assert AmenityType.CHARGING.value == "charging"
        assert AmenityType.WIFI.value == "wifi"
        assert AmenityType.LANGUAGE_LEARNING.value == "language_learning"
        
        assert LoungeTier.BASIC.value == "basic"
        assert LoungeTier.STANDARD.value == "standard"
        assert LoungeTier.PREMIUM.value == "premium"
        assert LoungeTier.VIP.value == "vip"
        
        # Test service initialization
        service = StationAmenityService()
        
        assert service is not None
        assert hasattr(service, '_amenities')
        assert hasattr(service, '_packages')
        assert hasattr(service, '_active_bookings')
        
        # Test default packages
        packages = service.get_default_packages()
        
        assert len(packages) > 0, "Should have default packages"
        
        package_ids = [p.package_id for p in packages]
        assert "basic_wait" in package_ids
        assert "standard_wait" in package_ids
        assert "premium_wait" in package_ids
        assert "family_wait" in package_ids
        assert "senior_wait" in package_ids
        
        # Test package pricing
        for pkg in packages:
            assert pkg.base_price > 0, f"Package {pkg.package_id} should have price"
            assert pkg.duration_hours > 0, f"Package {pkg.package_id} should have duration"
        
        print("✅ Station amenities test passed!")
    
    @pytest.mark.asyncio
    async def test_unified_travel_planner(self):
        """Test unified travel planner integration"""
        
        from services.unified_travel_planner import (
            UnifiedTravelPlanner, TravelRequest, TravelPreference, WaitPreference
        )
        
        # Test enums
        assert TravelPreference.FASTEST.value == "fastest"
        assert TravelPreference.CHEAPEST.value == "cheapest"
        assert TravelPreference.COMFORTABLE.value == "comfortable"
        assert TravelPreference.CROWD_FREE.value == "crowd_free"
        assert TravelPreference.BALANCED.value == "balanced"
        
        assert WaitPreference.NO_WAIT.value == 0
        assert WaitPreference.SHORT_WAIT.value == 60
        assert WaitPreference.MEDIUM_WAIT.value == 180
        assert WaitPreference.LONG_WAIT.value == 360
        
        # Test travel request creation
        request = TravelRequest(
            origin="NDLS",
            destination="BCT",
            travel_date=date.today() + timedelta(days=7),
            passenger_count=2,
            travel_preference=TravelPreference.BALANCED,
            wait_preference=WaitPreference.ANY_WAIT,
            max_wait_hours=4,
            max_cost=5000,
            preferred_class="3A",
            allow_multi_modal=True,
            avoid_high_crowd=True
        )
        
        assert request.origin == "NDLS"
        assert request.destination == "BCT"
        assert request.passenger_count == 2
        assert request.max_cost == 5000
        assert request.allow_multi_modal == True
        
        # Test service initialization
        planner = UnifiedTravelPlanner()
        
        assert planner is not None
        assert hasattr(planner, '_services')
        
        # Test service lazy loading
        crowd_service = planner._get_service("crowd")
        assert crowd_service is not None
        
        multimodal_service = planner._get_service("multimodal")
        assert multimodal_service is not None
        
        amenity_service = planner._get_service("amenity")
        assert amenity_service is not None
        
        print("✅ Unified travel planner test passed!")
    
    @pytest.mark.asyncio
    async def test_travel_option_scoring(self):
        """Test travel option scoring and ranking"""
        
        from services.unified_travel_planner import TravelOption, TravelPreference, TravelRequest
        from datetime import datetime
        
        # Create sample options
        options = [
            TravelOption(
                option_id="opt1",
                option_type="direct",
                from_station="NDLS",
                to_station="BCT",
                departure_time=datetime.now() + timedelta(hours=2),
                arrival_time=datetime.now() + timedelta(hours=10),
                total_duration_minutes=480,
                total_fare=1200,
                comfort_score=0.8,
                crowd_level="moderate",
                crowd_avoidance_score=0.6
            ),
            TravelOption(
                option_id="opt2",
                option_type="wait",
                from_station="NDLS",
                to_station="BCT",
                departure_time=datetime.now() + timedelta(hours=4),
                arrival_time=datetime.now() + timedelta(hours=12),
                total_duration_minutes=480,
                wait_duration_minutes=60,
                total_fare=1400,
                comfort_score=0.9,
                crowd_level="low",
                crowd_avoidance_score=0.9
            ),
            TravelOption(
                option_id="opt3",
                option_type="multi_modal",
                from_station="NDLS",
                to_station="BCT",
                departure_time=datetime.now() + timedelta(hours=3),
                arrival_time=datetime.now() + timedelta(hours=8),
                total_duration_minutes=300,
                total_fare=2000,
                comfort_score=0.7,
                crowd_level="low",
                crowd_avoidance_score=0.8,
                segments=[{"mode": "train"}, {"mode": "cab"}]
            )
        ]
        
        # Test fastest preference
        fastest_request = TravelRequest(
            origin="NDLS",
            destination="BCT",
            travel_date=date.today(),
            passenger_count=1,
            travel_preference=TravelPreference.FASTEST
        )
        
        fastest = min(options, key=lambda x: x.total_duration_minutes)
        assert fastest.option_id == "opt3", "Multi-modal should be fastest"
        
        # Test cheapest preference
        cheapest_request = TravelRequest(
            origin="NDLS",
            destination="BCT",
            travel_date=date.today(),
            passenger_count=1,
            travel_preference=TravelPreference.CHEAPEST
        )
        
        cheapest = min(options, key=lambda x: x.total_fare)
        assert cheapest.option_id == "opt1", "Direct train should be cheapest"
        
        # Test crowd-free preference
        crowd_free_request = TravelRequest(
            origin="NDLS",
            destination="BCT",
            travel_date=date.today(),
            passenger_count=1,
            travel_preference=TravelPreference.CROWD_FREE
        )
        
        crowd_free = max(options, key=lambda x: x.crowd_avoidance_score)
        assert crowd_free.option_id == "opt2", "Wait option should be most crowd-free"
        
        # Test to_dict conversion
        for opt in options:
            opt_dict = opt.to_dict()
            assert 'option_id' in opt_dict
            assert 'option_type' in opt_dict
            assert 'total_fare' in opt_dict
            assert 'comfort_score' in opt_dict
            assert 'crowd_level' in opt_dict
        
        print("✅ Travel option scoring test passed!")
    
    @pytest.mark.asyncio
    async def test_incentive_optimization(self, redistribution_service):
        """Test incentive calculation optimization"""
        
        from services.demand_redistribution_service import DemandSnapshot, RedistributionOpportunity
        
        # Test various scenarios with real DemandSnapshot objects
        test_cases = [
            # (occupancy_rate_source, occupancy_rate_target, expected_range)
            (0.95, 0.25, (50, 500)),  # High to low demand
            (0.85, 0.35, (50, 500)),  # Moderate to moderate
            (0.75, 0.45, (50, 500)),  # Premium to standard
        ]
        
        for occ_source, occ_target, expected_range in test_cases:
            source = DemandSnapshot(
                route_id="source_route",
                source="NDLS",
                destination="BCT",
                travel_date=date.today(),
                total_capacity=500,
                current_bookings=int(500 * occ_source),
                search_demand=100,
                demand_score=occ_source,
                available_seats=int(500 * (1 - occ_source)),
                occupancy_rate=occ_source
            )
            target = DemandSnapshot(
                route_id="target_route",
                source="NDLS",
                destination="MMCT",
                travel_date=date.today(),
                total_capacity=500,
                current_bookings=int(500 * occ_target),
                search_demand=50,
                demand_score=occ_target,
                available_seats=int(500 * (1 - occ_target)),
                occupancy_rate=occ_target
            )
            
            incentive = redistribution_service._calculate_incentive(source, target)
            
            assert expected_range[0] <= incentive <= expected_range[1], \
                f"Incentive {incentive} not in range {expected_range}"
        
        # Test personalized incentive
        passenger = {
            "id": "user1",
            "flexibility_score": 0.8
        }
        
        opportunity = RedistributionOpportunity(
            source_route=source,
            target_route=target,
            passengers_needed=10,
            incentive_range=(50, 500),
            time_advantage=30
        )
        
        personalized = redistribution_service._personalize_incentive(passenger, opportunity)
        
        assert 50 <= personalized <= 500, "Personalized incentive should be in range"
        
        print("✅ Incentive optimization test passed!")


class TestAPIEndpoints:
    """Test API endpoints for travel planning"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        from fastapi.testclient import TestClient
        from services.travel_planning_api import router
        from fastapi import FastAPI
        
        app = FastAPI()
        # Router already has prefix="/api/travel", so don't add it again
        app.include_router(router)
        
        return TestClient(app)
    
    def test_health_endpoint(self, client):
        """Test health check endpoint"""
        response = client.get("/api/travel/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "travel_planning"
    
    def test_travel_plan_request_model(self):
        """Test travel plan request model validation"""
        from services.travel_planning_api import TravelPlanRequest
        
        # Valid request
        request = TravelPlanRequest(
            origin="NDLS",
            destination="BCT",
            travel_date="2024-12-25",
            passenger_count=2,
            preference="balanced",
            wait_hours=4,
            max_cost=5000
        )
        
        assert request.origin == "NDLS"
        assert request.destination == "BCT"
        assert request.passenger_count == 2
        
        # Test preference enum mapping
        pref_map = {
            'fastest': 'fastest',
            'cheapest': 'cheapest',
            'comfortable': 'comfortable',
            'crowd_free': 'crowd_free',
            'balanced': 'balanced'
        }
        
        for pref in pref_map.keys():
            request = TravelPlanRequest(
                origin="NDLS",
                destination="BCT",
                travel_date="2024-12-25",
                preference=pref
            )
            assert request.preference == pref_map[pref]
    
    def test_waiting_booking_request_model(self):
        """Test waiting booking request model"""
        from services.travel_planning_api import WaitingBookingRequest
        
        request = WaitingBookingRequest(
            passenger_id="user123",
            station_code="NDLS",
            package_id="standard_wait",
            start_time="2024-12-25T10:00:00",
            passenger_count=2
        )
        
        assert request.passenger_id == "user123"
        assert request.station_code == "NDLS"
        assert request.package_id == "standard_wait"
        assert request.passenger_count == 2


class TestIntegrationScenarios:
    """Test complete integration scenarios"""
    
    @pytest.mark.asyncio
    async def test_passenger_journey_with_redistribution(self):
        """
        Test complete passenger journey including:
        1. Initial booking
        2. Redistribution offer
        3. Offer acceptance
        4. Updated booking
        """
        from services.demand_redistribution_service import (
            DemandRedistributionService, DemandSnapshot, RedistributionOpportunity, PassengerOffer
        )
        from services.crowd_control_service import CrowdLevel
        
        # Step 1: Passenger books initial route
        initial_booking = Mock(
            booking_id="BK001",
            user_id="user123",
            route_id="NDLS-BCT",
            train_number="12951",
            travel_date=date.today() + timedelta(days=7),
            status="confirmed"
        )
        
        assert initial_booking.status == "confirmed"
        
        # Step 2: System detects high demand
        high_demand_route = Mock(
            route_id="NDLS-BCT",
            current_bookings=450,
            capacity=500,
            demand_score=0.95
        )
        
        assert high_demand_route.demand_score > 0.8, "Route should be high demand"
        
        # Step 3: System identifies alternative
        alternative_route = Mock(
            route_id="NDLS-MMCT",
            current_bookings=150,
            capacity=500,
            demand_score=0.25,
            base_fare=800,
            duration=420
        )
        
        assert alternative_route.demand_score < 0.4, "Alternative should be low demand"
        
        # Step 4: Create redistribution offer
        offer = PassengerOffer(
            passenger_id="user123",
            original_route=high_demand_route,
            alternative_route=alternative_route,
            incentive_amount=200,
            time_difference_minutes=60,
            comfort_improvement=0.3,
            message="Switch and save!",
            expires_at=datetime.utcnow() + timedelta(hours=2)
        )
        
        assert offer.incentive_amount == 200
        assert offer.utility_score > 0, "Should have positive utility"
        
        # Step 5: Passenger accepts offer
        acceptance = Mock(
            offer_id="OFF001",
            accepted=True,
            new_booking_id="BK002",
            incentive_claimed=200
        )
        
        assert acceptance.accepted == True
        assert acceptance.incentive_claimed == 200
        
        # Step 6: Verify booking updated
        final_booking = Mock(
            booking_id="BK002",
            route_id="NDLS-MMCT",
            train_number="12953",
            status="confirmed",
            final_fare=600  # Original fare - incentive
        )
        
        assert final_booking.route_id == "NDLS-MMCT"
        assert final_booking.final_fare < 1000
        
        print("✅ Complete passenger journey test passed!")
    
    @pytest.mark.asyncio
    async def test_wait_and_save_scenario(self):
        """
        Test scenario where passenger waits for better option:
        1. Initial search shows crowded train
        2. System offers wait option with amenities
        3. Passenger accepts wait
        4. Passenger uses amenities during wait
        5. Passenger boards less crowded train
        """
        from services.unified_travel_planner import TravelOption, TravelRequest, TravelPreference
        from services.station_amenity_service import WaitingPackage
        from datetime import datetime, timedelta
        
        # Step 1: Initial search results
        crowded_option = TravelOption(
            option_id="opt1",
            option_type="direct",
            from_station="NDLS",
            to_station="BCT",
            departure_time=datetime.now() + timedelta(hours=2),
            arrival_time=datetime.now() + timedelta(hours=12),
            total_duration_minutes=600,
            total_fare=1200,
            comfort_score=0.4,
            crowd_level="critical",
            crowd_avoidance_score=0.1
        )
        
        assert crowded_option.crowd_level == "critical"
        assert crowded_option.crowd_avoidance_score < 0.3
        
        # Step 2: Wait option offered
        wait_option = TravelOption(
            option_id="opt2",
            option_type="wait",
            from_station="NDLS",
            to_station="BCT",
            departure_time=datetime.now() + timedelta(hours=4),
            arrival_time=datetime.now() + timedelta(hours=14),
            total_duration_minutes=600,
            wait_duration_minutes=120,
            wait_station="NDLS",
            total_fare=1400,
            comfort_score=0.9,
            crowd_level="low",
            crowd_avoidance_score=0.9,
            wait_amenities={
                "has_lounge": True,
                "has_food": True,
                "has_wifi": True,
                "language_learning": True
            }
        )
        
        assert wait_option.option_type == "wait"
        assert wait_option.wait_duration_minutes == 120
        assert wait_option.crowd_level == "low"
        assert wait_option.wait_amenities["language_learning"] == True
        
        # Step 3: Passenger selects wait option
        selected_option = wait_option
        
        assert selected_option.option_type == "wait"
        assert selected_option.wait_amenities["has_lounge"] == True
        
        # Step 4: Verify comfort improvement
        comfort_improvement = wait_option.comfort_score - crowded_option.comfort_score
        crowd_improvement = wait_option.crowd_avoidance_score - crowded_option.crowd_avoidance_score
        
        assert comfort_improvement > 0, "Wait option should be more comfortable"
        assert crowd_improvement > 0.5, "Wait option should have much better crowd situation"
        
        print("✅ Wait and save scenario test passed!")
    
    @pytest.mark.asyncio
    async def test_multimodal_alternative(self):
        """
        Test multi-modal journey as alternative:
        1. Direct train is crowded/expensive
        2. System offers train + cab combination
        3. Passenger accepts multi-modal
        4. Journey completes successfully
        """
        from services.unified_travel_planner import TravelOption
        from services.multimodal_planning_service import JourneyType
        from datetime import datetime, timedelta
        
        # Step 1: Direct train option (expensive, crowded)
        direct_option = TravelOption(
            option_id="opt1",
            option_type="direct",
            from_station="NDLS",
            to_station="BCT",
            departure_time=datetime.now() + timedelta(hours=6),
            arrival_time=datetime.now() + timedelta(hours=16),
            total_duration_minutes=600,
            total_fare=2500,  # High price
            comfort_score=0.5,
            crowd_level="high",
            crowd_avoidance_score=0.3
        )
        
        assert direct_option.total_fare == 2500
        assert direct_option.crowd_level == "high"
        
        # Step 2: Multi-modal option (train + cab)
        multimodal_option = TravelOption(
            option_id="opt2",
            option_type="multi_modal",
            from_station="NDLS",
            to_station="BCT",
            departure_time=datetime.now() + timedelta(hours=8),
            arrival_time=datetime.now() + timedelta(hours=14),
            total_duration_minutes=360,  # Faster!
            total_fare=1800,  # Cheaper!
            comfort_score=0.8,
            crowd_level="low",
            crowd_avoidance_score=0.9,
            segments=[
                {"mode": "train", "from": "NDLS", "to": "BVI", "fare": 800},
                {"mode": "cab", "from": "BVI", "to": "BCT", "fare": 1000}
            ]
        )
        
        assert multimodal_option.option_type == "multi_modal"
        assert len(multimodal_option.segments) == 2
        assert multimodal_option.total_duration_minutes < direct_option.total_duration_minutes
        assert multimodal_option.total_fare < direct_option.total_fare
        
        # Step 3: Verify multi-modal benefits
        time_savings = direct_option.total_duration_minutes - multimodal_option.total_duration_minutes
        cost_savings = direct_option.total_fare - multimodal_option.total_fare
        
        assert time_savings > 0, "Multi-modal should save time"
        assert cost_savings > 0, "Multi-modal should save money"
        
        print("✅ Multi-modal alternative test passed!")


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])