import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any, TYPE_CHECKING

from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.database import SessionLocal
from backend.database.models import RealtimeData, TrainState

if TYPE_CHECKING:
    from .route_engine.engine import RailwayRouteEngine

logger = logging.getLogger(__name__)

class RealtimeEventProcessor:
    """
    Processes real-time events from the RealtimeData table (simulating an event stream)
    and applies them to the RailwayRouteEngine's overlay and TrainState.
    Implements Phase 5: Real-Time Update Engine (Event Stream & Mutation Engine).
    """

    def __init__(self, engine: 'RailwayRouteEngine', db_session_factory=SessionLocal):
        self.engine = engine
        self.db_session_factory = db_session_factory

    async def process_events(self):
        """
        Fetches new events from the RealtimeData table and applies them.
        """
        session = self.db_session_factory()
        try:
            # Fetch unprocessed events (e.g., where status is 'new' or no 'processed_at' timestamp)
            # For simplicity, we'll process all events and then mark them
            events = session.query(RealtimeData).order_by(RealtimeData.timestamp).all()
            
            if not events:
                logger.debug("No new real-time events to process.")
                return

            logger.info(f"Processing {len(events)} real-time events...")
            
            updates_for_engine = []
            updates_for_train_state = []

            for event in events:
                # Prepare update for engine's overlay
                update_data = event.data
                update_data['type'] = event.event_type
                update_data['trip_id'] = event.entity_id # Assuming entity_id is trip_id for these events
                updates_for_engine.append(update_data)

                # Prepare update for TrainState table (for propagation/persistence)
                if event.event_type in ['delay', 'cancellation']:
                    updates_for_train_state.append({
                        'trip_id': int(event.entity_id), # Ensure trip_id is int for TrainState
                        'event_type': event.event_type,
                        'delay_minutes': event.data.get('delay_minutes', 0),
                        'status': event.data.get('status', 'delayed' if event.event_type == 'delay' else 'cancelled'),
                        'platform_number': event.data.get('platform_number'),
                        'last_updated': event.timestamp
                    })
                
                # Mark event as processed (e.g., delete or change status)
                # For this implementation, we will delete processed events
                session.delete(event)

            # Apply updates to the engine's in-memory overlay
            await self.engine.apply_realtime_updates(updates_for_engine)

            # Apply updates to the persistent TrainState table
            self._update_train_state_table(session, updates_for_train_state)
            
            session.commit()
            logger.info(f"Successfully processed {len(events)} real-time events.")

        except Exception as e:
            session.rollback()
            logger.error(f"Error processing real-time events: {e}")
        finally:
            session.close()

    def _update_train_state_table(self, session: Session, updates: List[Dict[str, Any]]):
        """
        Updates the TrainState table based on processed events.
        (Step 2: Delay Propagation - basic implementation for persistence)
        """
        for update in updates:
            trip_id = update['trip_id']
            train_state = session.query(TrainState).filter(TrainState.trip_id == trip_id).first()
            
            if not train_state:
                # Create a new TrainState entry if it doesn't exist
                train_state = TrainState(trip_id=trip_id, train_number=str(trip_id)) # Dummy train_number
                session.add(train_state)
            
            train_state.last_updated = update.get('last_updated', datetime.utcnow())

            if update['event_type'] == 'delay':
                train_state.delay_minutes = update.get('delay_minutes', train_state.delay_minutes)
                train_state.status = update.get('status', 'delayed')
            elif update['event_type'] == 'cancellation':
                train_state.status = update.get('status', 'cancelled')
                train_state.delay_minutes = 0 # No delay if cancelled

            if update.get('platform_number'):
                train_state.platform_number = update['platform_number']
            
            logger.debug(f"Updated TrainState for trip {trip_id}: Status={train_state.status}, Delay={train_state.delay_minutes}")

