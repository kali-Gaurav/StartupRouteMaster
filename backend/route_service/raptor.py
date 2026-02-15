import heapq
from collections import defaultdict
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class RAPTOR:
    """RAPTOR (Round-Based Public Transit Routing) Algorithm Implementation"""

    def __init__(self, network_data):
        self.network = network_data  # Dict with stations, schedules, etc.
        self.MAX_TRANSFERS = 3
        self.TRANSFER_TIME = 5  # minutes

    def search(self, source, destination, departure_time, max_transfers=None):
        """
        Find routes from source to destination using RAPTOR algorithm

        Args:
            source: Source station code
            destination: Destination station code
            departure_time: Departure datetime
            max_transfers: Maximum number of transfers

        Returns:
            List of route options
        """
        if max_transfers is None:
            max_transfers = self.MAX_TRANSFERS

        # Initialize
        routes = []
        earliest_arrival = {source: departure_time}
        previous = {}

        # Round 0: Direct trips
        self._round_zero(source, departure_time, earliest_arrival, previous)

        # Subsequent rounds: Transfers
        for k in range(1, max_transfers + 1):
            self._round_k(k, earliest_arrival, previous)

        # Extract routes to destination
        if destination in earliest_arrival:
            routes = self._extract_routes(destination, earliest_arrival, previous)

        return routes

    def _round_zero(self, source, departure_time, earliest_arrival, previous):
        """Round 0: Find direct trips from source"""
        # Get all trips departing from source after departure_time
        trips = self._get_trips_from_station(source, departure_time)

        for trip in trips:
            # Find arrival time at destination
            arrival_time = self._get_arrival_time(trip, source)
            if arrival_time:
                dest = trip['destination']
                if dest not in earliest_arrival or arrival_time < earliest_arrival[dest]:
                    earliest_arrival[dest] = arrival_time
                    previous[dest] = (source, trip, 0)  # (prev_station, trip, round)

    def _round_k(self, k, earliest_arrival, previous):
        """Round k: Find routes with k transfers"""
        marked_stations = set()

        # For each station reached in previous rounds
        for station in list(earliest_arrival.keys()):
            if station in earliest_arrival:
                arrival_time = earliest_arrival[station]

                # Find trips departing after arrival + transfer time
                transfer_time = arrival_time + timedelta(minutes=self.TRANSFER_TIME)
                trips = self._get_trips_from_station(station, transfer_time)

                for trip in trips:
                    # Mark stations reachable by this trip
                    reachable_stations = self._get_stations_on_trip(trip, station)

                    for reach_station in reachable_stations:
                        arrival_time_at_reach = self._get_arrival_time_at_station(trip, reach_station)
                        if reach_station not in earliest_arrival or arrival_time_at_reach < earliest_arrival[reach_station]:
                            earliest_arrival[reach_station] = arrival_time_at_reach
                            previous[reach_station] = (station, trip, k)
                            marked_stations.add(reach_station)

        # Process marked stations
        for station in marked_stations:
            # Footpaths/transfers from marked stations
            self._process_footpaths(station, earliest_arrival, previous, k)

    def _process_footpaths(self, station, earliest_arrival, previous, k):
        """Process walking transfers between nearby stations"""
        # TODO: Implement footpath processing
        pass

    def _get_trips_from_station(self, station, after_time):
        """Get trips departing from station after given time"""
        # Mock implementation - replace with actual DB query
        return [
            {
                'trip_id': 'T1',
                'departure_time': after_time + timedelta(minutes=10),
                'destination': 'DELHI',
                'stops': [
                    {'station': station, 'departure': after_time + timedelta(minutes=10)},
                    {'station': 'DELHI', 'arrival': after_time + timedelta(hours=4)}
                ]
            }
        ]

    def _get_arrival_time(self, trip, destination):
        """Get arrival time at destination for a trip"""
        for stop in trip['stops']:
            if stop['station'] == destination:
                return stop.get('arrival')
        return None

    def _get_arrival_time_at_station(self, trip, station):
        """Get arrival time at specific station"""
        return self._get_arrival_time(trip, station)

    def _get_stations_on_trip(self, trip, from_station):
        """Get all stations reachable from from_station on this trip"""
        stations = []
        found = False
        for stop in trip['stops']:
            if stop['station'] == from_station:
                found = True
            elif found:
                stations.append(stop['station'])
        return stations

    def _extract_routes(self, destination, earliest_arrival, previous):
        """Extract complete routes to destination"""
        routes = []

        # Reconstruct path
        current = destination
        path = []
        while current in previous:
            prev_station, trip, round_num = previous[current]
            path.append((prev_station, trip, round_num))
            current = prev_station
            if current not in previous:
                break

        if path:
            # Build route from path
            route = self._build_route_from_path(path, destination)
            routes.append(route)

        return routes

    def _build_route_from_path(self, path, destination):
        """Build route dict from reconstructed path"""
        segments = []
        total_duration = 0
        total_cost = 0

        # Reverse path to get chronological order
        path.reverse()

        for prev_station, trip, round_num in path:
            # Add segment
            segment = {
                'train_number': trip.get('trip_id', 'Unknown'),
                'train_name': trip.get('name', 'Train'),
                'departure_station': prev_station,
                'arrival_station': destination,
                'departure_time': trip['departure_time'].strftime('%H:%M'),
                'arrival_time': self._get_arrival_time(trip, destination).strftime('%H:%M'),
                'duration': 240,  # Mock
                'cost': 500.0  # Mock
            }
            segments.append(segment)
            total_duration += segment['duration']
            total_cost += segment['cost']

        return {
            'segments': segments,
            'total_duration': total_duration,
            'total_cost': total_cost,
            'transfers': len(segments) - 1
        }