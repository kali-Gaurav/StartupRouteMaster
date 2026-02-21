import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from collections import defaultdict

from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.database import SessionLocal
from backend.database.models import (
    RealtimeData, TrainState, TrainLiveUpdate, TrainMaster, TrainStation
)

if TYPE_CHECKING:
    from .route_engine.engine import RailwayRouteEngine

logger = logging.getLogger(__name__)


class RealtimeEventProcessor:
    """
    Processes real-time events from TrainLiveUpdate table (API data) and RealtimeData table.
    Applies delays to the RailwayRouteEngine's overlay and propagates through route.
    
    Implements Phase 4: Realtime Overlay Integration
    Pipeline:
        1. Fetch latest TrainLiveUpdate records
        2. Apply delay propagation logic
        3. Update RealtimeOverlay (in-memory)
        4. Update TrainState (persistent)
        5. Pass updated delays to routing engine
    """

    def __init__(self, engine: 'RailwayRouteEngine', db_session_factory=SessionLocal):
        self.engine = engine
        self.db_session_factory = db_session_factory
        self._processed_updates = set()  # Track processed updates to avoid duplicates

    async def process_events(self):
        """
        Fetches new events from both RealtimeData and TrainLiveUpdate tables,
        applies delay propagation, and updates the routing engine overlay.
        """
        session = self.db_session_factory()
        try:
            logger.info("=" * 60)
            logger.info("🔄 Processing real-time events and delays...")
            
            # Process both event stream and live API data
            event_updates = self._process_realtime_data_events(session)
            api_updates = self._process_train_live_updates(session)
            
            total_updates = len(event_updates) + len(api_updates)
            
            if total_updates == 0:
                logger.debug("No new real-time events or updates")
                return
            
            logger.info(f"📊 Processing {total_updates} updates (events: {len(event_updates)}, API: {len(api_updates)})")
            
            # Apply to overlay and train state
            self._apply_updates_to_overlay(session, event_updates + api_updates)
            self._update_train_state_table(session, event_updates + api_updates)
            
            session.commit()
            logger.info(f"✓ Successfully processed {total_updates} real-time updates")
            logger.info("=" * 60)

        except Exception as e:
            session.rollback()
            logger.error(f"❌ Error processing real-time events: {e}", exc_info=True)
        finally:
            session.close()

    def _process_realtime_data_events(self, session: Session) -> List[Dict[str, Any]]:
        """
        Process events from RealtimeData table (delay, cancellation, platform_change).
        
        Args:
            session: SQLAlchemy session
            
        Returns:
            List of update dicts
        """
        try:
            # Fetch unprocessed events
            events = session.query(RealtimeData).filter(
                RealtimeData.status == 'new'
            ).order_by(RealtimeData.timestamp).all()
            
            if not events:
                return []
            
            logger.info(f"📡 Processing {len(events)} RealtimeData events...")
            
            updates = []
            for event in events:
                try:
                    update = {
                        'type': event.event_type,  # 'delay', 'cancellation', 'platform_change'
                        'trip_id': int(event.entity_id),
                        'train_number': str(event.entity_id),
                        'delay_minutes': event.data.get('delay_minutes', 0),
                        'status': event.data.get('status'),
                        'platform': event.data.get('platform_number'),
                        'timestamp': event.timestamp,
                        'source': 'event_stream'
                    }
                    updates.append(update)
                    
                    # Mark as processed
                    event.status = 'processed'
                    event.processed_at = datetime.utcnow()
                
                except Exception as e:
                    logger.error(f"Error processing event {event.id}: {e}")
            
            return updates
        
        except Exception as e:
            logger.error(f"Error fetching RealtimeData events: {e}")
            return []

    def _process_train_live_updates(self, session: Session) -> List[Dict[str, Any]]:
        """
        Process train live updates from API (most recent snapshot per train).
        This is the Phase 2 (ingestion) output that needs to propagate through routing.
        
        Args:
            session: SQLAlchemy session
            
        Returns:
            List of propagated delays ready for overlay
        """
        try:
            # Get most recent update per train
            most_recent_query = session.query(
                TrainLiveUpdate.train_number,
                TrainLiveUpdate.recorded_at
            ).group_by(TrainLiveUpdate.train_number).all()
            
            if not most_recent_query:
                return []
            
            logger.info(f"🚆 Processing {len(most_recent_query)} trains from API updates...")
            
            updates = []
            propagation_manager = self._get_propagation_manager(session)
            
            for train_number, recorded_at in most_recent_query:
                try:
                    # Get the most recent update for this train
                    latest_update = session.query(TrainLiveUpdate).filter(
                        TrainLiveUpdate.train_number == train_number,
                        TrainLiveUpdate.recorded_at == recorded_at
                    ).order_by(desc(TrainLiveUpdate.sequence)).first()
                    
                    if not latest_update:
                        continue
                    
                    # Find current station and delay
                    current_station_idx = latest_update.sequence
                    current_delay = latest_update.delay_minutes
                    
                    # Propagate delay through route
                    propagated = propagation_manager.get_propagated_delays(
                        train_number,
                        current_station_idx,
                        current_delay
                    )
                    
                    # Create updates for downstream stations
                    for station_idx, propagated_delay in propagated.items():
                        update = {
                            'type': 'delay',
                            'train_number': train_number,
                            'station_sequence': station_idx,
                            'delay_minutes': propagated_delay,
                            'status': 'delayed' if propagated_delay > 0 else 'on_time',
                            'platform': latest_update.platform,
                            'timestamp': datetime.utcnow(),
                            'source': 'api_propagation'
                        }
                        updates.append(update)
                
                except Exception as e:
                    logger.error(f"Error processing train {train_number}: {e}")
            
            return updates
        
        except Exception as e:
            logger.error(f"Error processing TrainLiveUpdates: {e}")
            return []

    def _apply_updates_to_overlay(self, session: Session, updates: List[Dict[str, Any]]):
        """
        Apply delay updates to the RealtimeOverlay (in-memory routing engine).
        This modifies trip departure times for subsequent RAPTOR runs.
        
        Args:
            session: SQLAlchemy session
            updates: List of update dicts
        """
        try:
            # Group updates by trip_id
            by_trip = defaultdict(list)
            max_delay = {}
            
            for update in updates:
                if 'trip_id' in update:
                    trip_id = update['trip_id']
                    delay = update.get('delay_minutes', 0)
                    
                    by_trip[trip_id].append(update)
                    max_delay[trip_id] = max(max_delay.get(trip_id, 0), delay)
            
            # Apply to overlay
            for trip_id, delay_minutes in max_delay.items():
                self.engine.current_overlay.apply_delay(trip_id, delay_minutes)
                logger.debug(f"Applied delay: trip {trip_id} -> +{delay_minutes}min")
            
            logger.info(f"✓ Applied {len(max_delay)} delays to RealtimeOverlay")
        
        except Exception as e:
            logger.error(f"Error applying updates to overlay: {e}")

    def _update_train_state_table(self, session: Session, updates: List[Dict[str, Any]]):
        """
        Persist train state changes to TrainState table.
        Used for historical tracking and future ML training.
        
        Args:
            session: SQLAlchemy session
            updates: List of update dicts
        """
        try:
            for update in updates:
                train_number = update.get('train_number')
                if not train_number:
                    continue
                
                # Get or create train state
                train_state = session.query(TrainState).filter(
                    TrainState.train_number == train_number
                ).first()
                
                if not train_state:
                    train_state = TrainState(
                        train_number=train_number,
                        trip_id=int(train_number) if train_number.isdigit() else hash(train_number) % 1000000
                    )
                    session.add(train_state)
                
                # Update state
                train_state.current_delay_minutes = update.get('delay_minutes', 0)
                train_state.status = update.get('status', 'on_time')
                train_state.platform_number = update.get('platform')
                train_state.current_station_code = update.get('station_code')
                train_state.last_updated = datetime.utcnow()
                train_state.last_update_source = update.get('source', 'system')
                
                logger.debug(
                    f"Updated TrainState: {train_number} -> "
                    f"delay={train_state.current_delay_minutes}min, "
                    f"status={train_state.status}"
                )
            
            logger.info(f"✓ Updated {len([u for u in updates if 'train_number' in u])} train states")
        
        except Exception as e:
            logger.error(f"Error updating TrainState: {e}")

    def _get_propagation_manager(self, session: Session):
        """Lazy import to avoid circular dependencies."""
        from backend.services.realtime_ingestion.delay_propagation import DelayPropagationManager
        return DelayPropagationManager(session)

