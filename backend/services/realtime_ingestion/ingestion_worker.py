"""
Live ingestion worker service.
Runs in background, fetches train data from API, stores in database.
Implements Phase 2 of the real-time pipeline.

Architecture:
    Background Thread/Task
        ↓
    Get Active Train List
        ↓
    Fetch from API (with retries)
        ↓
    Parse Responses
        ↓
    Store in TrainLiveUpdate table
        ↓
    Sleep 5-10 minutes
        ↓
    Repeat
"""

import asyncio
import logging
import threading
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
import schedule

from ...database import SessionLocal
from ...database.models import TrainLiveUpdate, TrainMaster
from .api_client import RappidAPIClient, AsyncRappidAPIClient, get_active_trains
from .parser import extract_train_update

logger = logging.getLogger(__name__)


class LiveIngestionWorker:
    """
    Background worker for live train data ingestion.
    Fetches data every N minutes and stores in database.
    """
    
    def __init__(
        self,
        db_session_factory=SessionLocal,
        interval_minutes: int = 5,
        use_async: bool = False,
        batch_size: int = 50,
        max_workers: int = 10
    ):
        """
        Initialize ingestion worker.
        
        Args:
            db_session_factory: SQLAlchemy session factory
            interval_minutes: Fetch interval in minutes
            use_async: Use async API client for concurrent requests
            batch_size: Number of trains to fetch per batch
            max_workers: Max concurrent workers for async mode
        """
        self.db_session_factory = db_session_factory
        self.interval_minutes = interval_minutes
        self.use_async = use_async
        self.batch_size = batch_size
        self.max_workers = max_workers
        
        self.api_client = RappidAPIClient() if not use_async else None
        self.async_api_client = AsyncRappidAPIClient(max_concurrent=max_workers) if use_async else None
        
        self.running = False
        self.worker_thread: Optional[threading.Thread] = None
        self.stats = {
            "fetches": 0,
            "updates_stored": 0,
            "errors": 0,
            "last_run": None,
            "last_error": None,
        }
    
    def start(self):
        """Start the background ingestion worker."""
        if self.running:
            logger.warning("⚠️ Ingestion worker already running")
            return
        
        self.running = True
        self.worker_thread = threading.Thread(
            target=self._run_scheduler,
            daemon=True,
            name="RealtimeIngestionWorker"
        )
        self.worker_thread.start()
        logger.info(f"🚀 Live ingestion worker started (interval: {self.interval_minutes}min)")
    
    def stop(self):
        """Stop the background ingestion worker."""
        self.running = False
        if self.api_client:
            self.api_client.close()
        logger.info("🛑 Live ingestion worker stopped")
    
    def _run_scheduler(self):
        """Run scheduled tasks in background thread."""
        schedule.every(self.interval_minutes).minutes.do(self._ingest_cycle)
        
        logger.info(f"📅 Scheduler running with {self.interval_minutes}min interval")
        
        while self.running:
            schedule.run_pending()
            threading.Event().wait(1)  # Check every 1 second
    
    def _ingest_cycle(self):
        """Single ingestion cycle: fetch all trains and store updates."""
        try:
            session = self.db_session_factory()
            
            logger.info("=" * 60)
            logger.info(f"🔄 Starting ingestion cycle at {datetime.now().isoformat()}")
            
            # Get active trains
            train_numbers = get_active_trains(session)
            
            if not train_numbers:
                logger.warning("⚠️ No active trains found")
                return
            
            logger.info(f"📊 Fetching data for {len(train_numbers)} trains")
            
            # Fetch data
            if self.use_async:
                updates_count = self._ingest_async(session, train_numbers)
            else:
                updates_count = self._ingest_sync(session, train_numbers)
            
            self.stats["fetches"] += 1
            self.stats["updates_stored"] += updates_count
            self.stats["last_run"] = datetime.now()
            
            logger.info(f"✓ Ingestion cycle complete: {updates_count} updates stored")
            logger.info("=" * 60)
        
        except Exception as e:
            logger.error(f"❌ Ingestion cycle failed: {e}", exc_info=True)
            self.stats["errors"] += 1
            self.stats["last_error"] = str(e)
    
    def _ingest_sync(self, session: Session, train_numbers: List[str]) -> int:
        """Synchronous ingestion of train data."""
        total_updates = 0
        
        for i in range(0, len(train_numbers), self.batch_size):
            batch = train_numbers[i:i + self.batch_size]
            logger.info(f"  📦 Processing batch {i//self.batch_size + 1}: {len(batch)} trains")
            
            for train_no in batch:
                try:
                    updates = self._fetch_and_store_train(session, train_no)
                    total_updates += updates
                
                except Exception as e:
                    logger.error(f"  ❌ Error processing train {train_no}: {e}")
        
        return total_updates
    
    def _ingest_async(self, session: Session, train_numbers: List[str]) -> int:
        """Asynchronous ingestion of train data."""
        # Run async code in event loop
        if not asyncio.get_event_loop().is_running():
            return asyncio.run(self._ingest_async_internal(session, train_numbers))
        else:
            # If loop already running, use sync fallback
            logger.warning("⚠️ Event loop already running, using sync ingestion")
            return self._ingest_sync(session, train_numbers)
    
    async def _ingest_async_internal(self, session: Session, train_numbers: List[str]) -> int:
        """Internal async ingestion implementation."""
        total_updates = 0
        
        for i in range(0, len(train_numbers), self.batch_size):
            batch = train_numbers[i:i + self.batch_size]
            logger.info(f"  📦 Async batch {i//self.batch_size + 1}: {len(batch)} trains")
            
            # Fetch all trains in batch concurrently
            results = await self.async_api_client.fetch_multiple_trains(batch)
            
            # Store results
            for train_no, response in results.items():
                try:
                    if response:
                        updates = self._store_train_updates(session, train_no, response)
                        total_updates += updates
                
                except Exception as e:
                    logger.error(f"  ❌ Error storing train {train_no}: {e}")
        
        return total_updates
    
    def _fetch_and_store_train(self, session: Session, train_number: str) -> int:
        """
        Fetch single train and store updates.
        
        Args:
            session: SQLAlchemy session
            train_number: Train number to fetch
            
        Returns:
            Number of updates stored
        """
        try:
            response = self.api_client.fetch_train_status(train_number)
            if response:
                return self._store_train_updates(session, train_number, response)
            return 0
        
        except Exception as e:
            logger.error(f"Error fetching train {train_number}: {e}")
            return 0
    
    def _store_train_updates(self, session: Session, train_number: str, response: dict) -> int:
        """
        Parse API response and store in database.
        
        Args:
            session: SQLAlchemy session
            train_number: Train number
            response: API response dict
            
        Returns:
            Number of records stored
        """
        try:
            updates = extract_train_update(response, train_number)
            
            if not updates:
                logger.debug(f"No updates for train {train_number}")
                return 0
            
            # Bulk insert
            for update in updates:
                record = TrainLiveUpdate(**update)
                session.add(record)
            
            session.commit()
            logger.debug(f"  ✓ Stored {len(updates)} updates for train {train_number}")
            
            return len(updates)
        
        except Exception as e:
            session.rollback()
            logger.error(f"Error storing updates for train {train_number}: {e}")
            return 0
    
    def get_stats(self) -> dict:
        """Get worker statistics."""
        return self.stats.copy()


# Global worker instance
_ingestion_worker: Optional[LiveIngestionWorker] = None


def start_ingestion_service(
    interval_minutes: int = 5,
    use_async: bool = False,
    batch_size: int = 50
) -> LiveIngestionWorker:
    """
    Start the global live ingestion service.
    
    Args:
        interval_minutes: Fetch interval in minutes
        use_async: Use async API client
        batch_size: Batch size for processing
        
    Returns:
        The worker instance
    """
    global _ingestion_worker
    
    if _ingestion_worker is not None and _ingestion_worker.running:
        logger.warning("Ingestion service already running")
        return _ingestion_worker
    
    _ingestion_worker = LiveIngestionWorker(
        interval_minutes=interval_minutes,
        use_async=use_async,
        batch_size=batch_size
    )
    _ingestion_worker.start()
    
    return _ingestion_worker


def stop_ingestion_service():
    """Stop the global ingestion service."""
    global _ingestion_worker
    
    if _ingestion_worker:
        _ingestion_worker.stop()
        _ingestion_worker = None


def get_ingestion_worker() -> Optional[LiveIngestionWorker]:
    """Get the global ingestion worker instance."""
    return _ingestion_worker
