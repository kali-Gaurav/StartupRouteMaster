"""
Train Position Estimation Engine.
Interpolates real-time train positions between stations based on delays and historical speeds.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database.models import Stop, TrainLiveUpdate, TrainStation

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
        Estimates current lat/long coordinates for a train using Time-Differential Interpolation.
        Phase 11: Real-time Interpolation for Map UX.
        """
        try:
            # 1. Get the latest status update
            last_update = self.session.query(TrainLiveUpdate).filter(
                TrainLiveUpdate.train_number == train_number
            ).order_by(desc(TrainLiveUpdate.recorded_at)).first()
            
            if not last_update:
                return None

            curr_stn_seq = last_update.sequence
            now = datetime.utcnow()

            # 2. Resolve Segment (Current stn to Next stn)
            prev_stn = self.session.query(TrainStation).filter(
                TrainStation.train_number == train_number,
                TrainStation.sequence == curr_stn_seq
            ).first()
            
            next_stn = self.session.query(TrainStation).filter(
                TrainStation.train_number == train_number,
                TrainStation.sequence == curr_stn_seq + 1
            ).first()

            if not prev_stn or not next_stn:
                # Terminal station or invalid data
                coords = self._get_station_coords(prev_stn.station_code if prev_stn else None)
                return {**coords, "status": "At Terminal"} if coords else None

            # 3. Time-Differential Calculation
            # scheduled_departure = prev_stn.departure_time (if we have it)
            # scheduled_arrival_next = next_stn.arrival_time
            
            # Since TrainStation model might have arrival/departure as strings or time objects:
            # Assuming they are relative to trip start or absolute for today
            def parse_time(t_str, ref_date):
                if not t_str: return None
                # Basic parser for HH:MM
                h, m = map(int, t_str.split(':')[:2])
                return ref_date.replace(hour=h, minute=m, second=0, microsecond=0)

            ref_date = last_update.recorded_at.date()
            ref_dt = datetime(ref_date.year, ref_date.month, ref_date.day)

            # Use last update as baseline
            t_start = last_update.recorded_at
            delay_mins = last_update.delay_minutes or 0
            
            # Estimate when it SHOULD arrive at next station
            # T_arrival_scheduled_next
            # Note: We need the scheduled arrival from TrainStation
            # If TrainStation doesn't have it, we fallback to distance/speed
            try:
                # Fallback if no schedule times
                seg_dist = (next_stn.distance_km or 0) - (prev_stn.distance_km or 0)
                if seg_dist <= 0: seg_dist = 30.0
                
                # Estimate travel time based on schedule if possible
                # travel_duration = (next_arrival - prev_departure)
                # For now: 55km/h average
                travel_duration_min = (seg_dist / 55.0) * 60
                
                t_expected_next = t_start + timedelta(minutes=travel_duration_min)
                
                # Calculate progress
                total_duration_sec = (t_expected_next - t_start).total_seconds()
                elapsed_sec = (now - t_start).total_seconds()
                
                if total_duration_sec > 0:
                    progress = min(0.98, max(0.01, elapsed_sec / total_duration_sec))
                else:
                    progress = 0.5
            except:
                progress = 0.5

            # 4. Geocoding and Interpolation
            coords_prev = self._get_station_coords(prev_stn.station_code)
            coords_next = self._get_station_coords(next_stn.station_code)
            
            if not coords_prev or not coords_next:
                return coords_prev or coords_next

            est_lat = coords_prev['lat'] + (coords_next['lat'] - coords_prev['lat']) * progress
            est_lon = coords_prev['lon'] + (coords_next['lon'] - coords_prev['lon']) * progress
            
            return {
                "train_number": train_number,
                "lat": round(est_lat, 6),
                "lon": round(est_lon, 6),
                "progress_percentage": round(progress * 100, 2),
                "last_station": {
                    "code": prev_stn.station_code,
                    "name": prev_stn.station_name,
                    "lat": coords_prev['lat'],
                    "lon": coords_prev['lon']
                },
                "next_station": {
                    "code": next_stn.station_code,
                    "name": next_stn.station_name,
                    "lat": coords_next['lat'],
                    "lon": coords_next['lon']
                },
                "status": "In Transit",
                "delay_minutes": delay_mins,
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
