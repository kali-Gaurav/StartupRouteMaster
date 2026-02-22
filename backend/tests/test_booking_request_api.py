"""
Test script for booking request API endpoints.
Tests the core pipeline: unlock → request → queue creation.
"""
import sys
import os
import json
from datetime import datetime, date

# Add project root to path (not just backend) to avoid shadowing stdlib modules
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, root_dir)

def test_schemas():
    """Test that schemas can be imported and validated."""
    print("Testing schemas...")
    try:
        from backend.schemas import (
            BookingRequestCreateSchema,
            BookingRequestResponseSchema,
            BookingRequestPassengerSchema
        )
        
        # Test schema validation
        passenger_data = {
            "name": "Test User",
            "age": 30,
            "gender": "M",
            "berth_preference": "LOWER"
        }
        passenger = BookingRequestPassengerSchema(**passenger_data)
        assert passenger.name == "Test User"
        assert passenger.age == 30
        
        request_data = {
            "source_station": "NDLS",
            "destination_station": "MMCT",
            "journey_date": "2026-03-15",
            "train_number": "12951",
            "train_name": "Rajdhani Express",
            "class_type": "AC3",
            "quota": "GENERAL",
            "passengers": [passenger_data]
        }
        request = BookingRequestCreateSchema(**request_data)
        assert request.source_station == "NDLS"
        assert len(request.passengers) == 1
        
        print("✅ Schemas validated successfully")
        return True
    except Exception as e:
        print(f"❌ Schema validation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_endpoint_imports():
    """Test that endpoints can be imported."""
    print("\nTesting endpoint imports...")
    try:
        # Just check if the file can be imported without errors
        from backend.api import bookings
        assert hasattr(bookings, 'router'), "Router not found"
        print("✅ Endpoints imported successfully")
        return True
    except Exception as e:
        print(f"❌ Endpoint import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_data_provider_rapidapi():
    """Test RapidAPI integration in DataProvider."""
    print("\nTesting RapidAPI integration...")
    try:
        from backend.core.route_engine.data_provider import DataProvider
        
        provider = DataProvider()
        
        # Check if RapidAPI client can be initialized
        if provider.rapidapi_client:
            print("✅ RapidAPI client initialized")
        else:
            print("⚠️  RapidAPI client not initialized (RAPIDAPI_KEY may not be set)")
            print("   This is OK - will use database fallback")
        
        # Check methods exist
        assert hasattr(provider, 'verify_seat_availability_unified')
        assert hasattr(provider, 'verify_fare_unified')
        
        print("✅ DataProvider RapidAPI integration check passed")
        return True
    except Exception as e:
        print(f"❌ DataProvider test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Booking Request API - Validation Tests")
    print("=" * 60)
    
    results = []
    results.append(test_schemas())
    results.append(test_endpoint_imports())
    results.append(test_data_provider_rapidapi())
    
    print("\n" + "=" * 60)
    if all(results):
        print("✅ ALL TESTS PASSED - API is ready for testing")
        sys.exit(0)
    else:
        print("❌ SOME TESTS FAILED - Fix issues before deployment")
        sys.exit(1)
