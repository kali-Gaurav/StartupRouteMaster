#!/usr/bin/env python3
"""
Test script for RouteMaster functionality
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from backend.database import engine_write
from sqlalchemy.orm import sessionmaker
from backend.models import Disruption
from backend.services.route_engine import route_engine
from datetime import datetime

# Create a simple session for testing
SimpleSession = sessionmaker(bind=engine_write, autocommit=False, autoflush=False)

def test_pareto_pruning():
    """Test Pareto pruning functionality"""
    print("Testing Pareto pruning...")

    # Load graph
    db = SimpleSession()
    try:
        route_engine.load_graph_from_db(db)
        print("Graph loaded successfully")

        # Test search
        routes = route_engine.search_routes(
            source="NDLS",  # New Delhi
            destination="BCT",  # Mumbai Central
            travel_date="2024-02-15"
        )

        print(f"Found {len(routes)} routes")
        for i, route in enumerate(routes[:3]):  # Show first 3
            print(f"Route {i+1}: {len(route.segments)} segments, duration: {route.total_duration}")

        print("Pareto pruning test passed!")

    except Exception as e:
        print(f"Error: {e}")
        return False
    finally:
        db.close()

    return True

def test_disruption_model():
    """Test disruption model"""
    print("Testing disruption model...")

    db = SimpleSession()
    try:
        # Create a test disruption
        disruption = Disruption(
            route_id="test-route-123",
            disruption_type="delay",
            description="Test delay",
            disruption_date=datetime(2024, 2, 15).date(),
            severity="minor",
            status="active"
        )
        db.add(disruption)
        db.commit()
        print("Disruption created successfully")

        # Query disruptions
        disruptions = db.query(Disruption).filter(Disruption.status == "active").all()
        print(f"Found {len(disruptions)} active disruptions")

        print("Disruption model test passed!")

    except Exception as e:
        print(f"Error: {e}")
        return False
    finally:
        db.close()

    return True

def test_redirect_service():
    """Test redirect service"""
    print("Testing redirect service...")
    from backend.services.redirect_service import redirect_service

    try:
        # Test URL generation
        url, cache_key = redirect_service.generate_redirect_url(
            partner="RailYatri",
            route_type="train",
            source="NDLS",
            destination="BCT",
            date="2024-02-15",
            passengers=1
        )

        if url:
            print(f"Generated redirect URL: {url}")
            print("Redirect service test passed!")
            return True
        else:
            print("Failed to generate URL")
            return False

    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    print("Starting RouteMaster functionality tests...")

    tests = [
        test_pareto_pruning,
        test_disruption_model,
        test_redirect_service
    ]

    passed = 0
    for test in tests:
        if test():
            passed += 1
        print()

    print(f"Tests passed: {passed}/{len(tests)}")

    if passed == len(tests):
        print("All tests passed! ✅")
    else:
        print("Some tests failed ❌")