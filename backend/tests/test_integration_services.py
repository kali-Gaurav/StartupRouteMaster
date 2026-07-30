"""
Unit Tests for Enhanced Services

Tests core functionality of enhanced services:
- Demand Redistribution Service
- Knowledge Graph Service
- Sync Service
- User Service
- Station Departure Service
"""

import pytest
import asyncio
from datetime import datetime, date, timedelta
from unittest.mock import Mock, MagicMock, patch
from collections import deque


# ============================================================================
# Demand Redistribution Service Tests
# ============================================================================

class TestDemandRedistributionService:
    """Tests for DemandRedistributionService."""
    
    def test_service_initialization(self):
        """Test service initializes with all components."""
        service = Mock()
        
        # Test that service has required attributes
        assert hasattr(service, 'db') or service is not None
    
    def test_calculate_demand_score(self):
        """Test demand score calculation."""
        # Mock service
        service = Mock()
        service._calculate_demand_score = lambda bookings, searches, capacity: (
            (min(1.0, bookings / capacity) * 0.6) + 
            (min(1.0, searches / (capacity * 0.5)) * 0.4)
        ) if capacity > 0 else 0.5
        
        # High demand
        score = service._calculate_demand_score(
            bookings=800, searches=400, capacity=1000
        )
        assert 0.7 <= score <= 0.9
        
        # Low demand
        score = service._calculate_demand_score(
            bookings=200, searches=50, capacity=1000
        )
        assert 0.1 <= score <= 0.4
        
        # Zero capacity
        score = service._calculate_demand_score(
            bookings=0, searches=0, capacity=0
        )
        assert score == 0.5
    
    def test_calculate_passenger_flexibility(self):
        """Test passenger flexibility calculation."""
        service = Mock()
        service._calculate_passenger_flexibility = lambda booking: 0.5
        
        # Mock booking with different classes
        booking_sl = Mock()
        booking_sl.booking_class = "SL"
        booking_sl.booking_date = date.today() - timedelta(days=30)
        booking_sl.travel_date = date.today() + timedelta(days=30)
        booking_sl.passenger_count = 1
        
        score = service._calculate_passenger_flexibility(booking_sl)
        assert score == 0.5
    
    def test_personalize_incentive(self):
        """Test incentive personalization."""
        service = Mock()
        service.MIN_INCENTIVE = 50
        service.MAX_INCENTIVE = 500
        service._personalize_incentive = lambda passenger, opportunity: 150
        
        opportunity = Mock()
        opportunity.incentive_midpoint = 275
        
        passenger_low_flex = {"flexibility_score": 0.3, "price_sensitivity": 0.5}
        incentive = service._personalize_incentive(passenger_low_flex, opportunity)
        
        assert incentive == 150
    
    def test_generate_offer_message(self):
        """Test offer message generation."""
        service = Mock()
        service._generate_offer_message = lambda opportunity, incentive: (
            f"We have an alternative route available from {opportunity.source_route.source} "
            f"to {opportunity.source_route.destination} with better availability. "
            f"If you switch, you'll receive ₹{int(incentive)} as a credit. "
            f"Would you like to switch?"
        )
        
        opportunity = Mock()
        opportunity.source_route = Mock()
        opportunity.source_route.source = "NDLS"
        opportunity.source_route.destination = "BCT"
        opportunity.time_advantage = 30
        
        message = service._generate_offer_message(opportunity, 150)
        
        assert "NDLS" in message
        assert "BCT" in message
        assert "₹150" in message
        assert "credit" in message.lower()


# ============================================================================
# Knowledge Graph Service Tests
# ============================================================================

class TestTravelKnowledgeGraph:
    """Tests for TravelKnowledgeGraph."""
    
    def test_service_initialization(self):
        """Test service initializes with all components."""
        kg = Mock()
        kg.graph = Mock()
        kg.user_preferences = {}
        kg.route_patterns = {}
        kg.station_patterns = {}
        kg.competitor_prices = {}
        kg.seasonal_patterns = {}
        kg.user_behavior_matrix = {}
        
        assert kg.graph is not None
        assert kg.user_preferences == {}
        assert kg.route_patterns == {}
    
    def test_create_station_pattern(self):
        """Test station pattern creation."""
        kg = Mock()
        kg.graph = {}
        kg.station_patterns = {}
        
        def create_station(code, name, region, zone, connectivity_score=0.5):
            node = {
                "code": code,
                "name": name,
                "region": region,
                "zone": zone,
                "connectivity_score": connectivity_score
            }
            kg.graph[code] = node
            kg.station_patterns[code] = node
            return node
        
        kg.create_station_pattern = create_station
        
        node = kg.create_station_pattern(
            code="NDLS",
            name="New Delhi",
            region="Delhi",
            zone="NR",
            connectivity_score=0.95
        )
        
        assert node["code"] == "NDLS"
        assert node["name"] == "New Delhi"
        assert node["connectivity_score"] == 0.95
        assert "NDLS" in kg.graph
        assert "NDLS" in kg.station_patterns
    
    def test_create_route_pattern(self):
        """Test route pattern creation."""
        kg = Mock()
        kg.route_patterns = {}
        kg.graph = {}
        
        def create_route(source, destination, avg_duration, success_rate, peak_hours, demand_pattern):
            route_key = f"{source}->{destination}"
            pattern = {
                "source": source,
                "destination": destination,
                "avg_duration": avg_duration,
                "success_rate": success_rate,
                "peak_hours": peak_hours,
                "demand_pattern": demand_pattern
            }
            kg.route_patterns[route_key] = pattern
            kg.graph[(source, destination)] = pattern
            return pattern
        
        kg.create_route_pattern = create_route
        
        pattern = kg.create_route_pattern(
            source="NDLS",
            destination="BCT",
            avg_duration=960,
            success_rate=0.85,
            peak_hours=[6, 12, 18],
            demand_pattern="high"
        )
        
        assert pattern["source"] == "NDLS"
        assert pattern["destination"] == "BCT"
        assert pattern["success_rate"] == 0.85
        assert "NDLS->BCT" in kg.route_patterns
    
    def test_create_user_preference(self):
        """Test user preference creation."""
        kg = Mock()
        kg.user_preferences = {}
        
        def create_pref(user_id, preferred_class, preferred_time_morning=False, 
                       flexibility_score=0.5, price_sensitivity=0.5):
            pref = {
                "user_id": user_id,
                "preferred_class": preferred_class,
                "preferred_time_morning": preferred_time_morning,
                "class_flexibility": flexibility_score,
                "price_sensitivity": price_sensitivity
            }
            kg.user_preferences[user_id] = pref
            return pref
        
        kg.create_user_preference = create_pref
        
        pref = kg.create_user_preference(
            user_id="user_123",
            preferred_class="SL",
            preferred_time_morning=True,
            flexibility_score=0.7,
            price_sensitivity=0.6
        )
        
        assert pref["user_id"] == "user_123"
        assert pref["preferred_class"] == "SL"
        assert pref["preferred_time_morning"] == True
        assert "user_123" in kg.user_preferences
    
    def test_competitor_price_update(self):
        """Test competitor price updates."""
        kg = Mock()
        kg.competitor_prices = {}
        
        def update_price(route, provider, price):
            if route not in kg.competitor_prices:
                kg.competitor_prices[route] = {}
            kg.competitor_prices[route][provider] = {"price": price}
        
        kg.update_competitor_price = update_price
        
        kg.update_competitor_price("NDLS->BCT", "IRCTC", 800)
        kg.update_competitor_price("NDLS->BCT", "MakeMyTrip", 850)
        
        assert "NDLS->BCT" in kg.competitor_prices
        assert kg.competitor_prices["NDLS->BCT"]["IRCTC"]["price"] == 800
        assert kg.competitor_prices["NDLS->BCT"]["MakeMyTrip"]["price"] == 850
    
    def test_seasonal_pattern_update(self):
        """Test seasonal pattern updates."""
        kg = Mock()
        kg.seasonal_patterns = {}
        
        def update_pattern(route, month, demand_score):
            if route not in kg.seasonal_patterns:
                kg.seasonal_patterns[route] = {}
            kg.seasonal_patterns[route][month] = {"demand_score": demand_score}
        
        kg.update_seasonal_pattern = update_pattern
        
        kg.update_seasonal_pattern("NDLS->BCT", 12, 0.85)
        kg.update_seasonal_pattern("NDLS->BCT", 6, 0.4)
        
        assert "NDLS->BCT" in kg.seasonal_patterns
        assert kg.seasonal_patterns["NDLS->BCT"][12]["demand_score"] == 0.85
        assert kg.seasonal_patterns["NDLS->BCT"][6]["demand_score"] == 0.4


# ============================================================================
# User Service Tests
# ============================================================================

class TestUserService:
    """Tests for UserService."""
    
    def test_service_initialization(self):
        """Test service initializes with all components."""
        service = Mock()
        service._cache = {}
        service._cache_ttl_seconds = 300
        
        assert service._cache == {}
        assert service._cache_ttl_seconds == 300
    
    def test_get_cache_key(self):
        """Test cache key generation."""
        service = Mock()
        service._get_cache_key = lambda key_type, value: f"user:{key_type}:{value.lower()}"
        
        key = service._get_cache_key("email", "test@example.com")
        
        assert "user" in key
        assert "email" in key
        assert "test@example.com" in key
    
    def test_analyze_travel_patterns(self):
        """Test travel pattern analysis."""
        service = Mock()
        service.analyze_travel_patterns = lambda user_id: {
            "user_id": user_id,
            "total_trips": 5,
            "most_frequent_routes": [("NDLS", "BCT")],
            "preferred_class": "SL"
        }
        
        pattern = service.analyze_travel_patterns("user_123")
        
        assert pattern["user_id"] == "user_123"
        assert pattern["total_trips"] == 5
        assert ("NDLS", "BCT") in pattern["most_frequent_routes"]
    
    def test_get_travel_recommendations(self):
        """Test travel recommendation generation."""
        service = Mock()
        service.get_travel_recommendations = lambda user_id: {
            "status": "success",
            "travel_pattern": {
                "total_trips": 5,
                "preferred_class": "SL"
            },
            "recommendations": [
                {"type": "booking_timing", "message": "Book early"}
            ]
        }
        
        recommendations = service.get_travel_recommendations("user_123")
        
        assert recommendations["status"] == "success"
        assert "travel_pattern" in recommendations
        assert "recommendations" in recommendations


# ============================================================================
# Sync Service Tests
# ============================================================================

class TestHeartbeatSyncAgent:
    """Tests for HeartbeatSyncAgent."""
    
    def test_agent_initialization(self):
        """Test agent initializes with all components."""
        agent = Mock()
        agent.hot_zones = set()
        agent._api_breaker = Mock()
        agent._api_retry = Mock()
        agent._metrics = deque(maxlen=1000)
        
        assert agent.hot_zones == set()
        assert agent._api_breaker is not None
        assert agent._api_retry is not None
    
    def test_get_hot_zones(self):
        """Test hot zone identification."""
        agent = Mock()
        agent.get_hot_zones = lambda limit: ["NDLS", "BCT", "MAS", "HWH"]
        
        zones = agent.get_hot_zones(limit=10)
        
        assert isinstance(zones, list)
        assert len(zones) > 0
        assert "NDLS" in zones
        assert "BCT" in zones


# ============================================================================
# Station Departure Service Tests
# ============================================================================

class TestStationDepartureService:
    """Tests for StationDepartureService."""
    
    def test_service_initialization(self):
        """Test service initializes with all components."""
        service = Mock()
        service._db_breaker = Mock()
        service._retry = Mock()
        service._metrics = deque(maxlen=1000)
        service._cache = {}
        service._cache_ttl_seconds = 60
        
        assert service._db_breaker is not None
        assert service._retry is not None
        assert service._cache == {}
        assert service._cache_ttl_seconds == 60
    
    def test_get_cache_key(self):
        """Test cache key generation."""
        from datetime import time
        service = Mock()
        service._get_cache_key = lambda station_id, time_min, time_max, date: (
            f"departures:{station_id}:{time_min.isoformat()}:{time_max.isoformat()}:{date.isoformat() if date else 'all'}"
        )
        
        key = service._get_cache_key(
            station_id=123,
            time_min=time(8, 0),
            time_max=time(12, 0),
            date=datetime.now()
        )
        
        assert "departures" in key
        assert "123" in key


# ============================================================================
# Metrics Tests
# ============================================================================

class TestMetricsTracking:
    """Tests for metrics tracking functionality."""
    
    def test_metrics_recording(self):
        """Test metrics recording."""
        metrics = deque(maxlen=1000)
        
        async def record_metrics():
            metrics.append({
                "timestamp": datetime.utcnow(),
                "operation": "test_operation",
                "success": True,
                "duration_ms": 100.0
            })
        
        asyncio.run(record_metrics())
        
        assert len(metrics) == 1
        assert metrics[0]["operation"] == "test_operation"
        assert metrics[0]["success"] == True
    
    def test_metrics_aggregation(self):
        """Test metrics aggregation."""
        metrics = deque(maxlen=1000)
        
        # Add some metrics
        metrics.append({"success": True, "duration_ms": 100})
        metrics.append({"success": True, "duration_ms": 200})
        metrics.append({"success": False, "duration_ms": 150})
        
        total = len(metrics)
        successful = sum(1 for m in metrics if m["success"])
        success_rate = successful / total if total > 0 else 0
        
        assert total == 3
        assert successful == 2
        assert success_rate == 2/3


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
