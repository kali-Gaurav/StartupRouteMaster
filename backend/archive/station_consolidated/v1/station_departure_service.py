"""
Station Departure Lookup Service

Provides fast, indexed lookups for train departures from stations.
Implements Phase 1: Time-Series Lookup Engine pattern.

Pattern: Station → Time → Departures
"""

import logging
from datetime import datetime, time, timedelta
from typing import List, Dict, Tuple, Optional
from sqlalchemy import and_, between
from sqlalchemy.orm import Session

from ..database.models import StationDeparture, Stop, Trip, StopTime, Calendar
from ..database.session import SessionLocal

logger = logging.getLogger(__name__)


class StationDepartureService:
    """
    Fast lookup service for station departures.

    Indexes: (station_id, departure_time)
    """

    @staticmethod
    def get_departures_from_station(
        session: Session,
        station_id: int,
        departure_time_min: time,
        departure_time_max: time,
        date: Optional[datetime] = None
    ) -> List[Dict]:
        """
        Get all departures from a station within a time window.

        Args:
            session: Database session
            station_id: Station ID (from stops.id)
            departure_time_min: Earliest departure time (e.g., 08:00)
            departure_time_max: Latest departure time (e.g., 12:00)
            date: Optional date for filtering by operating days

        Returns:
            List of departure records with:
            {
                'station_id': int,
                'trip_id': int,
                'departure_time': time,
                'arrival_time_at_next': time,
                'next_station_id': int,
                'next_station_name': str,
                'train_number': str,
                'distance_to_next': float,
            }
        """
        try:
            query = session.query(StationDeparture).filter(
                and_(
                    StationDeparture.station_id == station_id,
                    StationDeparture.departure_time >= departure_time_min,
                    StationDeparture.departure_time <= departure_time_max
                )
            )

            # Filter by operating days if date provided
            if date:
                day_of_week = date.weekday()  # 0=Monday, 6=Sunday
                operating_day_map = {
                    0: 0,  # Monday
                    1: 1,  # Tuesday
                    2: 2,  # Wednesday
                    3: 3,  # Thursday
                    4: 4,  # Friday
                    5: 5,  # Saturday
                    6: 6,  # Sunday
                }
                day_index = operating_day_map[day_of_week]
                # operating_days is "MTWTFSS" string, e.g., "1111111" for all days
                # This filtering is done in application since SQLite doesn't support substring easily
                results = []
                for dep in query.all():
                    if len(dep.operating_days) > day_index and dep.operating_days[day_index] == '1':
                        results.append(dep)
            else:
                results = query.all()

            # Format results
            departures = []
            for dep in results:
                next_station = session.query(Stop).filter(
                    Stop.id == dep.next_station_id
                ).first() if dep.next_station_id else None

                departures.append({
                    'station_id': dep.station_id,
                    'trip_id': dep.trip_id,
                    'departure_time': dep.departure_time,
                    'arrival_time_at_next': dep.arrival_time_at_next,
                    'next_station_id': dep.next_station_id,
                    'next_station_name': next_station.name if next_station else None,
                    'train_number': dep.train_number,
                    'distance_to_next': dep.distance_to_next,
                })

            logger.info(
                f"Found {len(departures)} departures from station {station_id} "
                f"between {departure_time_min} and {departure_time_max}"
            )

            return departures

        except Exception as e:
            logger.error(f"Error querying station departures: {e}")
            return []

    @staticmethod
    def get_departures_for_day(
        session: Session,
        station_id: int,
        date: datetime
    ) -> List[Dict]:
        """
        Get all departures from a station on a specific date.

        Args:
            session: Database session
            station_id: Station ID
            date: Specific date to query

        Returns:
            List of all departures on that date
        """
        try:
            day_of_week = date.weekday()  # 0=Monday, 6=Sunday
            operating_day_map = {
                0: '0',  # Monday
                1: '1',  # Tuesday
                2: '2',  # Wednesday
                3: '3',  # Thursday
                4: '4',  # Friday
                5: '5',  # Saturday
                6: '6',  # Sunday
            }
            day_char = operating_day_map[day_of_week]

            # Query all departures for station
            all_deps = session.query(StationDeparture).filter(
                StationDeparture.station_id == station_id
            ).all()

            # Filter by operating days
            results = []
            for dep in all_deps:
                if len(dep.operating_days) > int(day_char) and dep.operating_days[int(day_char)] == '1':
                    results.append(dep)

            # Format results
            departures = []
            for dep in results:
                next_station = session.query(Stop).filter(
                    Stop.id == dep.next_station_id
                ).first() if dep.next_station_id else None

                departures.append({
                    'station_id': dep.station_id,
                    'trip_id': dep.trip_id,
                    'departure_time': dep.departure_time,
                    'arrival_time_at_next': dep.arrival_time_at_next,
                    'next_station_id': dep.next_station_id,
                    'next_station_name': next_station.name if next_station else None,
                    'train_number': dep.train_number,
                    'distance_to_next': dep.distance_to_next,
                })

            logger.info(
                f"Found {len(departures)} departures from station {station_id} on {date.date()}"
            )

            return departures

        except Exception as e:
            logger.error(f"Error querying daily departures: {e}")
            return []

    @staticmethod
    def rebuild_station_departures_cache(session: Session) -> bool:
        """
        Rebuild the StationDeparture table from stop_times.

        This is the core population logic used during ETL/migrations.
        """
        try:
            # Delete existing records to rebuild
            session.query(StationDeparture).delete()
            session.commit()
            logger.info("Cleared existing station_departures_indexed records")

            # Query all trips ordered by trip_id and stop_sequence
            trips_with_stops = session.query(
                Trip.id,
                Trip.headsign,
                StopTime.stop_id,
                StopTime.departure_time,
                StopTime.stop_sequence,
                Calendar.monday,
                Calendar.tuesday,
                Calendar.wednesday,
                Calendar.thursday,
                Calendar.friday,
                Calendar.saturday,
                Calendar.sunday,
            ).join(
                StopTime, Trip.id == StopTime.trip_id
            ).join(
                Calendar, Trip.service_id == Calendar.service_id
            ).order_by(
                Trip.id, StopTime.stop_sequence
            ).all()

            # Group by trip_id for easier processing
            trips_dict = {}
            for record in trips_with_stops:
                trip_id = record[0]
                if trip_id not in trips_dict:
                    trips_dict[trip_id] = []
                trips_dict[trip_id].append(record)

            # Create StationDeparture records
            station_departure_records = []
            for trip_id, stops in trips_dict.items():
                train_number = stops[0][1] if stops[0][1] else "N/A"

                # Build operating days string "MTWTFSS"
                operating_days = "".join([
                    str(int(stops[0][5])),  # Monday
                    str(int(stops[0][6])),  # Tuesday
                    str(int(stops[0][7])),  # Wednesday
                    str(int(stops[0][8])),  # Thursday
                    str(int(stops[0][9])),  # Friday
                    str(int(stops[0][10])), # Saturday
                    str(int(stops[0][11])), # Sunday
                ])

                # Create segment for each consecutive stop pair
                for i in range(len(stops) - 1):
                    from_stop = stops[i]
                    to_stop = stops[i + 1]

                    station_departure_records.append(
                        StationDeparture(
                            id=str(uuid.uuid4()),
                            station_id=from_stop[2],  # from_stop_id
                            trip_id=trip_id,
                            departure_time=from_stop[3],  # departure_time
                            arrival_time_at_next=to_stop[3],  # next arrival time (for next stop, it's the departure time too)
                            next_station_id=to_stop[2],  # to_stop_id
                            operating_days=operating_days,
                            train_number=train_number,
                            distance_to_next=None,  # Will be populated from segments table
                        )
                    )

            # Bulk insert
            session.bulk_save_objects(station_departure_records)
            session.commit()

            logger.info(
                f"✓ Rebuilt station_departures_indexed with {len(station_departure_records)} records"
            )
            return True

        except Exception as e:
            session.rollback()
            logger.error(f"✗ Error rebuilding station departures cache: {e}")
            return False

    @staticmethod
    def get_station_stats(session: Session, station_id: int) -> Dict:
        """
        Get statistics about departures from a station.

        Returns:
            {
                'total_departures': int,
                'unique_trains': int,
                'time_range': (min_time, max_time),
                'avg_distance': float,
            }
        """
        try:
            departures = session.query(StationDeparture).filter(
                StationDeparture.station_id == station_id
            ).all()

            if not departures:
                return {
                    'total_departures': 0,
                    'unique_trains': 0,
                    'time_range': (None, None),
                    'avg_distance': 0.0,
                }

            unique_trains = len(set(d.train_number for d in departures))
            times = sorted([d.departure_time for d in departures])
            distances = [d.distance_to_next for d in departures if d.distance_to_next is not None]
            avg_distance = sum(distances) / len(distances) if distances else 0.0

            return {
                'total_departures': len(departures),
                'unique_trains': unique_trains,
                'time_range': (times[0], times[-1]) if times else (None, None),
                'avg_distance': avg_distance,
            }

        except Exception as e:
            logger.error(f"Error computing station stats: {e}")
            return {}


# Module-level convenience functions
def get_departures(
    station_id: int,
    departure_time_min: time,
    departure_time_max: time,
    date: Optional[datetime] = None
) -> List[Dict]:
    """
    Convenience function for getting departures (handles session management).
    """
    session = SessionLocal()
    try:
        return StationDepartureService.get_departures_from_station(
            session, station_id, departure_time_min, departure_time_max, date
        )
    finally:
        session.close()


def rebuild_cache() -> bool:
    """
    Convenience function for rebuilding cache (handles session management).
    """
    session = SessionLocal()
    try:
        return StationDepartureService.rebuild_station_departures_cache(session)
    finally:
        session.close()


import uuid
