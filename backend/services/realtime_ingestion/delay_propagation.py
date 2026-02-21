"""
Delay propagation logic for real-time routing.
Propagates delays through downstream stations based on train characteristics.

Architecture:
    Current Delay at Station A
        ↓
    Analyze Train Movement
        ↓
    Propagate Delay to B, C, D...
        ↓
    Update TrainState
        ↓
    Use in Routing Engine
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from sqlalchemy.orm import Session

from backend.database.models import TrainState
from routemaster_agent.database.models import TrainLiveUpdate, TrainStation, TrainMaster
from .parser import classify_delay_severity

logger = logging.getLogger(__name__)


class DelayPropagationManager:
    """
    Manages delay propagation through a train's route.
    Models realistic delay dynamics based on train operations.
    """
    
    # Recovery heuristics
    RECOVERY_RATE = 0.8  # Train recovers 80% of delay if no new delays
    HALT_RECOVERY = 0.2  # Per minute of halt: delay reduction (can make up time at station)
    JITTER_PERCENTAGE = 0.05  # ±5% uncertainty in propagation
    
    def __init__(self, db_session: Session):
        self.session = db_session
    
    def get_propagated_delays(
        self,
        train_number: str,
        current_station_index: int,
        current_delay: int
    ) -> Dict[int, int]:
        """
        Calculate propagated delays for all downstream stations.
        
        Args:
            train_number: Train number
            current_station_index: Current station sequence index
            current_delay: Current delay in minutes
            
        Returns:
            Dict mapping station_index -> propagated_delay_minutes
        """
        propagated = {}
        
        # Get train route
        train = self.session.query(TrainMaster).filter(
            TrainMaster.train_number == train_number
        ).first()
        
        if not train:
            logger.warning(f"Train {train_number} not found")
            return {}
        
        # Get all stations in order
        stations = self.session.query(TrainStation).filter(
            TrainStation.train_number == train_number
        ).order_by(TrainStation.sequence).all()
        
        if not stations:
            return {}
        
        current_delay_prop = current_delay  # Propagated delay value
        
        # Propagate to downstream stations
        for station in stations:
            if station.sequence <= current_station_index:
                continue  # Skip stations up to current
            
            # Calculate delay at this station
            distance_to_travel = station.distance_km  # km since last station
            halt_time = station.halt_minutes or 1  # minutes at station
            
            # Delay reduction through recovery
            recovered = self._calculate_recovery(
                current_delay_prop,
                distance_to_travel,
                halt_time
            )
            
            current_delay_prop = max(0, current_delay_prop - recovered)
            
            # Add randomness/uncertainty
            variance = int(current_delay_prop * self.JITTER_PERCENTAGE)
            current_delay_prop = max(0, current_delay_prop + (variance // 2 - variance // 4))
            
            propagated[station.sequence] = current_delay_prop
            
            logger.debug(
                f"  Station {station.sequence} ({station.station_name}): "
                f"delay={current_delay_prop}min (recovered {recovered}min)"
            )
        
        return propagated
    
    def _calculate_recovery(
        self,
        current_delay: int,
        distance_km: float,
        halt_minutes: int
    ) -> int:
        """
        Calculate how much delay train can recover between stations.
        
        Factors:
        - Train speed capability
        - Halt time available for recovery
        - Distance to next station
        
        Args:
            current_delay: Current delay in minutes
            distance_km: Distance to next station
            halt_minutes: Halt time at next station
            
        Returns:
            Minutes of delay recovered
        """
        # Assume train travels ~100 km/hour on average
        travel_time_minutes = distance_km * 60 / 100
        
        # Recovery potential
        recovery_potential = int(travel_time_minutes * self.RECOVERY_RATE)
        
        # Add halt recovery (train can leave early if ahead of schedule + delay)
        halt_recovery = int(halt_minutes * self.HALT_RECOVERY)
        
        total_recovery = recovery_potential + halt_recovery
        
        return min(total_recovery, current_delay)  # Can't recover more than delay
    
    def apply_propagated_delays(
        self,
        train_number: str,
        propagated_delays: Dict[int, int]
    ) -> int:
        """
        Update TrainState table with propagated delays.
        
        Args:
            train_number: Train number
            propagated_delays: Dict mapping station_index -> delay
            
        Returns:
            Number of records updated
        """
        updated_count = 0
        
        try:
            for station_index, delay in propagated_delays.items():
                # Get or create train state
                train_state = self.session.query(TrainState).filter(
                    TrainState.train_number == train_number
                ).first()
                
                if not train_state:
                    train_state = TrainState(
                        train_number=train_number,
                        trip_id=int(train_number)  # Simplified mapping
                    )
                    self.session.add(train_state)
                
                # Update delay
                train_state.current_delay_minutes = delay
                train_state.last_updated = datetime.utcnow()
                train_state.last_update_source = "system_propagation"
                
                updated_count += 1
            
            self.session.commit()
            logger.info(f"✓ Updated {updated_count} train states with propagated delays")
            
            return updated_count
        
        except Exception as e:
            self.session.rollback()
            logger.error(f"❌ Error applying propagated delays: {e}")
            return 0
    
    def analyze_delay_progression(
        self,
        train_number: str,
        hours_lookback: int = 24
    ) -> Dict[str, any]:
        """
        Analyze how delays have evolved over time.
        Useful for anomaly detection and pattern learning.
        
        Args:
            train_number: Train number
            hours_lookback: How far back to analyze
            
        Returns:
            Analysis dict with statistics
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_lookback)
        
        updates = self.session.query(TrainLiveUpdate).filter(
            TrainLiveUpdate.train_number == train_number,
            TrainLiveUpdate.recorded_at >= cutoff_time
        ).order_by(TrainLiveUpdate.recorded_at).all()
        
        if not updates:
            return {
                "train_number": train_number,
                "data_points": 0,
                "status": "No data",
            }
        
        # Group by station
        stations_data = {}
        for update in updates:
            station_code = update.station_code
            if station_code not in stations_data:
                stations_data[station_code] = []
            stations_data[station_code].append(update.delay_minutes)
        
        # Calculate statistics
        stats = {
            "train_number": train_number,
            "data_points": len(updates),
            "time_window_hours": hours_lookback,
            "stations_tracked": len(stations_data),
            "delays": {},
        }
        
        for station_code, delays in stations_data.items():
            delays_sorted = sorted(delays)
            stats["delays"][station_code] = {
                "min": min(delays),
                "max": max(delays),
                "avg": sum(delays) / len(delays),
                "median": delays_sorted[len(delays) // 2],
                "latest": delays[-1],
                "trend": "improving" if delays[-1] < delays[0] else "worsening",
            }
        
        return stats
    
    def detect_anomalies(
        self,
        train_number: str,
        threshold_std_devs: float = 2.0
    ) -> List[Dict[str, any]]:
        """
        Detect anomalous delays (e.g., unusual stops, infrastructure issues).
        
        Args:
            train_number: Train number
            threshold_std_devs: Z-score threshold for anomaly
            
        Returns:
            List of anomalies detected
        """
        # Get recent delays for this train
        recent_updates = self.session.query(TrainLiveUpdate).filter(
            TrainLiveUpdate.train_number == train_number,
            TrainLiveUpdate.recorded_at >= datetime.utcnow() - timedelta(days=1)
        ).all()
        
        if len(recent_updates) < 3:
            return []
        
        # Calculate mean and std dev
        delays = [u.delay_minutes for u in recent_updates]
        mean = sum(delays) / len(delays)
        variance = sum((d - mean) ** 2 for d in delays) / len(delays)
        std_dev = variance ** 0.5
        
        if std_dev == 0:
            return []
        
        # Detect anomalies
        anomalies = []
        for update in recent_updates:
            z_score = abs((update.delay_minutes - mean) / std_dev)
            
            if z_score >= threshold_std_devs:
                anomalies.append({
                    "train": train_number,
                    "station": update.station_name,
                    "delay": update.delay_minutes,
                    "z_score": z_score,
                    "severity": classify_delay_severity(update.delay_minutes),
                    "time": update.recorded_at,
                })
        
        logger.info(f"🔍 {train_number}: Detected {len(anomalies)} anomalies")
        
        return anomalies


def create_propagation_manager(db_session: Session) -> DelayPropagationManager:
    """Factory function to create DelayPropagationManager."""
    return DelayPropagationManager(db_session)
