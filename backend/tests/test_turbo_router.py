import pytest
from datetime import datetime
from core.route_engine.turbo_router import TurboRouter
from database.session import SessionLocal
from sqlalchemy import text

@pytest.fixture(scope="module")
def setup_turbo_data():
    session = SessionLocal()
    # Ensure station_transit_index has some data for testing
    # Using NDLS and BCT as examples
    # trains_map structure: { "train_no": ["arr_time", "dep_time", "day_mask", "sequence"] }
    # Note: The actual structure in TurboRouter seems to be:
    # (s.trains_map->train_no->>0) as dep_time (for source)
    # (d.trains_map->train_no->>0) as arr_time (for destination)
    # Wait, looking at _search_direct:
    # (s.trains_map->train_no->>0) as dep_time
    # (d.trains_map->train_no->>0) as arr_time
    # This implies index 0 is used for both dep and arr depending on the station context? 
    # Usually it's ["arrival", "departure", "mask", "sequence"]
    
    # Let's verify the actual structure in the DB if possible, or assume based on code.
    # In _search_direct: 
    # (s.trains_map->train_no->>0) as dep_time (from source map)
    # (d.trains_map->train_no->>0) as arr_time (from destination map)
    # In _search_one_transfer:
    # (s.trains_map->t1->>1) as dep1
    # (inter.trains_map->t1->>0) as arr1
    # (inter.trains_map->t2->>1) as dep2
    # (d.trains_map->t2->>0) as arr2
    # So index 0 is ARRIVAL, index 1 is DEPARTURE.
    
    try:
        session.execute(text("DELETE FROM station_transit_index WHERE station_code IN ('TEST_S1', 'TEST_S2', 'TEST_HUB')"))
        session.execute(text("""
            INSERT INTO station_transit_index (station_code, station_name, trains_map) VALUES 
            ('TEST_S1', 'Source', '{"T101": ["00:00", "08:00", 127, 1], "T102": ["00:00", "20:00", 127, 1]}'),
            ('TEST_S2', 'Dest',   '{"T101": ["12:00", "12:10", 127, 10], "T103": ["15:00", "15:10", 127, 10]}'),
            ('TEST_HUB', 'Hub',   '{"T102": ["22:00", "22:10", 127, 5], "T103": ["23:00", "23:10", 127, 1]}')
        """))
        session.commit()
    except Exception as e:
        print(f"Setup error: {e}")
        session.rollback()
    finally:
        session.close()

    yield

    session = SessionLocal()
    session.execute(text("DELETE FROM station_transit_index WHERE station_code IN ('TEST_S1', 'TEST_S2', 'TEST_HUB')"))
    session.commit()
    session.close()

def test_turbo_router_direct(setup_turbo_data):
    router = TurboRouter()
    # Monday is 0, mask 1
    departure_date = datetime(2026, 3, 2, 8, 0) # Monday
    routes = router.find_routes("TEST_S1", "TEST_S2", departure_date)
    
    assert len(routes) >= 1
    assert routes[0]["train_no"] == "T101"
    assert routes[0]["type"] == "direct"

def test_turbo_router_one_transfer(setup_turbo_data):
    router = TurboRouter()
    # Route: TEST_S1 -(T102)-> TEST_HUB -(T103)-> TEST_S2
    # T102 dep S1 20:00, arr HUB 22:00
    # T103 dep HUB 23:00, arr S2 15:00 (next day if seq is higher)
    departure_date = datetime(2026, 3, 2, 8, 0)
    routes = router.find_routes("TEST_S1", "TEST_S2", departure_date)
    
    # T101 is direct. T102->T103 is 1-transfer.
    transfer_routes = [r for r in routes if r["type"] == "1-transfer"]
    assert len(transfer_routes) >= 1
    assert transfer_routes[0]["legs"][0]["train_no"] == "T102"
    assert transfer_routes[0]["legs"][1]["train_no"] == "T103"
    assert transfer_routes[0]["interchange"] == "TEST_HUB"

def test_turbo_router_no_results():
    router = TurboRouter()
    routes = router.find_routes("NONEXISTENT", "S2", datetime.now())
    assert len(routes) == 0
