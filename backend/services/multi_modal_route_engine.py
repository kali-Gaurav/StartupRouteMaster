import logging
import asyncio
import redis
import json
import hashlib
import hmac
from typing import List, Dict, Optional, Tuple, Set
from datetime import datetime, date, time, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
import heapq

from backend.config import Config
from backend.models import (
    Agency, Stop, Route, Trip, StopTime, Transfer,
    Calendar, CalendarDate, Disruption, SeatInventory
)
from backend.database import get_db
from backend.services.cache_service import cache_service

logger = logging.getLogger(__name__)

class MultiModalRouteEngine:
    """
    Multi-modal RAPTOR-based routing engine for GTFS transit data.
    Supports transfers between different transport modes (tram, subway, rail, bus).
    Features connecting journeys, circular trips, multi-city booking, and fare calculation.
    """

    CACHE_SCHEMA_VERSION = 1
    MAX_TRANSFERS = 3
    MAX_JOURNEYS = 3  # For multi-city booking

    def __init__(self):
        self.stops_map: Dict[int, Dict] = {}
        self.routes_map: Dict[int, Dict] = {}
        self.trips_map: Dict[int, Dict] = {}
        self.stop_times_map: Dict[int, List[Dict]] = {}
        self.transfers_map: Dict[int, List[Dict]] = {}
        self.calendar_map: Dict[int, Dict] = {}
        self.calendar_dates_map: Dict[int, List[Dict]] = {}
        self._is_loaded = False
        self._redis_client = None

    def _get_redis_client(self):
        if self._redis_client is None:
            try:
                self._redis_client = redis.from_url(Config.REDIS_URL, decode_responses=True)
            except:
                self._redis_client = None
        return self._redis_client

    def load_graph_from_db(self, db: Session):
        """Load GTFS data into memory structures."""
        if self._is_loaded:
            return

        logger.info("Loading GTFS graph from database...")

        # Load stops
        stops = db.query(Stop).all()
        for stop in stops:
            # prefer an explicit safety_score column if available in the DB model, otherwise default to 50
            safety = getattr(stop, 'safety_score', None)
            if safety is None:
                safety = 50
            self.stops_map[stop.id] = {
                'stop_id': stop.stop_id,
                'name': stop.name,
                'city': stop.city,
                'lat': stop.latitude,
                'lon': stop.longitude,
                'location_type': stop.location_type,
                'parent_station': stop.parent_station_id,
                'safety_score': float(safety)
            }

        # Load routes
        routes = db.query(Route).all()
        for route in routes:
            self.routes_map[route.id] = {
                'route_id': route.route_id,
                'agency_id': route.agency_id,
                'short_name': route.short_name,
                'long_name': route.long_name,
                'route_type': route.route_type
            }

        # Load trips
        trips = db.query(Trip).all()
        for trip in trips:
            self.trips_map[trip.id] = {
                'trip_id': trip.trip_id,
                'route_id': trip.route_id,
                'service_id': trip.service_id,
                'headsign': trip.headsign,
                'direction_id': trip.direction_id
            }

        # Load stop times
        stop_times = db.query(StopTime).all()
        for st in stop_times:
            if st.trip_id not in self.stop_times_map:
                self.stop_times_map[st.trip_id] = []
            self.stop_times_map[st.trip_id].append({
                'stop_id': st.stop_id,
                'arrival_time': st.arrival_time,
                'departure_time': st.departure_time,
                'stop_sequence': st.stop_sequence,
                'cost': st.cost or 0.0
            })

        # Sort stop times by sequence
        for trip_id in self.stop_times_map:
            self.stop_times_map[trip_id].sort(key=lambda x: x['stop_sequence'])

        # Load transfers
        transfers = db.query(Transfer).all()
        for transfer in transfers:
            from_stop = transfer.from_stop_id
            if from_stop not in self.transfers_map:
                self.transfers_map[from_stop] = []
            self.transfers_map[from_stop].append({
                'to_stop_id': transfer.to_stop_id,
                'transfer_type': transfer.transfer_type,
                'min_transfer_time': transfer.min_transfer_time
            })

        # Load calendar
        calendars = db.query(Calendar).all()
        for cal in calendars:
            self.calendar_map[cal.id] = {
                'service_id': cal.service_id,
                'monday': cal.monday,
                'tuesday': cal.tuesday,
                'wednesday': cal.wednesday,
                'thursday': cal.thursday,
                'friday': cal.friday,
                'saturday': cal.saturday,
                'sunday': cal.sunday,
                'start_date': cal.start_date,
                'end_date': cal.end_date
            }

        # Load calendar dates
        calendar_dates = db.query(CalendarDate).all()
        for cd in calendar_dates:
            service_id = cd.service_id
            if service_id not in self.calendar_dates_map:
                self.calendar_dates_map[service_id] = []
            self.calendar_dates_map[service_id].append({
                'date': cd.date,
                'exception_type': cd.exception_type
            })

        self._is_loaded = True
        logger.info(f"GTFS graph loaded: {len(self.stops_map)} stops, {len(self.routes_map)} routes, {len(self.trips_map)} trips")

    def _time_to_minutes(self, t: time) -> int:
        """Convert time to minutes since midnight."""
        return t.hour * 60 + t.minute

    def _minutes_to_time(self, minutes: int) -> time:
        """Convert minutes since midnight to time."""
        hours = minutes // 60
        mins = minutes % 60
        return time(hour=hours, minute=mins)

    def _is_service_active(self, service_id: int, travel_date: date) -> bool:
        """Check if service operates on given date."""
        if service_id not in self.calendar_map:
            return False

        cal = self.calendar_map[service_id]

        # Check date range
        if not (cal['start_date'] <= travel_date <= cal['end_date']):
            return False

        # Check calendar dates exceptions
        if service_id in self.calendar_dates_map:
            for cd in self.calendar_dates_map[service_id]:
                if cd['date'] == travel_date:
                    return cd['exception_type'] == 1  # 1 = added, 2 = removed

        # Check weekday
        weekday = travel_date.weekday()  # 0=Monday
        weekday_map = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        return cal[weekday_map[weekday]]

    def _get_earliest_departure(self, trip_id: int, from_stop_id: int, after_time: int) -> Optional[Tuple[int, int, float]]:
        """
        Get earliest departure time from a stop on a trip after given time.
        Returns (departure_minutes, arrival_stop_minutes, cost)
        """
        if trip_id not in self.stop_times_map:
            return None

        stop_times = self.stop_times_map[trip_id]
        from_sequence = None
        departure_minutes = None
        cost_accum = 0.0

        for st in stop_times:
            if st['stop_id'] == from_stop_id:
                dep_min = self._time_to_minutes(st['departure_time'])
                if dep_min >= after_time:
                    from_sequence = st['stop_sequence']
                    departure_minutes = dep_min
                    break
            elif from_sequence is not None and st['stop_sequence'] > from_sequence:
                arr_min = self._time_to_minutes(st['arrival_time'])
                cost_accum += st['cost']
                return (departure_minutes, arr_min, cost_accum)

        return None

    def _find_feasible_trips(self, from_stop_id: int, travel_date: date, after_time: int) -> List[Tuple[int, int, int, float]]:
        """
        Find all feasible trips from a stop.
        Returns list of (trip_id, departure_minutes, arrival_minutes, cost)
        """
        feasible_trips = []

        # Find all trips that stop at this stop
        for trip_id, stop_times in self.stop_times_map.items():
            trip_info = self.trips_map[trip_id]
            if not self._is_service_active(trip_info['service_id'], travel_date):
                continue

            result = self._get_earliest_departure(trip_id, from_stop_id, after_time)
            if result:
                dep_min, arr_min, cost = result
                feasible_trips.append((trip_id, dep_min, arr_min, cost))

        return feasible_trips

    def _multi_modal_raptor(self, source_stop_id: int, dest_stop_id: int, travel_date: date,
                           max_transfers: int = MAX_TRANSFERS) -> List[Dict]:
        """
        Multi-modal RAPTOR algorithm implementation.
        Returns list of journey options with transfers between modes.
        """
        if source_stop_id == dest_stop_id:
            return []

        # Initialize labels: stop_id -> list of (arrival_time, cost, trip_id, transfers)
        labels = {stop_id: [] for stop_id in self.stops_map.keys()}
        labels[source_stop_id] = [(0, 0.0, None, 0)]  # (time, cost, trip, transfers)

        # Track best arrival times per round
        best_arrival_times = {stop_id: float('inf') for stop_id in self.stops_map.keys()}
        best_arrival_times[source_stop_id] = 0

        marked_stops = {source_stop_id}

        for round_num in range(max_transfers + 1):
            if not marked_stops:
                break

            next_marked = set()

            # Process each marked stop
            for current_stop in marked_stops:
                current_labels = labels[current_stop]

                for arr_time, arr_cost, last_trip, transfers in current_labels:
                    # Find feasible trips from current stop
                    feasible_trips = self._find_feasible_trips(current_stop, travel_date, arr_time)

                    for trip_id, dep_time, arr_time_trip, trip_cost in feasible_trips:
                        trip_info = self.trips_map[trip_id]
                        route_info = self.routes_map[trip_info['route_id']]

                        # Get all stops on this trip after current stop
                        stop_times = self.stop_times_map[trip_id]
                        current_sequence = None

                        for st in stop_times:
                            if st['stop_id'] == current_stop:
                                current_sequence = st['stop_sequence']
                                break

                        if current_sequence is None:
                            continue

                        cumulative_cost = 0.0
                        for st in stop_times:
                            if st['stop_sequence'] <= current_sequence:
                                continue

                            stop_id = st['stop_id']
                            arrival_min = self._time_to_minutes(st['arrival_time'])
                            cumulative_cost += st['cost']

                            new_arr_time = arrival_min
                            new_cost = arr_cost + cumulative_cost
                            new_transfers = transfers

                            # Check if this improves the label
                            existing_labels = labels[stop_id]
                            is_dominated = any(
                                ex_time <= new_arr_time and ex_cost <= new_cost
                                for ex_time, ex_cost, _, _ in existing_labels
                            )

                            if not is_dominated:
                                # Remove dominated labels
                                new_labels = [
                                    (t, c, tr, tf) for t, c, tr, tf in existing_labels
                                    if not (new_arr_time <= t and new_cost <= c)
                                ]
                                new_labels.append((new_arr_time, new_cost, trip_id, new_transfers))
                                labels[stop_id] = new_labels

                                if new_arr_time < best_arrival_times[stop_id]:
                                    best_arrival_times[stop_id] = new_arr_time
                                    next_marked.add(stop_id)

            # Handle transfers
            transfer_marked = set()
            for stop_id in next_marked:
                if stop_id in self.transfers_map:
                    for transfer in self.transfers_map[stop_id]:
                        to_stop = transfer['to_stop_id']
                        transfer_time = transfer['min_transfer_time'] // 60  # Convert to minutes

                        for arr_time, arr_cost, trip_id, transfers in labels[stop_id]:
                            new_arr_time = arr_time + transfer_time
                            new_labels = labels[to_stop]

                            is_dominated = any(
                                ex_time <= new_arr_time and ex_cost <= arr_cost
                                for ex_time, ex_cost, _, _ in new_labels
                            )

                            if not is_dominated:
                                new_labels = [
                                    (t, c, tr, tf) for t, c, tr, tf in new_labels
                                    if not (new_arr_time <= t and arr_cost <= c)
                                ]
                                new_labels.append((new_arr_time, arr_cost, trip_id, transfers + 1))
                                labels[to_stop] = new_labels
                                transfer_marked.add(to_stop)

            marked_stops = next_marked | transfer_marked

        # Extract journeys to destination
        journeys = []
        for arr_time, arr_cost, trip_id, transfers in labels[dest_stop_id]:
            journey = self._reconstruct_journey(source_stop_id, dest_stop_id, arr_time, arr_cost, trip_id)
            if journey:
                journeys.append(journey)

        # Sort by arrival time, then cost
        journeys.sort(key=lambda x: (x['arrival_time'], x['total_cost']))
        return journeys[:10]  # Return top 10 options

    def _reconstruct_journey(self, source_stop: int, dest_stop: int, arr_time: int,
                           arr_cost: float, last_trip: int) -> Optional[Dict]:
        """Reconstruct journey details from RAPTOR results."""
        # This is a simplified reconstruction - in practice, you'd need to track the path
        # For now, return a basic journey structure
        return {
            'source_stop_id': source_stop,
            'dest_stop_id': dest_stop,
            'arrival_time': arr_time,
            'total_cost': arr_cost,
            'trips': [last_trip] if last_trip else [],
            'transfers': 0
        }

    def search_single_journey(self, source_stop_id: int, dest_stop_id: int,
                            travel_date: date) -> List[Dict]:
        """Search for single journey options."""
        if not self._is_loaded:
            raise RuntimeError("MultiModalRouteEngine graph is not loaded.")

        journeys = self._multi_modal_raptor(source_stop_id, dest_stop_id, travel_date)

        # Enrich journey data
        enriched_journeys = []
        for journey in journeys:
            enriched = self._enrich_journey(journey, travel_date)
            if enriched:
                enriched_journeys.append(enriched)

        return enriched_journeys

    def _enrich_journey(self, journey: Dict, travel_date: date) -> Optional[Dict]:
        """Add detailed information to journey."""
        try:
            source_stop = self.stops_map[journey['source_stop_id']]
            dest_stop = self.stops_map[journey['dest_stop_id']]

            segments = []
            total_duration = 0

            # For each trip in the journey
            for trip_id in journey.get('trips', []):
                if trip_id not in self.trips_map:
                    continue

                trip_info = self.trips_map[trip_id]
                route_info = self.routes_map[trip_info['route_id']]

                stop_times = self.stop_times_map[trip_id]
                for i in range(len(stop_times) - 1):
                    current_st = stop_times[i]
                    next_st = stop_times[i + 1]

                    dep_time = self._time_to_minutes(current_st['departure_time'])
                    arr_time = self._time_to_minutes(next_st['arrival_time'])
                    duration = arr_time - dep_time
                    cost = next_st['cost']

                    segments.append({
                        'mode': self._route_type_to_mode(route_info['route_type']),
                        'from_stop': self.stops_map[current_st['stop_id']]['name'],
                        'to_stop': self.stops_map[next_st['stop_id']]['name'],
                        'departure_time': self._minutes_to_time(dep_time),
                        'arrival_time': self._minutes_to_time(arr_time),
                        'duration_minutes': duration,
                        'cost': cost,
                        'route_name': route_info['long_name'],
                        'trip_id': trip_info['trip_id']
                    })
                    total_duration += duration

            return {
                'journey_id': f"journey_{hashlib.md5(f'{journey}'.encode()).hexdigest()[:12]}",
                'source': source_stop['name'],
                'destination': dest_stop['name'],
                'departure_date': travel_date.isoformat(),
                'segments': segments,
                'total_duration_minutes': total_duration,
                'total_cost': journey['total_cost'],
                'transfers': journey['transfers'],
                'modes': list(set(s['mode'] for s in segments)),
                'pnr_reference': None  # Will be set when booked
            }
        except Exception as e:
            logger.error(f"Error enriching journey: {e}")
            return None

    def _route_type_to_mode(self, route_type: int) -> str:
        """Convert GTFS route type to mode string."""
        mapping = {
            0: 'tram',
            1: 'subway',
            2: 'rail',
            3: 'bus'
        }
        return mapping.get(route_type, 'unknown')

    def _compute_feasibility_score(self, *, total_time_minutes: float, total_cost: float, safety_score: float, transfers: int, layover_penalty: float = 0.0) -> float:
        """Compute feasibility score for connecting / multimodal journeys.
        Keeps the same weighting strategy as the main RouteEngine.
        """
        wt = getattr(Config, 'FEASIBILITY_WEIGHT_TIME', 1.0)
        wc = getattr(Config, 'FEASIBILITY_WEIGHT_COST', 0.01)
        wf = getattr(Config, 'FEASIBILITY_WEIGHT_COMFORT', 0.5)
        wtr = getattr(Config, 'FEASIBILITY_WEIGHT_TRANSFERS', 5.0)

        time_hours = total_time_minutes / 60.0
        score = (wf * (safety_score / 100.0)) - (wt * time_hours) - (wc * total_cost) - (wtr * transfers) - layover_penalty
        return score

    def _combine_journeys(self, j1: Dict, j2: Dict, layover_minutes: float) -> Dict:
        """Combine two journeys into a connecting journey and compute feasibility score."""
        combined_segments = j1['segments'] + j2['segments']
        total_duration = j1['total_duration_minutes'] + j2['total_duration_minutes'] + layover_minutes
        total_cost = j1['total_cost'] + j2['total_cost']

        # Determine safety score: average of involved stops' safety_score when available
        stop_names = [seg.get('from_stop') or seg.get('from') for seg in combined_segments if seg.get('from_stop') or seg.get('from')]
        safety_vals = []
        # try to map stop names back to stop entries
        for stop_id, stop_info in self.stops_map.items():
            if stop_info['name'] in stop_names and isinstance(stop_info.get('safety_score'), (int, float)):
                safety_vals.append(float(stop_info['safety_score']))
        if safety_vals:
            safety_score = sum(safety_vals) / len(safety_vals)
        else:
            # fallback heuristic
            safety_score = max(1, 100 - (len(combined_segments) - 1) * 10 - int(total_duration / 60 / 24))

        # Night layover penalty (if layover in night window)
        NIGHT_START = 22 * 60
        NIGHT_END = 5 * 60
        layover_penalty = 0.0
        # check approximate time of layover using j1 last segment arrival
        if j1['segments']:
            last_seg = j1['segments'][-1]
            # attempt to parse time objects or strings
            try:
                arr_time = last_seg.get('arrival_time')
                if isinstance(arr_time, str):
                    hh, mm = map(int, arr_time.split(':'))
                    arr_min = hh * 60 + mm
                else:
                    arr_min = arr_time.hour * 60 + arr_time.minute
                if (arr_min >= NIGHT_START) or (arr_min <= NIGHT_END):
                    station_name = j1['destination']
                    # find station safety
                    station_safety = 50.0
                    for sid, sinfo in self.stops_map.items():
                        if sinfo['name'] == station_name:
                            station_safety = float(sinfo.get('safety_score', station_safety))
                            break
                    station_factor = max(0.0, 1.0 - station_safety / 100.0)
                    layover_penalty = station_factor * getattr(Config, 'NIGHT_LAYOVER_PENALTY', 1.0)
            except Exception:
                # defensive: if we cannot parse times, ignore layover penalty
                pass

        feasibility = self._compute_feasibility_score(
            total_time_minutes=total_duration,
            total_cost=total_cost,
            safety_score=safety_score,
            transfers=j1.get('transfers', 0) + j2.get('transfers', 0) + 1,
            layover_penalty=layover_penalty
        )

        return {
            'journey_id': f"connecting_{j1['journey_id']}_{j2['journey_id']}",
            'source': j1['source'],
            'destination': j2['destination'],
            'departure_date': j1['departure_date'],
            'segments': combined_segments,
            'total_duration_minutes': total_duration,
            'total_cost': total_cost,
            'transfers': j1['transfers'] + j2['transfers'] + 1,  # +1 for inter-journey transfer
            'modes': list(set(j1['modes'] + j2['modes'])),
            'layover_minutes': layover_minutes,
            'connecting_stations': [j1['destination']],
            'pnr_references': [j1.get('pnr_reference'), j2.get('pnr_reference')],
            'safety_score': safety_score,
            'layover_penalty': layover_penalty,
            'feasibility_score': feasibility
        }

    def search_connecting_journeys(self, journeys: List[Dict], min_layover: int = 30,
                                 max_layover: int = 240) -> List[Dict]:
        """
        Find connecting journey combinations.
        journeys: List of individual journey options
        Returns combined journeys with layovers
        """
        if len(journeys) < 2:
            return journeys

        connecting_options = []

        # Group journeys by destination
        dest_groups = {}
        for journey in journeys:
            dest = journey['destination']
            if dest not in dest_groups:
                dest_groups[dest] = []
            dest_groups[dest].append(journey)

        # Find connections
        for dest1, journeys1 in dest_groups.items():
            for dest2, journeys2 in dest_groups.items():
                if dest1 == dest2:
                    continue

                for j1 in journeys1:
                    for j2 in journeys2:
                        # Check if j2 can connect from j1's destination
                        if j1['destination'] != j2['source']:
                            continue

                        # Calculate layover time
                        j1_arrival = self._calculate_journey_arrival_time(j1)
                        j2_departure = self._calculate_journey_departure_time(j2)

                        if j1_arrival and j2_departure:
                            layover_minutes = (j2_departure - j1_arrival).total_seconds() / 60

                            if min_layover <= layover_minutes <= max_layover:
                                combined = self._combine_journeys(j1, j2, layover_minutes)
                                connecting_options.append(combined)

        return connecting_options[:20]  # Limit results

    def _calculate_journey_arrival_time(self, journey: Dict) -> Optional[datetime]:
        """Calculate actual arrival datetime for journey."""
        try:
            date_obj = datetime.fromisoformat(journey['departure_date']).date()
            if journey['segments']:
                last_segment = journey['segments'][-1]
                arrival_time = last_segment['arrival_time']
                return datetime.combine(date_obj, arrival_time)
        except:
            pass
        return None

    def _calculate_journey_departure_time(self, journey: Dict) -> Optional[datetime]:
        """Calculate actual departure datetime for journey."""
        try:
            date_obj = datetime.fromisoformat(journey['departure_date']).date()
            if journey['segments']:
                first_segment = journey['segments'][0]
                dep_time = first_segment['departure_time']
                return datetime.combine(date_obj, dep_time)
        except:
            pass
        return None



    def search_circular_journey(self, outward_journey: Dict, return_date: date,
                              max_layover: int = 1440) -> List[Dict]:
        """
        Create circular (round-trip) journey options.
        Returns combined outward + return journeys with telescopic fares.
        """
        circular_options = []

        # Search return journeys from destination back to source
        dest_stop_id = None
        source_stop_id = None

        for stop_id, stop_info in self.stops_map.items():
            if stop_info['name'] == outward_journey['destination']:
                dest_stop_id = stop_id
            if stop_info['name'] == outward_journey['source']:
                source_stop_id = stop_id

        if not dest_stop_id or not source_stop_id:
            return []

        return_journeys = self.search_single_journey(dest_stop_id, source_stop_id, return_date)

        for return_journey in return_journeys:
            # Calculate layover between outward arrival and return departure
            outward_arrival = self._calculate_journey_arrival_time(outward_journey)
            return_departure = self._calculate_journey_departure_time(return_journey)

            if outward_arrival and return_departure:
                layover_minutes = (return_departure - outward_arrival).total_seconds() / 60

                if 0 <= layover_minutes <= max_layover:
                    circular = self._create_circular_journey(outward_journey, return_journey, layover_minutes)
                    circular_options.append(circular)

        return circular_options[:10]

    def _create_circular_journey(self, outward: Dict, return_journey: Dict, layover_minutes: float) -> Dict:
        """Create a circular journey with telescopic fare calculation."""
        total_duration = outward['total_duration_minutes'] + return_journey['total_duration_minutes'] + layover_minutes
        base_cost = outward['total_cost'] + return_journey['total_cost']

        # Apply telescopic fare discount (simplified)
        telescopic_discount = min(0.3, layover_minutes / 1440)  # Up to 30% discount
        total_cost = base_cost * (1 - telescopic_discount)

        return {
            'journey_id': f"circular_{outward['journey_id']}_{return_journey['journey_id']}",
            'source': outward['source'],
            'destination': outward['destination'],
            'outward_date': outward['departure_date'],
            'return_date': return_journey['departure_date'],
            'outward_segments': outward['segments'],
            'return_segments': return_journey['segments'],
            'total_duration_minutes': total_duration,
            'base_cost': base_cost,
            'total_cost': total_cost,
            'telescopic_discount': telescopic_discount,
            'layover_minutes': layover_minutes,
            'modes': list(set(outward['modes'] + return_journey['modes'])),
            'pnr_references': [outward.get('pnr_reference'), return_journey.get('pnr_reference')]
        }

    def search_multi_city_journey(self, cities: List[str], travel_dates: List[date],
                               max_journeys: int = MAX_JOURNEYS) -> List[Dict]:
        """
        Search multi-city journeys (up to 3 cities).
        cities: List of city names in order
        travel_dates: Corresponding travel dates
        """
        if len(cities) < 2 or len(cities) > 3 or len(cities) != len(travel_dates):
            return []

        multi_city_options = []

        # Find stop IDs for cities (simplified - take first stop in each city)
        city_stops = {}
        for city in cities:
            for stop_id, stop_info in self.stops_map.items():
                if stop_info['city'] == city:
                    city_stops[city] = stop_id
                    break

        if len(city_stops) != len(cities):
            return []

        # Search journeys between consecutive cities
        journey_segments = []
        for i in range(len(cities) - 1):
            from_city = cities[i]
            to_city = cities[i + 1]
            travel_date = travel_dates[i]

            from_stop = city_stops[from_city]
            to_stop = city_stops[to_city]

            journeys = self.search_single_journey(from_stop, to_stop, travel_date)
            if not journeys:
                return []  # No options for this segment

            journey_segments.append(journeys[0])  # Take best option for simplicity

        # Combine into multi-city journey
        combined_segments = []
        total_duration = 0
        total_cost = 0
        all_modes = set()

        for journey in journey_segments:
            combined_segments.extend(journey['segments'])
            total_duration += journey['total_duration_minutes']
            total_cost += journey['total_cost']
            all_modes.update(journey['modes'])

        multi_city_journey = {
            'journey_id': f"multicity_{'_'.join(cities)}_{hashlib.md5(str(travel_dates).encode()).hexdigest()[:8]}",
            'cities': cities,
            'travel_dates': [d.isoformat() for d in travel_dates],
            'segments': combined_segments,
            'total_duration_minutes': total_duration,
            'total_cost': total_cost,
            'transfers': sum(j['transfers'] for j in journey_segments),
            'modes': list(all_modes),
            'pnr_references': [j.get('pnr_reference') for j in journey_segments]
        }

        return [multi_city_journey]

    def calculate_fare_with_concessions(self, journey: Dict, passenger_type: str = 'adult',
                                      concessions: List[str] = None) -> Dict:
        """
        Calculate fare with mode-specific pricing and concessions.
        passenger_type: 'adult', 'child', 'senior', 'student'
        concessions: List of applicable concessions
        """
        base_cost = journey['total_cost']
        mode_multipliers = {
            'tram': 1.0,
            'bus': 1.0,
            'subway': 1.2,
            'rail': 1.5
        }

        # Apply mode-specific pricing
        adjusted_cost = 0
        for segment in journey['segments']:
            mode = segment['mode']
            multiplier = mode_multipliers.get(mode, 1.0)
            adjusted_cost += segment['cost'] * multiplier

        # Apply passenger type discounts
        passenger_discounts = {
            'adult': 1.0,
            'child': 0.5,
            'senior': 0.6,
            'student': 0.7
        }
        adjusted_cost *= passenger_discounts.get(passenger_type, 1.0)

        # Apply concessions
        concession_discount = 0
        if concessions:
            for concession in concessions:
                if concession == 'defence':
                    concession_discount += 0.1
                elif concession == 'freedom_fighter':
                    concession_discount += 0.5
                elif concession == 'divyang':
                    concession_discount += 0.5

        adjusted_cost *= (1 - min(concession_discount, 0.75))  # Max 75% concession

        return {
            'base_fare': base_cost,
            'adjusted_fare': adjusted_cost,
            'passenger_type': passenger_type,
            'concessions_applied': concessions or [],
            'mode_breakdown': {
                mode: sum(s['cost'] * mode_multipliers.get(s['mode'], 1.0)
                         for s in journey['segments'] if s['mode'] == mode)
                for mode in set(s['mode'] for s in journey['segments'])
            }
        }

    def simulate_real_time_delays(self, journey: Dict, disruption_db: Session = None) -> Dict:
        """
        Simulate real-time delay handling and OTP-based confirmations.
        """
        delayed_journey = journey.copy()
        total_delay = 0

        # Check for active disruptions
        disruptions = []
        if disruption_db:
            try:
                travel_date = datetime.fromisoformat(journey['departure_date']).date()
                disruptions = disruption_db.query(Disruption).filter(
                    Disruption.status == "active",
                    or_(
                        and_(Disruption.start_time <= datetime.combine(travel_date, datetime.max.time()),
                             Disruption.end_time >= datetime.combine(travel_date, datetime.min.time())),
                        Disruption.gtfs_route_id.in_([s.get('route_id') for s in journey.get('segments', [])])
                    )
                ).all()
            except Exception as e:
                logger.error(f"Error querying disruptions: {e}")
                disruptions = []
            except Exception as e:
                logger.error(f"Error querying disruptions: {e}")
                disruptions = []

        # Apply delays based on disruptions
        for disruption in disruptions:
            delay_minutes = 15  # Default delay
            if disruption.disruption_type == 'delay':
                delay_minutes = 30
            elif disruption.disruption_type == 'cancellation':
                delay_minutes = 120  # Major delay for cancellations

            total_delay += delay_minutes

        # Update segment times
        current_delay = 0
        for segment in delayed_journey['segments']:
            segment['delay_minutes'] = current_delay
            segment['adjusted_departure'] = (
                datetime.combine(datetime.fromisoformat(journey['departure_date']).date(),
                               segment['departure_time']) +
                timedelta(minutes=current_delay)
            ).time()
            segment['adjusted_arrival'] = (
                datetime.combine(datetime.fromisoformat(journey['departure_date']).date(),
                               segment['arrival_time']) +
                timedelta(minutes=current_delay + segment['duration_minutes'])
            ).time()
            current_delay += total_delay / len(delayed_journey['segments'])

        delayed_journey['total_delay_minutes'] = total_delay
        delayed_journey['otp_confidence'] = max(0, 100 - total_delay)  # Simplified OTP calculation

        return delayed_journey

    def generate_pnr_reference(self, journey: Dict, user_id: str) -> str:
        """Generate PNR-like reference for booking."""
        import uuid
        pnr = f"PNR{uuid.uuid4().hex[:10].upper()}"
        journey['pnr_reference'] = pnr
        return pnr

# Global instance
multi_modal_route_engine = MultiModalRouteEngine()