"""
Test script for booking queue system models.
Run this before applying migration to validate models are correct.
"""
import sys
import os

# Add project root to path (not just backend) to avoid shadowing stdlib modules
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, root_dir)

def test_model_imports():
    """Test that all new models can be imported."""
    print("Testing model imports...")
    try:
        from database.models import (
            BookingRequest,
            BookingRequestPassenger,
            BookingQueue,
            BookingResult,
            Refund,
            ExecutionLog
        )
        print("✅ All models imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Failed to import models: {e}")
        return False

def test_model_relationships():
    """Test that model relationships are properly defined."""
    print("\nTesting model relationships...")
    try:
        from database.models import BookingRequest, BookingQueue, User
        
        # Check if relationships exist
        assert hasattr(BookingRequest, 'queue_entry'), "BookingRequest missing queue_entry relationship"
        assert hasattr(BookingRequest, 'result'), "BookingRequest missing result relationship"
        assert hasattr(BookingRequest, 'refunds'), "BookingRequest missing refunds relationship"
        assert hasattr(BookingRequest, 'execution_logs'), "BookingRequest missing execution_logs relationship"
        assert hasattr(BookingRequest, 'request_passengers'), "BookingRequest missing request_passengers relationship"
        
        assert hasattr(BookingQueue, 'booking_request'), "BookingQueue missing booking_request relationship"
        assert hasattr(BookingQueue, 'executor'), "BookingQueue missing executor relationship"
        
        assert hasattr(User, 'booking_requests'), "User missing booking_requests relationship"
        assert hasattr(User, 'executed_bookings'), "User missing executed_bookings relationship"
        assert hasattr(User, 'processed_refunds'), "User missing processed_refunds relationship"
        
        print("✅ All relationships defined correctly")
        return True
    except AssertionError as e:
        print(f"❌ Relationship check failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Error checking relationships: {e}")
        return False

def test_model_attributes():
    """Test that models have required attributes."""
    print("\nTesting model attributes...")
    try:
        from database.models import BookingRequest
        
        # Check BookingRequest has required columns
        required_attrs = [
            'id', 'user_id', 'source_station', 'destination_station',
            'journey_date', 'train_number', 'status', 'verification_status'
        ]
        
        for attr in required_attrs:
            assert hasattr(BookingRequest, attr), f"BookingRequest missing attribute: {attr}"
        
        print("✅ Model attributes check passed")
        return True
    except AssertionError as e:
        print(f"❌ Attribute check failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Error checking attributes: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Booking Queue System - Model Validation Tests")
    print("=" * 60)
    
    results = []
    results.append(test_model_imports())
    results.append(test_model_relationships())
    results.append(test_model_attributes())
    
    print("\n" + "=" * 60)
    if all(results):
        print("✅ ALL TESTS PASSED - Models are ready for migration")
        sys.exit(0)
    else:
        print("❌ SOME TESTS FAILED - Fix issues before migration")
        sys.exit(1)
