#!/usr/bin/env python3
"""
Test script for Multi-Modal Route Engine
Reproduces IRCTC-like system model for multi-mode transport.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.multi_modal_route_engine import MultiModalRouteEngine
from backend.database import get_db
from datetime import date

def test_multi_modal_engine():
    """Test the multi-modal route engine."""
    print("Testing Multi-Modal Route Engine...")

    # Initialize engine
    engine = MultiModalRouteEngine()

    # Get DB session
    db = next(get_db())

    try:
        # Load data
        engine.load_graph_from_db(db)
        print("Data loaded successfully.")

        # Test single journey (assuming stop IDs exist)
        # For demo, use dummy IDs or find real ones
        stops = db.query(db.models.Stop).limit(2).all()
        if len(stops) >= 2:
            source_id = stops[0].id
            dest_id = stops[1].id
            travel_date = date.today()

            journeys = engine.search_single_journey(source_id, dest_id, travel_date)
            print(f"Found {len(journeys)} journeys from {stops[0].name} to {stops[1].name}")

            for j in journeys[:1]:  # Show first journey
                print(f"Journey: {j}")

        # Test fare calculation
        if journeys:
            fare = engine.calculate_fare_with_concessions(journeys[0], 'senior')
            print(f"Fare with senior concession: {fare}")

        print("Test completed successfully.")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_multi_modal_engine()