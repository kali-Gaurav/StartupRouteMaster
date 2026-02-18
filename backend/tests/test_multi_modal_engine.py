import pytest
import asyncio
from datetime import date, datetime
from sqlalchemy.orm import Session
from unittest.mock import Mock, patch

from backend.services.multi_modal_route_engine import MultiModalRouteEngine
from backend.models import Stop, Route, Trip, StopTime, Transfer, Calendar
from backend.database import get_db


class TestMultiModalRouteEngine:
    """Test suite for MultiModalRouteEngine"""

    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)

    @pytest.fixture
    def engine(self, mock_db):
        """Create engine instance with mock data"""
        engine = MultiModalRouteEngine()

        # Mock stops
        engine.stops_map = {
            1: {'stop_id': 'S1', 'name': 'Central Station', 'city': 'Mumbai', 'lat': 19.0760, 'lon': 72.8777},
            2: {'stop_id': 'S2', 'name': 'Airport', 'city': 'Mumbai', 'lat': 19.0896, 'lon': 72.8656},
            3: {'stop_id': 'S3', 'name': 'Delhi Station', 'city': 'Delhi', 'lat': 28.6139, 'lon': 77.2090},
            4: {'stop_id': 'S4', 'name': 'Bus Terminal', 'city': 'Delhi', 'lat': 28.6139, 'lon': 77.2090}
        }

        # Mock routes
        engine.routes_map = {
            1: {'route_id': 'R1', 'agency_id': 1, 'short_name': 'Express', 'long_name': 'Mumbai-Delhi Express', 'route_type': 2},  # Rail
            2: {'route_id': 'R2', 'agency_id': 1, 'short_name': 'Metro', 'long_name': 'Mumbai Metro', 'route_type': 1},  # Subway
            3: {'route_id': 'R3', 'agency_id': 2, 'short_name': 'Bus', 'long_name': 'Mumbai-Delhi Bus', 'route_type': 3}  # Bus
        }

        # Mock trips
        engine.trips_map = {
            1: {'trip_id': 'T1', 'route_id': 1, 'service_id': 1, 'headsign': 'Delhi', 'direction_id': 0},
            2: {'trip_id': 'T2', 'route_id': 2, 'service_id': 1, 'headsign': 'Airport', 'direction_id': 0},
            3: {'trip_id': 'T3', 'route_id': 3, 'service_id': 1, 'headsign': 'Delhi', 'direction_id': 0}
        }

        # Mock stop times
        engine.stop_times_map = {
            1: [  # Train trip
                {'stop_id': 1, 'arrival_time': '06:00:00', 'departure_time': '06:05:00', 'stop_sequence': 1, 'cost': 0.0},
                {'stop_id': 3, 'arrival_time': '14:00:00', 'departure_time': '14:05:00', 'stop_sequence': 2, 'cost': 500.0}
            ],
            2: [  # Metro trip
                {'stop_id': 1, 'arrival_time': '07:00:00', 'departure_time': '07:02:00', 'stop_sequence': 1, 'cost': 0.0},
                {'stop_id': 2, 'arrival_time': '07:30:00', 'departure_time': '07:32:00', 'stop_sequence': 2, 'cost': 50.0}
            ],
            3: [  # Bus trip
                {'stop_id': 1, 'arrival_time': '08:00:00', 'departure_time': '08:05:00', 'stop_sequence': 1, 'cost': 0.0},
                {'stop_id': 4, 'arrival_time': '16:00:00', 'departure_time': '16:05:00', 'stop_sequence': 2, 'cost': 300.0}
            ]
        }

        # Mock transfers
        engine.transfers_map = {
            2: [{'to_stop_id': 1, 'transfer_type': 0, 'min_transfer_time': 300}],  # 5 min transfer
            4: [{'to_stop_id': 3, 'transfer_type': 0, 'min_transfer_time': 600}]   # 10 min transfer
        }

        # Mock calendar
        engine.calendar_map = {
            1: {
                'service_id': 'S1',
                'monday': True, 'tuesday': True, 'wednesday': True,
                'thursday': True, 'friday': True, 'saturday': True, 'sunday': True,
                'start_date': date.today() - timedelta(days=365),
                'end_date': date.today() + timedelta(days=365)
            }
        }

        engine._is_loaded = True
        return engine

    def test_single_journey_search(self, engine):
        """Test single journey search"""
        travel_date = date.today() + timedelta(days=30)
        journeys = engine.search_single_journey(1, 3, travel_date)

        assert len(journeys) > 0
        journey = journeys[0]

        assert journey['source'] == 'Central Station'
        assert journey['destination'] == 'Delhi Station'
        assert journey['total_cost'] > 0
        assert len(journey['segments']) > 0
        assert journey['modes'] == ['rail']

    def test_connecting_journeys(self, engine):
        """Test connecting journey search"""
        # First get individual journeys
        travel_date = date.today() + timedelta(days=30)
        individual_journeys = engine.search_single_journey(1, 3, travel_date)

        # Search for connecting options
        connecting = engine.search_connecting_journeys(individual_journeys)

        # Should find combinations if multiple journeys exist
        assert isinstance(connecting, list)

    # walk-connector test removed by request (walk transfers are not part of core deployment).

    def test_transfer_min_time_validation(self, engine):
        """Ensure explicit transfer min_transfer_time is enforced"""
        # Make explicit transfer very large (2 hours) so short layover is invalid
        engine.transfers_map[2] = [{'to_stop_id': 1, 'transfer_type': 0, 'min_transfer_time': 7200}]

        # Journey 1 arrives at 'Airport' (stop 2) at 07:00
        j1 = {
            'source': 'Central Station',
            'destination': 'Airport',
            'departure_date': '2025-12-25',
            'segments': [{'departure_time': datetime.strptime('06:00:00', '%H:%M:%S').time(), 'arrival_time': datetime.strptime('07:00:00', '%H:%M:%S').time(), 'duration_minutes': 60}],
            'total_cost': 100.0,
            'total_duration_minutes': 60
        }
        # Journey 2 departs from 'Central Station' (stop 1) at 07:30 -> 30 min layover (insufficient)
        j2 = {
            'source': 'Central Station',
            'destination': 'Delhi Station',
            'departure_date': '2025-12-25',
            'segments': [{'departure_time': datetime.strptime('07:30:00', '%H:%M:%S').time(), 'arrival_time': datetime.strptime('14:00:00', '%H:%M:%S').time(), 'duration_minutes': 390}],
            'total_cost': 1500.0,
            'total_duration_minutes': 390
        }

        results = engine.search_connecting_journeys([j1, j2], min_layover=5, max_layover=180)
        # Since transfer min time required is 120 minutes, the 30 minute layover should be rejected
        assert results == []

    def test_circular_journey(self, engine):
        """Test circular (round-trip) journey"""
        travel_date = date(2025, 12, 25)
        return_date = date(2025, 12, 30)

        outward_journeys = engine.search_single_journey(1, 3, travel_date)
        assert len(outward_journeys) > 0

        circular_journeys = engine.search_circular_journey(outward_journeys[0], return_date)

        assert isinstance(circular_journeys, list)
        if circular_journeys:
            circular = circular_journeys[0]
            assert 'outward_segments' in circular
            assert 'return_segments' in circular
            assert 'telescopic_discount' in circular

    def test_multi_city_journey(self, engine):
        """Test multi-city journey"""
        cities = ['Mumbai', 'Delhi']
        travel_dates = [date(2025, 12, 25), date(2025, 12, 26)]

        multi_city = engine.search_multi_city_journey(cities, travel_dates)

        assert isinstance(multi_city, list)
        if multi_city:
            journey = multi_city[0]
            assert journey['cities'] == cities
            assert len(journey['segments']) > 0

    def test_fare_calculation_with_concessions(self, engine):
        """Test fare calculation with different passenger types and concessions"""
        journey = {
            'segments': [
                {'mode': 'rail', 'cost': 500.0},
                {'mode': 'bus', 'cost': 300.0}
            ],
            'total_cost': 800.0
        }

        # Adult fare
        fare_info = engine.calculate_fare_with_concessions(journey, 'adult', [])
        assert fare_info['adjusted_fare'] > 800.0  # Rail multiplier > 1

        # Child fare
        child_fare = engine.calculate_fare_with_concessions(journey, 'child', [])
        assert child_fare['adjusted_fare'] == fare_info['adjusted_fare'] * 0.5

        # With concessions
        concession_fare = engine.calculate_fare_with_concessions(journey, 'adult', ['defence'])
        assert concession_fare['adjusted_fare'] < fare_info['adjusted_fare']

    def test_real_time_delays(self, engine, mock_db):
        """Test real-time delay simulation"""
        journey = {
            'departure_date': '2025-12-25',
            'segments': [
                {'departure_time': '06:00:00', 'arrival_time': '14:00:00', 'duration_minutes': 480}
            ]
        }

        # Mock disruptions
        mock_disruption = Mock()
        mock_disruption.disruption_type = 'delay'
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_disruption]

        delayed_journey = engine.simulate_real_time_delays(journey, mock_db)

        assert 'total_delay_minutes' in delayed_journey
        assert 'otp_confidence' in delayed_journey
        assert delayed_journey['otp_confidence'] < 100

    def test_pnr_generation(self, engine):
        """Test PNR reference generation"""
        journey = {}
        user_id = "user123"

        pnr = engine.generate_pnr_reference(journey, user_id)

        assert pnr.startswith('PNR')
        assert len(pnr) == 13  # PNR + 10 hex chars
        assert journey['pnr_reference'] == pnr

    def test_mode_specific_pricing(self, engine):
        """Test that different modes have different pricing"""
        journey = {
            'segments': [
                {'mode': 'tram', 'cost': 100.0},
                {'mode': 'subway', 'cost': 100.0},
                {'mode': 'rail', 'cost': 100.0},
                {'mode': 'bus', 'cost': 100.0}
            ],
            'total_cost': 400.0
        }

        fare_info = engine.calculate_fare_with_concessions(journey, 'adult', [])

        # Rail should be most expensive, tram/bus cheapest
        mode_breakdown = fare_info['mode_breakdown']
        assert mode_breakdown['rail'] > mode_breakdown['subway'] > mode_breakdown['tram']
        assert mode_breakdown['bus'] == mode_breakdown['tram']  # Both multiplier 1.0

    def test_service_active_check(self, engine):
        """Test service availability checking"""
        # Service within date range
        active = engine._is_service_active(1, date(2025, 6, 15))
        assert active

        # Service outside date range
        inactive = engine._is_service_active(1, date(2024, 6, 15))
        assert not inactive

    def test_time_conversions(self, engine):
        """Test time conversion utilities"""
        # Test time to minutes
        time_obj = datetime.strptime('14:30:00', '%H:%M:%S').time()
        minutes = engine._time_to_minutes(time_obj)
        assert minutes == 14 * 60 + 30

        # Test minutes to time
        time_back = engine._minutes_to_time(minutes)
        assert time_back.hour == 14
        assert time_back.minute == 30


class TestIRCTCLikeFeatures:
    """Test IRCTC-inspired features"""

    def test_pnr_linking(self, engine):
        """Test PNR-like journey linking"""
        journey1 = {'segments': []}
        journey2 = {'segments': []}

        pnr1 = engine.generate_pnr_reference(journey1, "user1")
        pnr2 = engine.generate_pnr_reference(journey2, "user1")

        assert pnr1 != pnr2
        assert journey1['pnr_reference'] == pnr1
        assert journey2['pnr_reference'] == pnr2

    def test_connecting_journeys_pnr(self, engine):
        """Test connecting journeys maintain separate PNRs"""
        j1 = {'source': 'A', 'destination': 'B', 'segments': []}
        j2 = {'source': 'B', 'destination': 'C', 'segments': []}

        combined = engine._combine_journeys(j1, j2, 30)

        assert 'pnr_references' in combined
        assert len(combined['pnr_references']) == 2

    def test_circular_fare_discount(self, engine):
        """Test telescopic fare for circular journeys"""
        outward = {
            'segments': [{'mode': 'rail', 'cost': 500.0}],
            'total_cost': 500.0,
            'total_duration_minutes': 480
        }
        return_journey = {
            'segments': [{'mode': 'rail', 'cost': 500.0}],
            'total_cost': 500.0,
            'total_duration_minutes': 480
        }

        circular = engine._create_circular_journey(outward, return_journey, 1440)  # 1 day layover

        assert circular['base_cost'] == 1000.0
        assert circular['total_cost'] < 1000.0  # Should have discount
        assert 'telescopic_discount' in circular

    def test_multi_city_booking(self, engine):
        """Test multi-city booking up to 3 cities"""
        # Should work with 2 cities
        cities_2 = ['Mumbai', 'Delhi']
        dates_2 = [date(2025, 12, 25), date(2025, 12, 26)]
        result_2 = engine.search_multi_city_journey(cities_2, dates_2)
        assert isinstance(result_2, list)

        # Should work with 3 cities
        cities_3 = ['Mumbai', 'Delhi', 'Kolkata']
        dates_3 = [date(2025, 12, 25), date(2025, 12, 26), date(2025, 12, 27)]
        result_3 = engine.search_multi_city_journey(cities_3, dates_3)
        assert isinstance(result_3, list)

        # Should reject more than 3 cities
        cities_4 = ['Mumbai', 'Delhi', 'Kolkata', 'Chennai']
        dates_4 = [date(2025, 12, 25), date(2025, 12, 26), date(2025, 12, 27), date(2025, 12, 28)]
        result_4 = engine.search_multi_city_journey(cities_4, dates_4)
        assert result_4 == []  # Should return empty list


if __name__ == "__main__":
    # Run basic functionality test
    print("Testing MultiModalRouteEngine...")

    engine = MultiModalRouteEngine()

    # Mock minimal data for testing
    engine.stops_map = {
        1: {'stop_id': 'MUM', 'name': 'Mumbai Central', 'city': 'Mumbai'},
        2: {'stop_id': 'DEL', 'name': 'Delhi Station', 'city': 'Delhi'}
    }
    engine.routes_map = {1: {'route_id': 'R1', 'route_type': 2, 'long_name': 'Rajdhani Express'}}
    engine.trips_map = {1: {'trip_id': 'T1', 'route_id': 1, 'service_id': 1}}
    engine.stop_times_map = {
        1: [
            {'stop_id': 1, 'arrival_time': '22:00:00', 'departure_time': '22:05:00', 'stop_sequence': 1, 'cost': 0.0},
            {'stop_id': 2, 'arrival_time': '10:00:00', 'departure_time': '10:05:00', 'stop_sequence': 2, 'cost': 2500.0}
        ]
    }
    engine.calendar_map = {1: {'start_date': date(2025, 1, 1), 'end_date': date(2025, 12, 31), **{day: True for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']}}}
    engine._is_loaded = True

    # Test single journey
    journeys = engine.search_single_journey(1, 2, date(2025, 12, 25))
    print(f"Found {len(journeys)} journeys")

    if journeys:
        journey = journeys[0]
        print(f"Journey: {journey['source']} -> {journey['destination']}")
        print(f"Duration: {journey['total_duration_minutes']} minutes")
        print(f"Cost: ₹{journey['total_cost']}")
        print(f"Modes: {journey['modes']}")

        # Test fare calculation
        fare_info = engine.calculate_fare_with_concessions(journey, 'adult', [])
        print(f"Adult fare: ₹{fare_info['adjusted_fare']}")

        child_fare = engine.calculate_fare_with_concessions(journey, 'child', [])
        print(f"Child fare: ₹{child_fare['adjusted_fare']}")

        # Test PNR generation
        pnr = engine.generate_pnr_reference(journey, "test_user")
        print(f"PNR: {pnr}")

    print("Basic functionality test completed!")