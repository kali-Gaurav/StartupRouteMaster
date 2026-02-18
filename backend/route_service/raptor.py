import logging
import heapq
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta, time, date
from collections import defaultdict
from sqlalchemy.orm import Session
from backend.models import Stop, Trip, StopTime, Route, Calendar # Import relevant GTFS models
from .raptor_data import NetworkDataLoader # Import the data loader

logger = logging.getLogger(__name__)

class RAPTOR:
    """RAPTOR (Round-Based Public Transit Routing) Algorithm Implementation"""

    def __init__(self, network_loader: NetworkDataLoader):
        self.network_loader = network_loader
        self.MAX_TRANSFERS = 3
        self.TRANSFER_TIME = 5  # minutes # TODO: Make dynamic based on Transfer model

    def search(self, source_gtfs_id: str, destination_gtfs_id: str, departure_datetime: datetime, max_transfers: Optional[int] = None) -> List[dict]:
        """
        Find routes from source to destination using RAPTOR algorithm.

        Args:
            source_gtfs_id: GTFS ID of the source station.
            destination_gtfs_id: GTFS ID of the destination station.
            departure_datetime: Desired departure datetime.
            max_transfers: Maximum number of transfers.

        Returns:
            List of route options.
        """
        if max_transfers is None:
            max_transfers = self.MAX_TRANSFERS

        current_date = departure_datetime.date()

        # Convert GTFS IDs to internal Stop PK IDs
        source_stop_obj = self.network_loader.get_stop_by_gtfs_id(source_gtfs_id)
        destination_stop_obj = self.network_loader.get_stop_by_gtfs_id(destination_gtfs_id)

        if not source_stop_obj:
            logger.warning(f"Source station GTFS ID '{source_gtfs_id}' not found in network data.")
            return []
        if not destination_stop_obj:
            logger.warning(f"Destination station GTFS ID '{destination_gtfs_id}' not found in network data.")
            return []

        source_pk_id = source_stop_obj.id
        destination_pk_id = destination_stop_obj.id

        # earliest_arrival: Map (stop_pk_id, round_k) -> earliest_datetime
        # This stores the earliest arrival time at each stop for each round (number of transfers)
        # Initialize with infinity
        earliest_arrival_per_round = defaultdict(lambda: defaultdict(lambda: datetime.max))
        earliest_arrival_per_round[source_pk_id][0] = departure_datetime

        # previous: Map (stop_pk_id, round_k) -> (prev_stop_pk_id, trip_obj, stop_time_obj)
        # Stores the path information to reconstruct the route
        previous_per_round = defaultdict(dict)

        # Q: Queue for stations newly marked to be processed in the current round
        Q = set()
        Q.add(source_pk_id)

        # R: Routes (journeys) found
        routes_found = []

        for k in range(max_transfers + 1): # k is the round number, also represents max transfers up to this point
            # If no stations were reached in the previous round, stop
            if not Q and k > 0:
                logger.info(f"RAPTOR: No new stations reached in round {k-1}. Stopping.")
                break

            # S: Stations to scan in this round
            S = set(Q)
            Q.clear() # Clear Q for next round

            # Process connections by foot/transfer (if any, not fully implemented here yet)
            # For simplicity, assuming footpaths are processed in _round_k logic or not needed for now
            # TODO: Integrate _process_footpaths here if actual footpath logic is needed
            
            # Traverse routes (trains)
            self._scan_routes(k, S, earliest_arrival_per_round, previous_per_round, Q, current_date)

            # After scanning all routes, update earliest arrival for destination if found
            final_arrival_time = datetime.max
            final_round = -1
            for r in range(max_transfers + 1):
                if earliest_arrival_per_round[destination_pk_id][r] < final_arrival_time:
                    final_arrival_time = earliest_arrival_per_round[destination_pk_id][r]
                    final_round = r
            
            if final_round != -1:
                # Reconstruct path and add to results
                reconstructed_route = self._reconstruct_route(source_pk_id, destination_pk_id, final_round, earliest_arrival_per_round, previous_per_round, current_date)
                if reconstructed_route:
                    routes_found.append(reconstructed_route)

        return routes_found

    def _scan_routes(self, k: int, S: set, earliest_arrival_per_round: Dict, previous_per_round: Dict, Q: set, current_date: date):
        """
        Scans all routes and propagates earliest arrival times.
        k: current round (number of transfers)
        S: set of stations reached in the previous round
        earliest_arrival_per_round: earliest arrival time at each stop for each round
        previous_per_round: path reconstruction data
        Q: set of stations newly reached/improved in this round, for next round's processing
        current_date: the date for which the search is performed
        """
        
        # Initialize earliest arrival for this round, based on previous round's results
        # This is essentially the R(k-1) array in RAPTOR
        # We start by copying the earliest arrivals from the previous round (k-1)
        # This means we can transfer from any station reached in the previous round.
        if k > 0:
            for stop_pk_id in self.network_loader.stops: # Iterate all known stops
                # This ensures values from k-1 are carried over to k initially.
                # If a stop was not reached in k-1, its value is still datetime.max
                earliest_arrival_per_round[stop_pk_id][k] = earliest_arrival_per_round[stop_pk_id][k-1]

        # Q_new: stations newly reached/improved in this round, to be passed to next round (k+1)
        Q_new = set()

        # Iterate through each route
        for route_pk_id in self.network_loader.routes:
            # We track the earliest time a trip on this route can be boarded
            # from a station that was in S.
            
            current_trip: Optional[Trip] = None
            boarded_stop_pk_id: Optional[int] = None
            boarded_stop_time_obj: Optional[StopTime] = None

            # Find all trips for this route that are operating on current_date
            operating_trips_for_route = []
            for trip in self.network_loader.get_trips_for_route(route_pk_id):
                calendar = self.network_loader.db.query(Calendar).filter(Calendar.id == trip.service_id).first()
                if not calendar or not (calendar.start_date <= current_date <= calendar.end_date):
                    continue
                day_of_week_attr = current_date.strftime('%A').lower()
                if not getattr(calendar, day_of_week_attr, False):
                    continue
                operating_trips_for_route.append(trip)
            
            if not operating_trips_for_route:
                continue

            # This is where RAPTOR's route scanning loop typically goes.
            # We need to find the earliest trip on this route that can be boarded from a station in S.

            for trip in operating_trips_for_route:
                # Reset boarding status for each trip on the route
                can_board_trip_on_route = False
                boarded_stop_pk_id = None
                boarded_stop_time_obj = None

                for st in self.network_loader.get_stop_times_for_trip(trip.id):
                    # Check for boarding opportunity if not currently on a trip (or if previous trip ended)
                    if not can_board_trip_on_route: # Not currently on a trip on this route
                        # Check if this stop (st.stop_id) was reached in the *previous* round (k-1 for new board)
                        # or if it's the source for round 0.
                        earliest_arrival_at_this_stop_from_prev_round = earliest_arrival_per_round[st.stop_id][k] # K holds the value from K-1

                        if st.departure_time and earliest_arrival_at_this_stop_from_prev_round != datetime.max:
                            # Consider transfer time before boarding
                            time_after_transfer = earliest_arrival_at_this_stop_from_prev_round + timedelta(minutes=self.TRANSFER_TIME)

                            # If we can board this trip at this stop
                            if datetime.combine(current_date, st.departure_time) >= time_after_transfer:
                                # Board this trip
                                can_board_trip_on_route = True
                                boarded_stop_pk_id = st.stop_id
                                boarded_stop_time_obj = st
                                current_trip = trip
                                logger.debug(f"RAPTOR: Boarding Trip {trip.trip_id} at Stop {self.network_loader.get_stop(st.stop_id).name} (PK {st.stop_id}) at {st.departure_time} in round {k}")
                    
                    # Propagate journey if currently on a trip
                    if can_board_trip_on_route and current_trip.id == trip.id: # Still on the same trip
                        arrival_datetime_at_current_stop = datetime.combine(current_date, st.arrival_time)
                        
                        # Check if arriving at this stop (st.stop_id) provides an earlier arrival
                        # for round k
                        if arrival_datetime_at_current_stop < earliest_arrival_per_round[st.stop_id][k]:
                            earliest_arrival_per_round[st.stop_id][k] = arrival_datetime_at_current_stop
                            previous_per_round[st.stop_id][k] = (boarded_stop_pk_id, current_trip, boarded_stop_time_obj, st) # (from_stop_pk, trip, boarded_st_obj, arrived_st_obj)
                            Q_new.add(st.stop_id) # Mark this station for further processing (transfers)
            
        Q.update(Q_new) # Update the main Q set for the next round

    def _reconstruct_route(self, source_pk_id: int, destination_pk_id: int, final_round: int, earliest_arrival_per_round: Dict, previous_per_round: Dict, current_date: date) -> Optional[dict]:
        """Reconstructs a route from the previous_per_round data structure.

        Args:
            current_date: date used to convert StopTime times to datetimes for duration calculations.
        """
        current_stop_pk_id = destination_pk_id
        current_round = final_round
        path_segments = []

        # Find the actual arrival time at the destination in the specified round
        final_arrival_time_at_dest = earliest_arrival_per_round[destination_pk_id][final_round]
        
        # Iterate backwards through the rounds and stops to reconstruct the path
        # The while loop condition needs to account for the possibility that the source is reached at round 0
        while current_stop_pk_id != source_pk_id or current_round > 0:
            
            # Iterate backwards through rounds to find the path segment
            # A stop might have been reached in an earlier round than the current_round
            # to be part of the optimal path.
            while current_stop_pk_id not in previous_per_round or current_round not in previous_per_round[current_stop_pk_id]:
                current_round -= 1
                if current_round < 0:
                    logger.warning(f"RAPTOR: Could not reconstruct path to {destination_pk_id}. Missing data for stop {current_stop_pk_id}.")
                    return None
            
            # (from_stop_pk, trip, boarded_st_time_obj, arrived_st_time_obj_at_current)
            prev_stop_pk_id, trip, boarded_st_time_obj, arrived_st_time_obj_at_current = previous_per_round[current_stop_pk_id][current_round]
            
            path_segments.append({
                "trip": trip,
                "boarded_at_stop_pk_id": boarded_st_time_obj.stop_id,
                "arrival_at_stop_pk_id": arrived_st_time_obj_at_current.stop_id,
                "board_stop_time": boarded_st_time_obj,
                "arrive_stop_time": arrived_st_time_obj_at_current # The StopTime object at the arrival station of this segment
            })
            current_stop_pk_id = prev_stop_pk_id
            # The current_round is used to find the path segment.
            # After adding a segment, we need to look for the path to prev_stop_pk_id in the previous round.
            current_round = current_round - 1 # Always step back one round

        path_segments.reverse() # Order from source to destination

        # Now convert path_segments to RouteResponse format
        segments = []
        total_duration = timedelta()
        total_cost = 0.0

        for i, path_seg in enumerate(path_segments):
            trip: Trip = path_seg["trip"]
            boarded_st_time_obj: StopTime = path_seg["board_stop_time"]
            arrived_st_time_obj: StopTime = path_seg["arrive_stop_time"] # The actual stop time when arriving at the stop

            route_obj = self.network_loader.get_route(trip.route_id)
            if not route_obj:
                logger.warning(f"RAPTOR: Route not found for trip {trip.trip_id}")
                continue
            
            departure_stop_obj = self.network_loader.get_stop(boarded_st_time_obj.stop_id)
            arrival_stop_obj = self.network_loader.get_stop(arrived_st_time_obj.stop_id)

            if not departure_stop_obj or not arrival_stop_obj:
                logger.warning(f"RAPTOR: Missing stop data for reconstruction.")
                continue

            # Calculate duration for this segment
            # Assuming current_date is constant for all segments in a single route search
            segment_dep_dt = datetime.combine(current_date, boarded_st_time_obj.departure_time)
            segment_arr_dt = datetime.combine(current_date, arrived_st_time_obj.arrival_time)
            
            # Handle overnight trips: if arrival time is earlier than departure time, it's next day.
            if segment_arr_dt < segment_dep_dt:
                segment_arr_dt += timedelta(days=1)
            
            segment_duration = (segment_arr_dt - segment_dep_dt).total_seconds() / 60 # In minutes

            segment = {
                "train_number": route_obj.route_id, # GTFS route_id (train_number)
                "train_name": route_obj.long_name,
                "departure_station": departure_stop_obj.name, # Using name for output
                "arrival_station": arrival_stop_obj.name,
                "departure_time": boarded_st_time_obj.departure_time.strftime('%H:%M'),
                "arrival_time": arrived_st_time_obj.arrival_time.strftime('%H:%M'),
                "duration": int(segment_duration),
                "cost": boarded_st_time_obj.cost # Use the cost from StopTime
            }
            segments.append(segment)
            total_duration += timedelta(minutes=int(segment_duration))
            total_cost += boarded_st_time_obj.cost # Assuming cost is cumulative here (or per segment logic needs refinement)

            # Add transfer time if this isn't the last segment
            # A transfer is implicit when we switch trips. The RAPTOR algorithm
            # handles transfer time by adding it *before* boarding a new trip.
            # So, the transfer time is already accounted for in the earliest arrival calculation.
            # We don't add it again here to the total_duration for each segment.
            # Only add if we transfer between routes, not just between stops on the same trip.
            
            # The definition of 'transfers' count should be number of distinct trips taken - 1.
            # The current reconstruction counts number of segments - 1, which implies transfers between segments.
            # For simplicity for now, use segments - 1 as transfer count.
            pass


        return {
            'segments': segments,
            'total_duration': int(total_duration.total_seconds() / 60), # Total duration in minutes
            'total_cost': total_cost,
            'transfers': len(segments) - 1 # Simple transfer count
        }


    def _get_trips_from_station(self, stop_pk_id: int, after_datetime: datetime, current_date: date) -> List[Tuple[Trip, StopTime]]:
        """
        Get trips departing from a station (by PK ID) after a given time on a specific date.
        Uses NetworkDataLoader.
        """
        return self.network_loader.get_trips_departing_from_stop_after(stop_pk_id, after_datetime.time(), current_date)

    def _get_arrival_time(self, trip: Trip, destination_stop_pk_id: int, current_date: date) -> Optional[datetime]:
        """
        Get arrival datetime at destination for a given Trip object.
        """
        for st in self.network_loader.get_stop_times_for_trip(trip.id):
            if st.stop_id == destination_stop_pk_id:
                return datetime.combine(current_date, st.arrival_time)
        return None

    def _get_arrival_time_at_station(self, trip: Trip, station_pk_id: int, current_date: date) -> Optional[datetime]:
        """Get arrival datetime at specific station for a trip."""
        return self._get_arrival_time(trip, station_pk_id, current_date)

    def _get_stations_on_trip(self, trip: Trip, from_stop_pk_id: int) -> List[int]:
        """
        Get all station PK IDs reachable from from_stop_pk_id on this trip.
        """
        reachable_pk_ids = []
        found_from_stop = False
        for st in self.network_loader.get_stop_times_for_trip(trip.id):
            if st.stop_id == from_stop_pk_id:
                found_from_stop = True
            elif found_from_stop:
                reachable_pk_ids.append(st.stop_id)
        return reachable_pk_ids
