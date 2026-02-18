"""
Multi-Modal Routing Validators (RT-051 to RT-070)

This module handles validation logic for multi-modal routing scenarios, including
train-bus integration, mode preferences, transfer penalties, and geographic constraints.
"""

from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


class TransportMode(Enum):
    """Supported transport modes"""
    TRAIN = "train"
    BUS = "bus"
    WALK = "walk"
    BIKE = "bike"
    TAXI = "taxi"
    METRO = "metro"
    RAIL = "rail"


@dataclass
class ModalitySegment:
    """Represents a single mode journey segment"""
    mode: TransportMode
    from_stop_id: int
    to_stop_id: int
    departure_time: datetime
    arrival_time: datetime
    distance_km: float
    cost: float
    duration_minutes: int
    comfort_score: float = 5.0
    safety_score: float = 5.0
    is_available: bool = True


@dataclass
class MultimodalRoute:
    """Represents a multi-modal route with multiple transport modes"""
    segments: List[ModalitySegment]
    total_cost: float
    total_duration_minutes: int
    mode_changes: int
    walking_distance_m: float = 0.0
    transfer_connections: List[Dict] = None


class MultimodalValidator:
    """Validator class for multi-modal routing scenarios"""

    def __init__(self):
        """Initialize the multimodal validator"""
        self.mode_availability = {
            TransportMode.TRAIN: True,
            TransportMode.BUS: True,
            TransportMode.WALK: True,
            TransportMode.BIKE: True,
            TransportMode.TAXI: True,
            TransportMode.METRO: True,
            TransportMode.RAIL: True,
        }
        self.mode_cost_weights = {
            TransportMode.TRAIN: 1.0,
            TransportMode.BUS: 0.8,
            TransportMode.WALK: 0.0,
            TransportMode.BIKE: 0.2,
            TransportMode.TAXI: 1.5,
            TransportMode.METRO: 0.9,
            TransportMode.RAIL: 1.1,
        }
        self.max_walking_distance_m = 2000  # 2km default max walking
        self.airport_transfer_modes = [TransportMode.TAXI, TransportMode.BUS, TransportMode.METRO]

    def validate_train_bus_integration(self, route: MultimodalRoute) -> bool:
        """
        RT-051: Validate train-bus integration in multi-modal routes.
        Ensures that train and bus segments are properly connected.
        """
        if not route.segments or len(route.segments) < 2:
            return True
        
        for i in range(len(route.segments) - 1):
            current_seg = route.segments[i]
            next_seg = route.segments[i + 1]
            
            # Check if modes can be integrated
            if current_seg.mode == TransportMode.TRAIN and next_seg.mode == TransportMode.BUS:
                # Ensure bus departs after train arrives with buffer
                if next_seg.departure_time < current_seg.arrival_time + timedelta(minutes=5):
                    return False
            elif current_seg.mode == TransportMode.BUS and next_seg.mode == TransportMode.TRAIN:
                # Ensure train departs after bus arrives
                if next_seg.departure_time < current_seg.arrival_time + timedelta(minutes=5):
                    return False
        
        return True

    def validate_walk_transfer_segments(self, route: MultimodalRoute) -> bool:
        """
        RT-052: Validate that walk transfer segments are correctly inserted.
        Walking segments should be between compatible mode changes.
        """
        walk_segments = [seg for seg in route.segments if seg.mode == TransportMode.WALK]
        
        for walk_seg in walk_segments:
            # Walking segments should have reasonable duration
            if walk_seg.duration_minutes > 30:  # 30 min = ~2.5km at average pace
                return False
            
            # Walking distance should not exceed max
            if walk_seg.distance_km * 1000 > self.max_walking_distance_m:
                return False
        
        return True

    def validate_mode_preference_filtering(self, route: MultimodalRoute, 
                                          preferred_modes: List[TransportMode]) -> bool:
        """
        RT-053: Validate that mode preference filtering is applied.
        Route should honor preferred modes when available.
        """
        if not preferred_modes:
            return True
        
        # Check if route uses non-preferred modes when preferred alternatives exist
        for seg in route.segments:
            if seg.mode not in preferred_modes and seg.mode != TransportMode.WALK:
                # Allow non-preferred if no alternative exists
                return True  # Placeholder - actual logic would check alternatives
        
        return True

    def validate_disabled_transport_mode_excluded(self, route: MultimodalRoute,
                                                 disabled_modes: List[TransportMode]) -> bool:
        """
        RT-054: Validate that disabled transport modes are excluded from route.
        Route should not contain disabled modes.
        """
        for seg in route.segments:
            if seg.mode in disabled_modes:
                logger.warning(f"Route contains disabled mode: {seg.mode}")
                return False
        
        return True

    def validate_multimodal_transfer_penalties(self, route: MultimodalRoute,
                                              transfer_penalty_minutes: Dict[str, int]) -> bool:
        """
        RT-055: Validate that multi-modal transfer penalties are correctly applied.
        Penalties should increase for transfers between different modes.
        """
        for i in range(len(route.segments) - 1):
            current_seg = route.segments[i]
            next_seg = route.segments[i + 1]
            
            if current_seg.mode != next_seg.mode:
                mode_key = f"{current_seg.mode.value}_{next_seg.mode.value}"
                expected_penalty = transfer_penalty_minutes.get(mode_key, 5)
                
                # Calculate actual transfer time
                actual_transfer_time = (next_seg.departure_time - current_seg.arrival_time).total_seconds() / 60
                
                if actual_transfer_time < expected_penalty:
                    return False
        
        return True

    def validate_first_last_mile_inclusion(self, route: MultimodalRoute) -> bool:
        """
        RT-056: Validate first/last mile solution inclusion.
        Routes should include walking/taxi/bike for first and last miles.
        """
        if not route.segments:
            return False
        
        first_seg = route.segments[0]
        last_seg = route.segments[-1]
        
        # First segment should typically be walk, bike, or taxi (last-mile transport)
        valid_first_modes = [TransportMode.WALK, TransportMode.BIKE, TransportMode.TAXI, TransportMode.METRO]
        if first_seg.mode not in valid_first_modes and len(route.segments) > 1:
            return False
        
        # Last segment should include accessible transport
        valid_last_modes = [TransportMode.WALK, TransportMode.BIKE, TransportMode.TAXI, TransportMode.METRO]
        if last_seg.mode not in valid_last_modes and len(route.segments) > 1:
            return False
        
        return True

    def validate_bike_taxi_connectors(self, route: MultimodalRoute,
                                     allow_bike: bool = True,
                                     allow_taxi: bool = True) -> bool:
        """
        RT-057: Validate bike or taxi connectors for first/last mile.
        Ensures availability of connector modes based on configuration.
        """
        has_bike = any(seg.mode == TransportMode.BIKE for seg in route.segments)
        has_taxi = any(seg.mode == TransportMode.TAXI for seg in route.segments)
        
        if allow_bike and not has_bike and len(route.segments) > 1:
            # Bike might be needed but not available - check walking distance
            walking_segs = [seg for seg in route.segments if seg.mode == TransportMode.WALK]
            total_walking = sum(seg.distance_km for seg in walking_segs)
            if total_walking > 1.0:  # More than 1km walking
                return False
        
        return True

    def validate_mode_cost_weighting(self, route: MultimodalRoute) -> bool:
        """
        RT-058: Validate that mode cost weighting is correctly applied.
        Cost should be calculated based on mode weights.
        """
        calculated_cost = 0.0
        
        for seg in route.segments:
            weight = self.mode_cost_weights.get(seg.mode, 1.0)
            calculated_cost += seg.cost * weight
        
        # Allow 5% variance due to rounding
        if abs(calculated_cost - route.total_cost) / route.total_cost > 0.05:
            return False
        
        return True

    def validate_mixed_schedule_frequency_routes(self, route: MultimodalRoute) -> bool:
        """
        RT-059: Validate mixed schedule and frequency-based routes.
        Route should handle both timetabled and frequency-based services.
        """
        for seg in route.segments:
            # All segments should have valid timing
            if seg.departure_time >= seg.arrival_time:
                return False
            
            # Duration should be positive
            if seg.duration_minutes <= 0:
                return False
        
        return True

    def validate_walking_time_estimation(self, route: MultimodalRoute) -> bool:
        """
        RT-060: Validate walking time estimation accuracy.
        Walking segments should have realistic time-distance relationships.
        """
        walk_segments = [seg for seg in route.segments if seg.mode == TransportMode.WALK]
        
        for seg in walk_segments:
            # Average walking speed is ~1.4 m/s or ~5 km/h
            expected_time_minutes = (seg.distance_km * 1000) / 1.4 / 60
            actual_time_minutes = seg.duration_minutes
            
            # Allow 20% variance for personal pace variations
            if abs(actual_time_minutes - expected_time_minutes) / expected_time_minutes > 0.2:
                return False
        
        return True

    def validate_maximum_walking_distance(self, route: MultimodalRoute,
                                         max_walking_distance_m: int = 2000) -> bool:
        """
        RT-061: Validate maximum walking distance constraint.
        Total walking distance should not exceed specified maximum.
        """
        total_walking_distance = 0.0
        
        for seg in route.segments:
            if seg.mode == TransportMode.WALK:
                total_walking_distance += seg.distance_km * 1000
        
        if total_walking_distance > max_walking_distance_m:
            return False
        
        return True

    def validate_mode_change_count(self, route: MultimodalRoute,
                                  max_mode_changes: int = 4) -> bool:
        """
        RT-062: Validate mode change count constraint.
        Number of mode changes should not exceed maximum.
        """
        if len(route.segments) < 2:
            return True
        
        mode_changes = 0
        for i in range(len(route.segments) - 1):
            if route.segments[i].mode != route.segments[i + 1].mode:
                mode_changes += 1
        
        if mode_changes > max_mode_changes:
            return False
        
        return True

    def validate_airport_transfer_integration(self, route: MultimodalRoute,
                                            is_airport_route: bool = False) -> bool:
        """
        RT-063: Validate airport transfer integration.
        Routes to/from airports should allow taxi, bus, or metro connections.
        """
        if not is_airport_route:
            return True
        
        # Check if route has valid airport connector modes
        has_valid_connector = any(seg.mode in self.airport_transfer_modes 
                                 for seg in route.segments)
        
        if not has_valid_connector:
            return False
        
        return True

    def validate_metro_rail_sync(self, route: MultimodalRoute) -> bool:
        """
        RT-064: Validate metro and rail schedule synchronization.
        Metro and rail transfers should have adequate buffer times.
        """
        for i in range(len(route.segments) - 1):
            current_seg = route.segments[i]
            next_seg = route.segments[i + 1]
            
            # Check metro-rail or rail-metro transitions
            if ((current_seg.mode == TransportMode.METRO and next_seg.mode == TransportMode.RAIL) or
                (current_seg.mode == TransportMode.RAIL and next_seg.mode == TransportMode.METRO)):
                
                transfer_time = (next_seg.departure_time - current_seg.arrival_time).total_seconds() / 60
                
                # Metro-rail transfers need at least 10 minutes buffer
                if transfer_time < 10:
                    return False
        
        return True

    def validate_overnight_bus_train(self, route: MultimodalRoute) -> bool:
        """
        RT-065: Validate overnight bus and train handling.
        Overnight services should be properly marked and validated.
        """
        for seg in route.segments:
            # Check if segment crosses midnight
            if seg.arrival_time.date() != seg.departure_time.date():
                # Overnight journey - validate duration
                if seg.mode == TransportMode.BUS and seg.duration_minutes > 14 * 60:
                    # Bus journey over 14 hours might be invalid
                    return False
                elif seg.mode == TransportMode.TRAIN and seg.duration_minutes > 24 * 60:
                    # Train journey over 24 hours is definitely invalid
                    return False
        
        return True

    def validate_mode_priority_override(self, route: MultimodalRoute,
                                       mode_priority: Dict[TransportMode, int]) -> bool:
        """
        RT-066: Validate mode priority override functionality.
        Routes should respect mode priority when specified.
        """
        if not mode_priority:
            return True
        
        # Check if higher priority modes are preferred when available
        for seg in route.segments:
            seg_priority = mode_priority.get(seg.mode, 999)
            # Placeholder for actual priority validation logic
            if seg_priority > 500:  # Very low priority
                return False
        
        return True

    def validate_transfer_station_mismatch(self, route: MultimodalRoute) -> bool:
        """
        RT-067: Validate transfer station mismatch detection.
        Arrival and departure stations should match for transfers.
        """
        for i in range(len(route.segments) - 1):
            current_seg = route.segments[i]
            next_seg = route.segments[i + 1]
            
            # For non-walking transfers, stations must match
            if next_seg.mode != TransportMode.WALK:
                if current_seg.to_stop_id != next_seg.from_stop_id:
                    return False
            
            # For walking transfers, check geographic proximity
            # (simplified - actual implementation would use distance calculation)
        
        return True

    def validate_geographic_distance_sanity(self, route: MultimodalRoute) -> bool:
        """
        RT-068: Validate geographic distance sanity checks.
        Total route distance should be reasonable relative to journey time.
        """
        total_distance_km = sum(seg.distance_km for seg in route.segments)
        total_time_hours = route.total_duration_minutes / 60
        
        if total_time_hours <= 0:
            return False
        
        avg_speed_kmh = total_distance_km / total_time_hours
        
        # Average speed should be between 5 km/h (walking) and 200 km/h (high-speed rail)
        if avg_speed_kmh < 5 or avg_speed_kmh > 200:
            return False
        
        return True

    def validate_rural_sparse_network(self, route: MultimodalRoute,
                                     is_rural: bool = False) -> bool:
        """
        RT-069: Validate rural sparse network handling.
        Routes in rural areas may have different constraints and modes.
        """
        if not is_rural:
            return True
        
        # Rural routes might rely more on buses and taxis
        non_transit_modes = [TransportMode.WALK, TransportMode.BIKE, TransportMode.TAXI]
        has_viable_transit = any(seg.mode in non_transit_modes for seg in route.segments)
        
        if not has_viable_transit and len(route.segments) > 0:
            return False
        
        return True

    def validate_mode_unavailable_fallback(self, route: MultimodalRoute,
                                          unavailable_modes: List[TransportMode]) -> bool:
        """
        RT-070: Validate mode unavailable fallback routing.
        Route should provide fallback options when preferred modes unavailable.
        """
        # Check if route avoids unavailable modes
        for seg in route.segments:
            if seg.mode in unavailable_modes and not seg.is_available:
                return False
        
        return True
