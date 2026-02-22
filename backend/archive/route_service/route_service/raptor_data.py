import logging
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
from datetime import datetime, time, date, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from backend.models import Stop, Route, Trip, StopTime, Calendar, Agency
from .db_utils import get_stop_by_id_cached # Leverage caching for stops

logger = logging.getLogger(__name__)

class NetworkDataLoader:
    """
    Loads and provides the transit network data for the RAPTOR algorithm.
    This class is responsible for converting GTFS-inspired database models
    into an in-memory representation suitable for route search.
    """

    def __init__(self, db: Session, redis_client=None):
        self.db = db
        self.redis_client = redis_client
        self.stops: Dict[int, Stop] = {} # Map Stop.id (PK) to Stop object
        self.routes: Dict[int, Route] = {} # Map Route.id (PK) to Route object
        self.trips_by_route_id: Dict[int, List[Trip]] = defaultdict(list)
        self.stop_times_by_trip_id: Dict[int, List[StopTime]] = defaultdict(list)
        self.stop_times_by_stop_pk_id: Dict[int, List[StopTime]] = defaultdict(list) # For faster lookup by Stop.id (PK)

        self._load_network_data()

    def _load_network_data(self):
        """
        Loads all relevant stops, routes, trips, stop_times and calendars
        from the database into memory.
        """
        logger.info("Loading network data from database...")

        # Load Stops
        all_stops = self.db.query(Stop).all()
        for stop in all_stops:
            self.stops[stop.id] = stop
        logger.info(f"Loaded {len(self.stops)} stops.")

        # Load Routes
        all_routes = self.db.query(Route).all()
        for route in all_routes:
            self.routes[route.id] = route
        logger.info(f"Loaded {len(self.routes)} routes.")

        # Load Trips and StopTimes
        all_trips = self.db.query(Trip).all()
        for trip in all_trips:
            self.trips_by_route_id[trip.route_id].append(trip)
            # Fetch and sort stop_times by sequence for each trip
            stop_times_for_trip = self.db.query(StopTime).filter(StopTime.trip_id == trip.id).order_by(StopTime.stop_sequence).all()
            self.stop_times_by_trip_id[trip.id] = stop_times_for_trip
            for st in stop_times_for_trip:
                self.stop_times_by_stop_pk_id[st.stop_id].append(st) # stop_id here is the FK to Stop.id (PK)
        logger.info(f"Loaded {len(all_trips)} trips and their stop times.")

        logger.info("Network data loading complete.")

    def get_stop(self, stop_pk_id: int) -> Optional[Stop]:
        """Get a stop by its internal primary key ID."""
        return self.stops.get(stop_pk_id)

    def get_stop_by_gtfs_id(self, gtfs_stop_id: str) -> Optional[Stop]:
        """Get a stop by its GTFS stop_id string."""
        # This can be optimized with a separate dictionary if performance is critical for this lookup
        for stop_obj in self.stops.values():
            if stop_obj.stop_id == gtfs_stop_id:
                return stop_obj
        return None

    def get_route(self, route_pk_id: int) -> Optional[Route]:
        """Get a route by its internal primary key ID."""
        return self.routes.get(route_pk_id)

    def get_trips_for_route(self, route_pk_id: int) -> List[Trip]:
        """Get all trips for a given route."""
        return self.trips_by_route_id.get(route_pk_id, [])

    def get_stop_times_for_trip(self, trip_pk_id: int) -> List[StopTime]:
        """Get all stop times for a given trip, ordered by sequence."""
        return self.stop_times_by_trip_id.get(trip_pk_id, [])

    def get_stop_times_at_stop(self, stop_pk_id: int) -> List[StopTime]:
        """Get all stop times that occur at a given stop, regardless of trip."""
        return self.stop_times_by_stop_pk_id.get(stop_pk_id, [])

    def get_trips_departing_from_stop_after(self, stop_pk_id: int, departure_time: time, current_date: date) -> List[Tuple[Trip, StopTime]]:
        """
        Finds all trips that depart from the given stop_pk_id after
        the specified departure_time on the current_date, considering calendar.
        Returns a list of (Trip, StopTime) tuples.
        """
        relevant_trips_info = []
        for st in self.stop_times_by_stop_pk_id.get(stop_pk_id, []):
            if st.departure_time is None:
                continue # Skip if no departure time specified for this stop_time

            if st.departure_time >= departure_time:
                trip = self.get_trip_by_pk_id(st.trip_id) # Fetch trip from in-memory cache
                if not trip:
                    continue 

                # Check Calendar for service availability on current_date
                # Assuming Calendar is fetched or cached by Trip.service_id as needed
                calendar = self.db.query(Calendar).filter(Calendar.id == trip.service_id).first()
                if calendar and current_date >= calendar.start_date and current_date <= calendar.end_date:
                    day_of_week_attr = current_date.strftime('%A').lower() # 'monday', 'tuesday', etc.
                    if getattr(calendar, day_of_week_attr, False):
                        relevant_trips_info.append((trip, st))
        
        relevant_trips_info.sort(key=lambda x: x[1].departure_time)
        return relevant_trips_info
    
    def get_trip_by_pk_id(self, trip_pk_id: int) -> Optional[Trip]:
        """Helper to get a trip by its primary key ID from loaded data."""
        for trips_list in self.trips_by_route_id.values():
            for trip in trips_list:
                if trip.id == trip_pk_id:
                    return trip
        return None