"""
Train Position Estimation Engine.
Interpolates real-time train positions between stations based on delays and historical speeds.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.database.models import Stop
from routemaster_agent.database.models import TrainLiveUpdate, TrainStation

logger = logging.getLogger(__name__)

class TrainPositionEstimator:
    """
    Computes real-time train geographical coordinates (Lat/Long) 
    using linear interpolation between stations.
    """
    
    def __init__(self, db_session: Session):
        self.session = db_session

    def estimate_position(self, train_number: str) -> Optional[Dict[str, Any]]:
        """
        Estimates current lat/long coordinates for a train.
        
        Algorithm:
        1. Find last recorded station update.
        2. Resolve previous and next station sequence.
        3. Interpolate based on elapsed time vs. segment duration.
        """
        try:
            # 1. Get the latest status update for this train
            last_update = self.session.query(TrainLiveUpdate).filter(
                TrainLiveUpdate.train_number == train_number
            ).order_by(desc(TrainLiveUpdate.recorded_at)).first()
            
            if not last_update:
                return None

            # 2. Find the current segment (between sequence N and N+1)
            # Find the station this update refers to
            curr_stn_seq = last_update.sequence
            
            # Find the next station in the schedule
            next_stn = self.session.query(TrainStation).filter(
                TrainStation.train_number == train_number,
                TrainStation.sequence == curr_stn_seq + 1
            ).first()
            
            # Find the previous station (to handle the current segment)
            prev_stn = self.session.query(TrainStation).filter(
                TrainStation.train_number == train_number,
                TrainStation.sequence == curr_stn_seq
            ).first()

            if not prev_stn or not next_stn:
                # We are at the last station or data is missing
                return self._get_station_coords(prev_stn.station_code if prev_stn else None)

            # 3. Calculate Progress Percentage
            # elapsed_time = (now - arrival_at_prev_station_with_delay)
            # segment_duration = (arrival_at_next_station_with_delay - arrival_at_prev_station_with_delay)
            
            now = datetime.utcnow()
            
            # We use recorded_at as the reference for the last known report
            # If the train is halted at the station, progress is low
            if last_update.is_current_station and last_update.status == 'Halted':
                 # progress = 0 (at station)
                 return self._get_station_coords(prev_stn.station_code)
                 
            # Estimate times
            # Note: scheduled_departure info might be needed from TrainStation
            # For simplicity: progress = (now - last_update_time) / (estimated_travel_to_next)
            
            # Better logic using distance-time average (Speed = Distance / Time)
            segment_distance = (next_stn.distance_km or 0) - (prev_stn.distance_km or 0)
            if segment_distance <= 0: segment_distance = 25.0 # default gap
            
            # Speed estimate: usually 60km/h for IR trains + delay factor
            estimated_speed_kmh = 50.0 
            travel_time_min = (segment_distance / estimated_speed_kmh) * 60
            
            elapsed_min = (now - last_update.recorded_at).total_seconds() / 60
            progress = min(0.99, max(0.01, elapsed_min / travel_time_min))
            
            # 4. Geocoding and Interpolation
            coords_prev = self._get_station_coords(prev_stn.station_code)
            coords_next = self._get_station_coords(next_stn.station_code)
            
            if not coords_prev or not coords_next:
                return coords_prev or coords_next

            est_lat = coords_prev['lat'] + (coords_next['lat'] - coords_prev['lat']) * progress
            est_lon = coords_prev['lon'] + (coords_next['lon'] - coords_prev['lon']) * progress
            
            return {
                "train_number": train_number,
                "lat": est_lat,
                "lon": est_lon,
                "progress_percentage": round(progress * 100, 2),
                "last_station": prev_stn.station_name,
                "next_station": next_stn.station_name,
                "estimated_at": now.isoformat()
            }

        except Exception as e:
            logger.error(f"Error estimating position for {train_number}: {e}")
            return None

    def _get_station_coords(self, station_code: Optional[str]) -> Optional[Dict[str, float]]:
        """Helper to resolve station coords from primary stops table."""
        if not station_code:
            return None
            
        stop = self.session.query(Stop).filter(Stop.code == station_code).first()
        if stop:
            return {"lat": stop.latitude, "lon": stop.longitude}
        return None
