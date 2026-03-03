import pickle
import os
from datetime import datetime
from typing import Optional, Any, List, Tuple
import logging

from .graph import StaticGraphSnapshot
from services.multi_layer_cache import multi_layer_cache

logger = logging.getLogger(__name__)

EXPECTED_SNAPSHOT_VERSION = "v2.5" # Bump this whenever graph structure or builder logic changes

class SnapshotManager:
    """Enhanced SnapshotManager with Redis support."""

    def __init__(self, snapshot_dir: str = "snapshots"):
        self.snapshot_dir = snapshot_dir
        if not os.path.exists(self.snapshot_dir):
            os.makedirs(self.snapshot_dir, exist_ok=True)

    def _get_snapshot_path(self, date: datetime) -> str:
        filename = f"graph_snapshot_{date.strftime('%Y%m%d')}.pkl"
        return os.path.join(self.snapshot_dir, filename)

    async def save_snapshot(self, snapshot: StaticGraphSnapshot) -> Optional[str]:
        if not snapshot:
            logger.warning("Attempted to save empty snapshot")
            return None
        
        # 0. Stability Audit (TODO #6)
        # We compare against the existing snapshot if we are overwriting it.
        is_stable = await self.validate_snapshot_stability(snapshot)
        if not is_stable:
            logger.error(f"SNAPSHOT ABORTED: Stability check failed for {snapshot.date.date()} (Trip delta > 2%)")
            return None

        # Ensure version is set before saving
        snapshot.version = EXPECTED_SNAPSHOT_VERSION
        date_str = snapshot.date.strftime('%Y%m%d')
        
        # 1. Save to Redis (Phase 10: Distributed Control Plane)
        try:
            await multi_layer_cache.initialize()
            await multi_layer_cache.set_graph_snapshot(date_str, snapshot)
            logger.info(f"Snapshot for {date_str} pushed to Redis.")
            
            # Phase 2: Cache station times (TODO #15)
            await multi_layer_cache.set_station_train_times(snapshot)
            
        except Exception as re:
            logger.warning(f"Failed to save snapshot to Redis: {re}")

        # 2. Save to Disk (Local fallback)
        try:
            path = self._get_snapshot_path(snapshot.date)
            with open(path, "wb") as f:
                pickle.dump(snapshot, f)
            logger.info(f"Snapshot saved to disk: {path}")
            return path
        except Exception as e:
            logger.error(f"Error saving snapshot to disk: {e}")
            return None

    async def validate_snapshot_stability(self, new_snapshot: StaticGraphSnapshot) -> bool:
        """
        Compares new snapshot with the existing one (if any) to detect massive data loss.
        (TODO #6)
        """
        # Load existing snapshot without triggers (to avoid infinite recursion)
        date_str = new_snapshot.date.strftime('%Y%m%d')
        
        # We use a direct load from disk/redis bypassing this validation
        existing = await self._load_raw_snapshot(new_snapshot.date)
        
        if not existing:
            logger.info(f"No existing snapshot for {date_str} to compare stability.")
            return True
            
        new_trip_count = len(new_snapshot.trip_segments or {})
        old_trip_count = len(existing.trip_segments or {})
        
        if old_trip_count == 0:
            return True
            
        delta = abs(new_trip_count - old_trip_count) / old_trip_count
        logger.info(f"Stability Check: Old={old_trip_count}, New={new_trip_count}, Delta={delta:.2%}")
        
        if delta > 0.02:
            # We only abort if it's a major drop. 
            # If it's a small change or an increase, we might allow it depending on policy.
            # But the TODO says "delta > 2%", implying absolute change.
            logger.error(f"CRITICAL: Snapshot stability check failed! Trip delta {delta:.2%} exceeds 2% threshold.")
            return False
            
        return True

    async def compare_snapshots_and_log_diffs(self, today_snapshot: StaticGraphSnapshot):
        """
        Compares today's snapshot with yesterday's and logs detailed diffs.
        (TODO #8 & #9)
        """
        from datetime import timedelta
        yesterday = today_snapshot.date - timedelta(days=1)
        yesterday_snapshot = await self._load_raw_snapshot(yesterday)
        
        if not yesterday_snapshot:
            logger.info("No yesterday snapshot found to compare.")
            return

        from database.session import SessionLocal
        from database.models import SnapshotDiffLog
        
        # Calculate diffs
        today_trips = set(today_snapshot.trip_segments.keys())
        yesterday_trips = set(yesterday_snapshot.trip_segments.keys())
        
        added = len(today_trips - yesterday_trips)
        removed = len(yesterday_trips - today_trips)
        
        # Time changes (trips present in both but with different segment counts or times)
        common_trips = today_trips.intersection(yesterday_trips)
        time_changes = 0
        # Check a sample for efficiency if needed, or all if small
        for tid in list(common_trips)[:500]: 
            if len(today_snapshot.trip_segments[tid]) != len(yesterday_snapshot.trip_segments[tid]):
                time_changes += 1
        
        session = SessionLocal()
        try:
            diff_log = SnapshotDiffLog(
                date=today_snapshot.date.date(),
                trains_added=added,
                trains_removed=removed,
                time_changes=time_changes
            )
            session.add(diff_log)
            session.commit()
            logger.info(f"Logged snapshot diff: +{added}, -{removed}, ~{time_changes} changes.")
            
            # TODO #9: High Volatility Alert
            total_trips = len(today_trips)
            if yesterday_trips and total_trips > 0:
                change_pct = (added + removed) / len(yesterday_trips)
                if change_pct > 0.10:
                    logger.critical(f"HIGH VOLATILITY DETECTED: {change_pct:.2%} schedule change! (+{added}, -{removed})")
                    # Here we would call slack/telegram notify helper

        except Exception as e:
            logger.error(f"Failed to log snapshot diff: {e}")
        finally:
            session.close()

    async def _load_raw_snapshot(self, date: datetime) -> Optional[StaticGraphSnapshot]:
        """Internal helper to load snapshot without extra logic."""
        date_str = date.strftime('%Y%m%d')
        # Redis first
        try:
            await multi_layer_cache.initialize()
            snapshot = await multi_layer_cache.get_graph_snapshot(date_str)
            if snapshot: return snapshot
        except Exception: pass
        
        # Disk
        path = self._get_snapshot_path(date)
        if os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    return pickle.load(f)
            except Exception: pass
        return None

    async def load_snapshot(self, date: datetime) -> Optional[StaticGraphSnapshot]:
        """Load a previously saved snapshot for the given date (Redis first, then disk)."""
        date_str = date.strftime('%Y%m%d')
        
        # 1. Try Redis
        try:
            await multi_layer_cache.initialize()
            snapshot = await multi_layer_cache.get_graph_snapshot(date_str)
            if snapshot:
                if getattr(snapshot, 'version', None) == EXPECTED_SNAPSHOT_VERSION:
                    logger.info(f"Loaded snapshot for {date_str} from Redis.")
                    return snapshot
                else:
                    logger.warning(f"Redis snapshot version mismatch: {getattr(snapshot, 'version', 'none')} != {EXPECTED_SNAPSHOT_VERSION}")
        except Exception as re:
            logger.warning(f"Redis snapshot load failed: {re}")

        # 2. Try Disk
        path = self._get_snapshot_path(date)
        if os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    snapshot = pickle.load(f)
                
                if getattr(snapshot, 'version', None) == EXPECTED_SNAPSHOT_VERSION:
                    logger.info(f"Loaded snapshot for {date_str} from disk.")
                    return snapshot
                else:
                    logger.warning(f"Disk snapshot version mismatch: {getattr(snapshot, 'version', 'none')} != {EXPECTED_SNAPSHOT_VERSION}")
                    # Force delete stale disk snapshot to trigger fresh build on next attempt
                    try:
                        os.remove(path)
                    except Exception:
                        pass
            except (pickle.UnpicklingError, EOFError, AttributeError, Exception) as e:
                logger.error(f"Snapshot corruption detected for {date_str}: {e}. Triggering automatic rebuild.")
                # Force delete corrupted file
                try:
                    os.remove(path)
                except Exception:
                    pass
        
        return None
        
    async def save_hub_table(self, table: Any, date: datetime) -> Optional[str]:
        if not table: return None
        path = os.path.join(self.snapshot_dir, f"hub_table_{date.strftime('%Y%m%d')}.pkl")
        try:
            with open(path, "wb") as f:
                pickle.dump(table, f)
            logger.info(f"Hub table saved to {path}")
            return path
        except Exception as e:
            logger.error(f"Error saving hub table: {e}")
            return None

    async def load_hub_table(self, date: datetime) -> Optional[Any]:
        path = os.path.join(self.snapshot_dir, f"hub_table_{date.strftime('%Y%m%d')}.pkl")
        if os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    return pickle.load(f)
            except Exception as e:
                logger.error(f"Error loading hub table: {e}")
        return None

    async def update_station_in_snapshot(self, date: datetime, station_id: int, 
                                       new_departures: List[Tuple[datetime, int]], 
                                       new_arrivals: List[Tuple[datetime, int]]):
        """
        Incrementally updates a single station's data in the Redis snapshot.
        (Phase 5: TODO #43)
        """
        date_str = date.strftime('%Y%m%d')
        snapshot = await self.load_snapshot(date)
        if not snapshot:
            logger.warning(f"No snapshot found for {date_str} to update station {station_id}")
            return

        # Update in-memory
        snapshot.departures_by_stop[station_id] = sorted(new_departures, key=lambda x: x[0])
        snapshot.arrivals_by_stop[station_id] = sorted(new_arrivals, key=lambda x: x[0])
        
        # Update hour buckets
        buckets = [[] for _ in range(24)]
        for dt, tid in new_departures:
            buckets[dt.hour].append((dt, tid))
        for h in range(24): buckets[h].sort(key=lambda x: x[0])
        snapshot.station_time_index[station_id] = buckets

        # Save back to Redis and Disk
        await self.save_snapshot(snapshot)
        logger.info(f"Incrementally updated station {station_id} in {date_str} snapshot.")
