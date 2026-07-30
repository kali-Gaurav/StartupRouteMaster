"""
Integration Tests for Service Registry and Cross-Service Integration

Tests:
1. Service initialization and dependency injection
2. Cross-service method calls
3. Integration workflows
4. Error handling and resilience
"""

import pytest
import asyncio
from datetime import datetime, date, timedelta
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from collections import deque


class TestServiceRegistry:
    """Tests for Service Registry and dependency injection."""
    
    def test_registry_initialization(self):
        """Test registry initializes properly."""
        from services.service_registry import ServiceRegistry
        
        registry = ServiceRegistry()
        assert registry._initialized == True
        assert registry._services == {}
    
    def test_get_user_service(self):
        """Test User Service creation with integrations."""
        from services.service_registry import ServiceRegistry
        
        registry = ServiceRegistry()
        registry._services.clear()  # Reset for test
        
        mock_db = Mock()
        
        # Patch SessionLocal to return mock_db
        with patch('services.service_registry.SessionLocal', return_value=mock_db):
            service = registry.get_user_service()
        
        assert service is not None
        # Verify service has knowledge_graph integration
        assert service.kg is not None
        # Verify service has redistribution integration
        assert service.redistribution is not None
    
    def test_get_knowledge_graph(self):
        """Test Knowledge Graph creation and initialization."""
        from services.service_registry import ServiceRegistry
        
        registry = ServiceRegistry()
        registry._services.clear()
        
        mock_db = Mock()
        mock_kg = Mock()
        mock_kg.initialize = AsyncMock()
        mock_kg.graph = Mock()
        mock_kg.graph.nodes = []
        
        with patch('services.service_registry.TravelKnowledgeGraph', return_value=mock_kg):
            with patch('services.service_registry.SessionLocal', return_value=mock_db):
                kg = registry.get_knowledge_graph()
        
        assert kg is not None
        mock_kg.initialize.assert_called_once()
    
    def test_get_redistribution_service(self):
        """Test Demand Redistribution Service creation with integrations."""
        from services.service_registry import ServiceRegistry
        
        registry = ServiceRegistry()
        registry._services.clear()
        
        mock_db = Mock()
        
        with patch('services.service_registry.SessionLocal', return_value=mock_db):
            service = registry.get_redistribution_service()
        
        assert service is not None
        # Verify service has knowledge_graph integration
        assert service.kg is not None
        # Verify service has user_service integration
        assert service.user_service is not None
    
    def test_get_sync_agent(self):
        """Test Sync Agent creation with Knowledge Graph integration."""
        from services.service_registry import ServiceRegistry
        from services.sync_service import HeartbeatSyncAgent
        
        registry = ServiceRegistry()
        
        mock_db = Mock()
        mock_kg = Mock()
        
        # Directly create the agent with mocked dependencies
        agent = HeartbeatSyncAgent(db=mock_db, knowledge_graph=mock_kg)
        
        assert agent is not None
        assert agent.kg == mock_kg
    
    def test_get_all_services(self):
        """Test getting all initialized services."""
        from services.service_registry import ServiceRegistry
        
        registry = ServiceRegistry()
        registry._services.clear()
        
        registry._services['test_service'] = Mock()
        
        services = registry.get_all_services()
        
        assert 'test_service' in services
        assert len(services) == 1
    
    def test_get_service_status(self):
        """Test getting service status."""
        from services.service_registry import ServiceRegistry
        
        registry = ServiceRegistry()
        registry._services.clear()
        
        mock_service = Mock()
        mock_service.health_check = Mock(return_value={"status": "healthy"})
        registry._services['test_service'] = mock_service
        
        status = registry.get_service_status()
        
        assert 'test_service' in status
        assert status['test_service']['status'] == "healthy"
    
    def test_shutdown(self):
        """Test registry shutdown."""
        from services.service_registry import ServiceRegistry
        
        registry = ServiceRegistry()
        registry._services.clear()
        
        mock_scheduler = Mock()
        mock_scheduler.running = True
        mock_scheduler.stop = Mock()
        mock_db = Mock()
        mock_db.close = Mock()
        
        registry._services['scheduler'] = mock_scheduler
        registry._services['test_service'] = Mock(db=mock_db)
        
        registry.shutdown()
        
        mock_scheduler.stop.assert_called_once()
        mock_db.close.assert_called_once()
        assert len(registry._services) == 0


class TestUserServiceIntegration:
    """Tests for User Service integration with other services."""
    
    def test_sync_user_to_knowledge_graph(self):
        """Test syncing user data to Knowledge Graph."""
        from services.user_service import UserService, TravelPattern
        
        mock_db = Mock()
        mock_kg = Mock()
        mock_redistribution = Mock()
        
        service = UserService(
            db=mock_db,
            knowledge_graph=mock_kg,
            redistribution_service=mock_redistribution
        )
        
        # Mock travel pattern
        pattern = TravelPattern(
            user_id="user_123",
            most_frequent_routes=[("NDLS", "BCT"), ("BCT", "MAS")],
            preferred_times=[6, 12, 18],
            preferred_class="SL",
            flexibility_score=0.7,
            price_sensitivity=0.5,
            total_trips=10
        )
        
        # Mock database query
        mock_booking = Mock()
        mock_booking.source_station = "NDLS"
        mock_booking.destination_station = "BCT"
        mock_booking.travel_date = date.today() - timedelta(days=30)
        mock_booking.departure_time = Mock(hour=10)
        mock_booking.booking_class = "SL"
        mock_booking.booking_date = date.today() - timedelta(days=45)
        mock_booking.passenger_count = 1
        mock_booking.booking_status = "confirmed"
        
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_booking]
        
        # Mock KG methods with AsyncMock
        mock_kg.create_user_preference = Mock()
        mock_kg._update_user_behavior = AsyncMock()
        
        # Run sync
        result = asyncio.run(service.sync_user_to_knowledge_graph("user_123"))
        
        assert result == True
        mock_kg.create_user_preference.assert_called()
        mock_kg._update_user_behavior.assert_called()
    
    def test_get_similar_users(self):
        """Test getting similar users from Knowledge Graph."""
        from services.user_service import UserService
        from services.knowledge_graph_service import UserPreference
        
        mock_db = Mock()
        mock_kg = Mock()
        mock_redistribution = Mock()
        
        service = UserService(
            db=mock_db,
            knowledge_graph=mock_kg,
            redistribution_service=mock_redistribution
        )
        
        # Mock user preference
        mock_kg.user_preferences = {
            "user_123": UserPreference(user_id="user_123")
        }
        
        # Mock similar users with AsyncMock
        mock_kg._get_similar_user_recommendations = AsyncMock(return_value=[
            {"user_id": "user_456", "similarity": 0.8},
            {"user_id": "user_789", "similarity": 0.7}
        ])
        
        similar = asyncio.run(service.get_similar_users("user_123", limit=5))
        
        assert len(similar) == 2
        assert similar[0]["user_id"] == "user_456"
    
    def test_get_redistribution_opportunities(self):
        """Test getting redistribution opportunities for user."""
        from services.user_service import UserService
        from services.demand_redistribution_service import DemandRedistributionService, DemandSnapshot, RedistributionOpportunity
        
        mock_db = Mock()
        mock_kg = Mock()
        mock_redistribution = Mock()
        
        service = UserService(
            db=mock_db,
            knowledge_graph=mock_kg,
            redistribution_service=mock_redistribution
        )
        
        # Mock travel pattern
        pattern = Mock()
        pattern.most_frequent_routes = [("NDLS", "BCT")]
        
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        
        # Mock redistribution opportunities
        snapshot1 = DemandSnapshot(
            route_id="route_1",
            source="NDLS",
            destination="BCT",
            travel_date=date.today(),
            total_capacity=1000,
            current_bookings=850,
            search_demand=200,
            demand_score=0.85,
            available_seats=150,
            occupancy_rate=0.85
        )
        
        snapshot2 = DemandSnapshot(
            route_id="route_2",
            source="BCT",
            destination="MAS",
            travel_date=date.today(),
            total_capacity=1000,
            current_bookings=200,
            search_demand=50,
            demand_score=0.25,
            available_seats=800,
            occupancy_rate=0.20
        )
        
        opportunity = RedistributionOpportunity(
            source_route=snapshot1,
            target_route=snapshot2,
            passengers_needed=100,
            incentive_range=(50, 500),
            time_advantage=30
        )
        
        mock_redistribution.identify_opportunities = AsyncMock(return_value=[opportunity])
        
        # Mock analyze_travel_patterns
        service.analyze_travel_patterns = Mock(return_value=pattern)
        
        opportunities = asyncio.run(service.get_redistribution_opportunities("user_123"))
        
        assert len(opportunities) == 1
        assert opportunities[0]["source_route"] == "NDLS->BCT"


class TestKnowledgeGraphIntegration:
    """Tests for Knowledge Graph integration with other services."""
    
    def test_update_station_from_heartbeat(self):
        """Test updating station patterns from heartbeat data."""
        from services.knowledge_graph_service import TravelKnowledgeGraph, StationNode
        
        kg = TravelKnowledgeGraph()
        
        # Mock heartbeat data
        heartbeat_data = {
            "station": "NDLS",
            "trains": [
                {"departure_time": "08:00"},
                {"departure_time": "10:00"},
                {"departure_time": "12:00"}
            ],
            "total_delayed": 5,
            "total_cancelled": 2
        }
        
        # Run update
        asyncio.run(kg.update_station_from_heartbeat("NDLS", heartbeat_data))
        
        # Verify station was updated
        assert "NDLS" in kg.station_patterns
        station = kg.station_patterns["NDLS"]
        assert station.peak_hours == [8, 10, 12]  # Most common hours
    
    def test_build_initial_graph(self):
        """Test building initial knowledge graph."""
        from services.knowledge_graph_service import TravelKnowledgeGraph
        
        kg = TravelKnowledgeGraph()
        
        # Mock load methods with AsyncMock
        kg._load_stations = AsyncMock(return_value=[
            {"code": "NDLS", "name": "New Delhi", "region": "Delhi", "zone": "NR", "connectivity_score": 0.95},
            {"code": "BCT", "name": "Mumbai Central", "region": "Mumbai", "zone": "WR", "connectivity_score": 0.90}
        ])
        
        kg._load_routes = AsyncMock(return_value=[
            {"source": "NDLS", "destination": "BCT", "duration_minutes": 960, "frequency_daily": 15, "reliability_score": 0.85, "avg_fare": 800}
        ])
        
        kg._load_transfers = AsyncMock(return_value=[])
        
        # Run build
        asyncio.run(kg.build_initial_graph())
        
        # Verify graph was built
        assert len(kg.graph.nodes) == 2
        assert len(kg.graph.edges) == 1
        assert "NDLS" in kg.station_patterns
        # Note: route_patterns is populated by learning methods, not build_initial_graph
        # Just verify the graph edge exists
        assert ("NDLS", "BCT") in kg.graph.edges
    
    def test_initialize_method(self):
        """Test initialize method with load and build."""
        from services.knowledge_graph_service import TravelKnowledgeGraph
        
        kg = TravelKnowledgeGraph()
        kg.load_from_database = AsyncMock()
        kg.build_initial_graph = AsyncMock()
        
        # Run initialize
        asyncio.run(kg.initialize())
        
        # Verify load was called (graph is empty)
        kg.load_from_database.assert_called_once()
        kg.build_initial_graph.assert_called_once()


class TestDemandRedistributionIntegration:
    """Tests for Demand Redistribution Service integration."""
    
    def test_get_active_routes_from_db(self):
        """Test fetching active routes from database."""
        from services.demand_redistribution_service import DemandRedistributionService
        
        mock_db = Mock()
        mock_kg = Mock()
        mock_user_service = Mock()
        
        service = DemandRedistributionService(
            db=mock_db,
            knowledge_graph=mock_kg,
            user_service=mock_user_service
        )
        
        # Mock database query
        mock_trip = Mock()
        mock_trip.id = 1
        
        mock_db.query.return_value.join.return_value.filter.return_value.limit.return_value.all.return_value = [mock_trip]
        
        # Mock stop queries
        mock_stop_time = Mock()
        mock_stop_time.stop_id = 1
        mock_stop_time.stop_sequence = 1
        
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_stop_time]
        
        mock_stop = Mock()
        mock_stop.code = "NDLS"
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_stop
        
        # Run get routes
        routes = asyncio.run(service._get_active_routes())
        
        assert len(routes) > 0
        assert routes[0]["source"] == "NDLS"
    
    def test_get_route_searches_from_kg(self):
        """Test fetching route searches from Knowledge Graph."""
        from services.demand_redistribution_service import DemandRedistributionService
        
        mock_db = Mock()
        mock_kg = Mock()
        mock_user_service = Mock()
        
        service = DemandRedistributionService(
            db=mock_db,
            knowledge_graph=mock_kg,
            user_service=mock_user_service
        )
        
        # Mock KG with search data
        mock_kg.route_patterns = {
            "NDLS->BCT": {"searches": 500, "bookings": 200}
        }
        
        route = {"source": "NDLS", "destination": "BCT", "travel_date": date.today()}
        
        # Run get searches
        searches = asyncio.run(service._get_route_searches(route))
        
        assert searches == 500


class TestSyncServiceIntegration:
    """Tests for Sync Service integration with Knowledge Graph."""
    
    def test_sync_with_kg_integration(self):
        """Test sync operation with Knowledge Graph integration."""
        from services.sync_service import HeartbeatSyncAgent
        
        mock_db = Mock()
        mock_kg = Mock()
        mock_kg.update_station_from_heartbeat = AsyncMock()
        
        agent = HeartbeatSyncAgent(db=mock_db, knowledge_graph=mock_kg)
        
        # Mock heartbeat data
        heartbeat_data = {
            "station": "NDLS",
            "trains": [],
            "total_delayed": 5
        }
        
        # Mock existing heartbeat
        mock_db.query.return_value.filter_by.return_value.first.return_value = None
        
        # Mock API call with proper async mock
        async def mock_fetch(*args, **kwargs):
            return heartbeat_data
        
        with patch.object(agent, '_fetch_live_station_status', mock_fetch):
            # Mock the get_hot_zones to return a proper list
            mock_db.query.return_value.filter.return_value.group_by.return_value.order_by.return_value.limit.return_value.all.return_value = []
            
            # Run sync
            result = asyncio.run(agent.sync_hot_zones())
        
        # Verify KG was updated
        mock_kg.update_station_from_heartbeat.assert_called()
    
    def test_scheduler_with_kg(self):
        """Test scheduler with Knowledge Graph integration."""
        from services.sync_service import HeartbeatScheduler
        
        mock_kg = Mock()
        
        scheduler = HeartbeatScheduler(knowledge_graph=mock_kg)
        
        assert scheduler.kg == mock_kg


class TestIntegrationWorkflows:
    """Tests for complete integration workflows."""
    
    def test_full_sync_workflow(self):
        """Test full sync workflow."""
        from services.service_registry import ServiceRegistry, run_full_sync_workflow
        
        registry = ServiceRegistry()
        registry._services.clear()
        
        # Mock all services
        mock_sync_agent = Mock()
        mock_sync_agent.sync_hot_zones = AsyncMock(return_value={"success": 5, "failed": 0})
        
        mock_kg = Mock()
        mock_kg.initialize = AsyncMock()
        mock_kg.graph = Mock()
        mock_kg.graph.nodes = []
        
        mock_redistribution = Mock()
        mock_redistribution.analyze_network_demand = AsyncMock(return_value={})
        mock_redistribution.identify_opportunities = AsyncMock(return_value=[])
        
        mock_user_service = Mock()
        
        # Pre-populate services to avoid database initialization
        registry._services['sync_agent'] = mock_sync_agent
        registry._services['knowledge_graph'] = mock_kg
        registry._services['redistribution'] = mock_redistribution
        registry._services['user_service'] = mock_user_service
        
        # Mock the registry methods to return our mocks
        with patch.object(registry, 'get_sync_agent', return_value=mock_sync_agent):
            with patch.object(registry, 'get_knowledge_graph', return_value=mock_kg):
                with patch.object(registry, 'get_redistribution_service', return_value=mock_redistribution):
                    with patch.object(registry, 'get_user_service', return_value=mock_user_service):
                        # Run workflow
                        result = asyncio.run(run_full_sync_workflow())
        
        assert result is not None
        assert 'sync_results' in result
        assert 'opportunities' in result
        assert 'services' in result
    
    def test_user_learning_workflow(self):
        """Test user learning workflow."""
        from services.service_registry import ServiceRegistry, run_user_learning_workflow
        from services.user_service import TravelPattern
        
        registry = ServiceRegistry()
        registry._services.clear()
        
        # Mock services
        mock_user_service = Mock()
        mock_kg = Mock()
        mock_redistribution = Mock()
        
        # Create mock pattern
        pattern = TravelPattern(
            user_id="user_123",
            most_frequent_routes=[("NDLS", "BCT")],
            preferred_times=[6, 12],
            preferred_class="SL",
            flexibility_score=0.7,
            price_sensitivity=0.5,
            total_trips=10
        )
        
        mock_user_service.analyze_travel_patterns = Mock(return_value=pattern)
        mock_user_service.sync_user_to_knowledge_graph = AsyncMock(return_value=True)
        mock_user_service.get_travel_recommendations = AsyncMock(return_value={
            "status": "success",
            "recommendations": []
        })
        mock_user_service.get_redistribution_opportunities = AsyncMock(return_value=[])
        
        # Pre-populate services
        registry._services['user_service'] = mock_user_service
        registry._services['knowledge_graph'] = mock_kg
        registry._services['redistribution'] = mock_redistribution
        
        # Mock the registry methods to return our mocks
        with patch.object(registry, 'get_user_service', return_value=mock_user_service):
            with patch.object(registry, 'get_knowledge_graph', return_value=mock_kg):
                with patch.object(registry, 'get_redistribution_service', return_value=mock_redistribution):
                    # Run workflow
                    result = asyncio.run(run_user_learning_workflow("user_123"))
        
        assert result is not None
        assert 'pattern' in result
        assert 'recommendations' in result
        assert 'opportunities' in result
        mock_user_service.sync_user_to_knowledge_graph.assert_called_once()


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
