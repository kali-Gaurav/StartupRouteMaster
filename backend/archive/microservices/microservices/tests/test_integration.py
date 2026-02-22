"""
Microservices Integration Tests
Tests gRPC microservices: Route, Inventory, and Booking services
"""

import asyncio
import pytest
from datetime import datetime, timedelta
import sys
import os

# Add paths
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

# Import gRPC client manager
from backend.microservices.common.grpc_clients import grpc_clients

# Import proto messages (proto src dirs are added to sys.path by grpc_clients)
import route_pb2
import inventory_pb2
import booking_pb2
from google.protobuf.timestamp_pb2 import Timestamp


@pytest.fixture
async def route_client():
    """Get route service client"""
    client = grpc_clients.get_route_client(host='localhost', port=50051, timeout_seconds=30)
    yield client


@pytest.fixture
async def inventory_client():
    """Get inventory service client"""
    client = grpc_clients.get_inventory_client(host='localhost', port=50052, timeout_seconds=30)
    yield client


@pytest.fixture
async def booking_client():
    """Get booking service client"""
    client = grpc_clients.get_booking_client(host='localhost', port=50053, timeout_seconds=60)
    yield client


# ==================== ROUTE SERVICE TESTS ====================

@pytest.mark.asyncio
async def test_find_routes_basic(route_client):
    """Test basic route finding"""
    # Create departure timestamp for tomorrow
    tomorrow = datetime.now() + timedelta(days=1)
    dep_time = Timestamp()
    dep_time.FromDatetime(tomorrow)
    
    request = route_pb2.RouteRequest(
        from_station_id="1",
        to_station_id="10",
        departure_date=dep_time,
        max_transfers=3,
        num_passengers=1
    )
    
    response = await route_client.FindRoutes(request)
    
    assert response is not None
    assert response.search_id
    assert isinstance(response.latency_ms, float)
    print(f"✓ Found {len(response.routes)} routes in {response.latency_ms}ms")


@pytest.mark.asyncio
async def test_find_routes_multiple_alternatives(route_client):
    """Test finding multiple alternative routes"""
    tomorrow = datetime.now() + timedelta(days=3)
    dep_time = Timestamp()
    dep_time.FromDatetime(tomorrow)
    
    request = route_pb2.RouteRequest(
        from_station_id="1",
        to_station_id="5",
        departure_date=dep_time,
        max_transfers=2,
        num_passengers=2,
        num_alternatives=5
    )
    
    response = await route_client.FindRoutes(request)
    
    assert response.total_results <= 5
    if response.routes:
        for route in response.routes:
            assert route.route_id
            assert route.legs
            assert route.total_duration_mins > 0
            assert route.total_price >= 0
            print(f"  Route: {route.total_duration_mins}min, ₹{route.total_price}, "
                  f"Reliability: {route.reliability_score*100:.1f}%")


@pytest.mark.asyncio
async def test_update_graph_delay(route_client):
    """Test graph mutation for delays"""
    request = route_pb2.GraphUpdateRequest(
        train_number="12345",
        trip_id="1",
        status="delayed",
        delay_minutes=15,
        current_station_id="3"
    )
    
    response = await route_client.UpdateGraph(request)
    
    assert response.success is True
    print(f"✓ Graph updated: {response.message}")


@pytest.mark.asyncio
async def test_get_station_reachability(route_client):
    """Test station reachability calculation"""
    now = Timestamp()
    now.FromDatetime(datetime.now())
    
    request = route_pb2.ReachabilityRequest(
        source_station_id="1",
        start_time=now,
        max_duration_mins=300,
        max_transfers=2
    )
    
    response = await route_client.GetStationReachability(request)
    
    assert response.source_station_id == "1"
    if response.reachable_stations:
        print(f"✓ {len(response.reachable_stations)} reachable stations found")


# ==================== INVENTORY SERVICE TESTS ====================

@pytest.mark.asyncio
async def test_check_availability(inventory_client):
    """Test seat availability check"""
    tomorrow = datetime.now() + timedelta(days=1)
    travel_date = Timestamp()
    travel_date.FromDatetime(tomorrow)
    
    request = inventory_pb2.AvailabilityRequest(
        train_id="12345",
        from_stop_id="1",
        to_stop_id="5",
        travel_date=travel_date,
        quota_type="general",
        num_passengers=2
    )
    
    response = await inventory_client.CheckAvailability(request)
    
    assert response.train_id == "12345"
    assert response.total_seats > 0
    print(f"✓ Availability check: {response.available_count}/{response.total_seats} "
          f"seats available, Status: {response.status}")


@pytest.mark.asyncio
async def test_lock_seats(inventory_client):
    """Test seat locking"""
    tomorrow = datetime.now() + timedelta(days=1)
    travel_date = Timestamp()
    travel_date.FromDatetime(tomorrow)
    
    request = inventory_pb2.LockRequest(
        train_id="12345",
        from_stop_id="1",
        to_stop_id="5",
        travel_date=travel_date,
        count=2,
        user_id="user_123",
        ttl_seconds=600
    )
    
    response = await inventory_client.LockSeats(request)
    
    assert response.success is True
    assert response.lock_id
    print(f"✓ Seats locked: {response.lock_id}, expires in {response.expires_in_seconds}s")
    
    return response.lock_id


@pytest.mark.asyncio
async def test_lock_release(inventory_client):
    """Test seat lock release"""
    # First lock
    tomorrow = datetime.now() + timedelta(days=1)
    travel_date = Timestamp()
    travel_date.FromDatetime(tomorrow)
    
    lock_request = inventory_pb2.LockRequest(
        train_id="12345",
        from_stop_id="1",
        to_stop_id="5",
        travel_date=travel_date,
        count=1,
        user_id="user_456",
        ttl_seconds=300
    )
    
    lock_response = await inventory_client.LockSeats(lock_request)
    lock_id = lock_response.lock_id
    
    # Then release
    release_request = inventory_pb2.ReleaseRequest(lock_id=lock_id)
    release_response = await inventory_client.ReleaseSeats(release_request)
    
    assert release_response.success is True
    print(f"✓ Lock released: {lock_id}")


@pytest.mark.asyncio
async def test_allocate_seats(inventory_client):
    """Test seat allocation"""
    request = inventory_pb2.AllocationRequest(
        pnr="PNR123456789",
        num_passengers=2,
        preferences=["LB", "UB"]
    )
    
    response = await inventory_client.AllocateSeats(request)
    
    if response.success:
        print(f"✓ Seats allocated: {response.seat_numbers}, Coach: {response.coach}")
    else:
        print(f"⚠ Allocation status: {response.status}, Message: {response.message}")


# ==================== BOOKING SERVICE TESTS ====================

@pytest.mark.asyncio
async def test_initiate_booking(booking_client):
    """Test booking initiation"""
    tomorrow = datetime.now() + timedelta(days=5)
    travel_date = Timestamp()
    travel_date.FromDatetime(tomorrow)
    
    passenger = booking_pb2.Passenger(
        name="John Doe",
        age=30,
        gender="M",
        berth_preference="LB"
    )
    
    request = booking_pb2.BookingRequest(
        user_id="user_123",
        trip_id="1",
        from_stop_id="1",
        to_stop_id="5",
        travel_date=travel_date,
        quota_type="general",
        passengers=[passenger],
        payment_method="razorpay",
        total_amount=500.0
    )
    
    response = await booking_client.InitiateBooking(request)
    
    print(f"✓ Booking initiated:")
    print(f"  PNR: {response.pnr}")
    print(f"  Status: {response.status}")
    print(f"  Amount: ₹{response.total_amount}")
    
    return response.pnr if response.success else None


@pytest.mark.asyncio
async def test_get_booking_status(booking_client):
    """Test booking status retrieval"""
    request = booking_pb2.StatusRequest(pnr="PNR123456789")
    
    response = await booking_client.GetBookingStatus(request)
    
    print(f"✓ Booking status: {response.status}")
    print(f"  Payment: {response.payment_status}")
    if response.seat_numbers:
        print(f"  Seats: {response.seat_numbers}")


@pytest.mark.asyncio
async def test_cancel_booking(booking_client):
    """Test booking cancellation"""
    request = booking_pb2.CancelRequest(
        pnr="PNR123456789",
        reason="Change of plans"
    )
    
    response = await booking_client.CancelBooking(request)
    
    if response.success:
        print(f"✓ Booking cancelled:")
        print(f"  Refund: ₹{response.refund_amount}")
        print(f"  Cancellation Charge: ₹{response.cancellation_charge}")
    else:
        print(f"⚠ Cancellation failed: {response.message}")


# ==================== END-TO-END INTEGRATION TEST ====================

@pytest.mark.asyncio
async def test_end_to_end_booking_flow(route_client, inventory_client, booking_client):
    """Test complete booking workflow"""
    print("\n" + "="*60)
    print("END-TO-END BOOKING WORKFLOW TEST")
    print("="*60)
    
    # Step 1: Search for routes
    print("\n1. Searching for routes...")
    tomorrow = datetime.now() + timedelta(days=7)
    dep_time = Timestamp()
    dep_time.FromDatetime(tomorrow)
    
    route_request = route_pb2.RouteRequest(
        from_station_id="1",
        to_station_id="10",
        departure_date=dep_time,
        max_transfers=2,
        num_passengers=1,
        num_alternatives=3
    )
    
    routes_response = await route_client.FindRoutes(route_request)
    assert len(routes_response.routes) > 0
    selected_route = routes_response.routes[0]
    print(f"   Selected route: {selected_route.route_id}, Duration: {selected_route.total_duration_mins}min")
    
    # Step 2: Check availability
    print("\n2. Checking seat availability...")
    first_leg = selected_route.legs[0]
    avail_request = inventory_pb2.AvailabilityRequest(
        train_id=first_leg.trip_id,
        from_stop_id=first_leg.from_station_id,
        to_stop_id=first_leg.to_station_id,
        travel_date=dep_time,
        quota_type="general",
        num_passengers=1
    )
    
    avail_response = await inventory_client.CheckAvailability(avail_request)
    assert avail_response.available_count > 0
    print(f"   Available seats: {avail_response.available_count}")
    
    # Step 3: Lock seats
    print("\n3. Locking seats...")
    lock_request = inventory_pb2.LockRequest(
        train_id=first_leg.trip_id,
        from_stop_id=first_leg.from_station_id,
        to_stop_id=first_leg.to_station_id,
        travel_date=dep_time,
        count=1,
        user_id="test_user_e2e",
        ttl_seconds=900
    )
    
    lock_response = await inventory_client.LockSeats(lock_request)
    assert lock_response.success
    print(f"   Lock acquired: {lock_response.lock_id}")
    
    # Step 4: Create booking
    print("\n4. Creating booking...")
    passenger = booking_pb2.Passenger(
        name="Test Passenger",
        age=25,
        gender="M",
        berth_preference="LB"
    )
    
    booking_request = booking_pb2.BookingRequest(
        user_id="test_user_e2e",
        trip_id=first_leg.trip_id,
        from_stop_id=first_leg.from_station_id,
        to_stop_id=first_leg.to_station_id,
        travel_date=dep_time,
        quota_type="general",
        passengers=[passenger],
        payment_method="razorpay",
        total_amount=selected_route.total_price
    )
    
    booking_response = await booking_client.InitiateBooking(booking_request)
    assert booking_response.success
    pnr = booking_response.pnr
    print(f"   PNR: {pnr}, Status: {booking_response.status}")
    
    # Step 5: Allocate seats
    print("\n5. Allocating seats...")
    alloc_request = inventory_pb2.AllocationRequest(
        pnr=pnr,
        num_passengers=1,
        preferences=["LB"]
    )
    
    alloc_response = await inventory_client.AllocateSeats(alloc_request)
    if alloc_response.success:
        print(f"   Seats: {alloc_response.seat_numbers}, Coach: {alloc_response.coach}")
    
    # Step 6: Get booking status
    print("\n6. Checking booking status...")
    status_request = booking_pb2.StatusRequest(pnr=pnr)
    status_response = await booking_client.GetBookingStatus(status_request)
    print(f"   Status: {status_response.status}, Payment: {status_response.payment_status}")
    
    print("\n" + "="*60)
    print("✓ END-TO-END TEST COMPLETED SUCCESSFULLY")
    print("="*60)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
