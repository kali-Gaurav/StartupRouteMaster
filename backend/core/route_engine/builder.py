import asyncio
import logging
import os
import sqlite3
import uuid
import time as _time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, time
from typing import Dict, List, Set, Tuple, Optional

from sqlalchemy import and_, or_, func
from sqlalchemy.orm import joinedload, Session

from ...database import SessionLocal
from ...database.models import (
    Stop, Trip, StopTime, Route as GTFRoute,
    Calendar, CalendarDate, Transfer, TimeIndexKey, StopDepartureBucket, Segment
)
from ...utils.graph_utils import haversine_distance
from .graph import TimeDependentGraph, StaticGraphSnapshot
from .data_structures import RouteSegment, TransferConnection

logger = logging.getLogger(__name__)

class ParallelGraphBuilder:
    """Builds regional graphs in parallel"""

    def __init__(self, executor: ThreadPoolExecutor):
        self.executor = executor

    async def build_national_snapshot(self, date: datetime, graph_builder: 'GraphBuilder') -> StaticGraphSnapshot:
        """Build all regions and merge into a national snapshot"""
        # In a highly distributed system, this would trigger remote worker tasks
        # For this implementation, we use the local builder
        # TODO: Implement actual regional parallelism
        graph = await graph_builder.build_graph(date)
        return graph.snapshot if graph.snapshot else StaticGraphSnapshot(date=date)


class GraphBuilder:
    """
    Handles construction of TimeDependentGraph from database.
    Implements Phase 0 (Segment Table Population) and Phase 1 (Time-Series Indexing).
    """

    def __init__(self, executor: Optional[ThreadPoolExecutor] = None):
        self.executor = executor or ThreadPoolExecutor(max_workers=4)

    async def build_graph(self, date: datetime) -> TimeDependentGraph:
        """Build optimized time-dependent graph for the given date"""
        graph = TimeDependentGraph()

        # Use thread pool for database operations
        loop = asyncio.get_event_loop()
        db_graph = await loop.run_in_executor(
            self.executor, self._build_graph_sync, date
        )

        # Transfer data to graph
        graph.departures_by_stop = db_graph['departures']
        graph.arrivals_by_stop = db_graph['arrivals']
        graph.trip_segments = db_graph['segments']
        graph.transfer_graph = db_graph['transfers']
        graph.stop_cache = db_graph['stops']

        # Attach precomputed indexes (if present)
        graph.route_patterns = db_graph.get('route_patterns', defaultdict(list))
        graph.transfer_cache = db_graph.get('transfer_cache', {})

        # Build stop_index for bitset operations
        graph.build_stop_index()

        # Load in-memory station/stop time-index (best-effort)
        try:
            from ...station_time_index import StationTimeIndex
            graph.station_time_index = StationTimeIndex(SessionLocal())
            logger.info("Loaded StationTimeIndex into graph.")
        except Exception as e:
            logger.debug("StationTimeIndex not available: %s", e)

        return graph

    def _build_graph_sync(self, date: datetime) -> Dict:
        """Synchronous graph building (runs in thread pool)"""
        session = SessionLocal()

        try:
            # Get active service IDs for the date
            service_ids = self._get_active_service_ids(session, date)

            # Build departures and arrivals index
            departures = defaultdict(list)
            arrivals = defaultdict(list)
            segments = defaultdict(list)
            stops = {}

            # Precomputed indexes for algorithmic speedups
            route_patterns = defaultdict(list)    # stop-sequence tuple -> list of trip_ids
            transfer_cache = {}                   # (from_stop,to_stop) -> list[TransferConnection]

            # Query stop times for active services
            stop_times = session.query(StopTime).join(Trip).filter(
                Trip.service_id.in_(service_ids)
            ).options(
                joinedload(StopTime.trip),
                joinedload(StopTime.stop)
            ).order_by(StopTime.trip_id, StopTime.stop_sequence).all()

            # Group by trip
            trip_groups = defaultdict(list)
            for st in stop_times:
                trip_groups[st.trip_id].append(st)
                stops[st.stop_id] = st.stop

            # Check if we need to build indexes (Phase 1)
            try:
                # rebuild only if empty
                existing_buckets = session.query(StopDepartureBucket).count()
                build_stop_index = (existing_buckets == 0)
            except Exception:
                build_stop_index = False

            # Check if we need to populate Segment table (Phase 0)
            try:
                existing_segments = session.query(Segment).count()
                populate_segments = (existing_segments == 0)
            except Exception:
                populate_segments = False

            # Cache for time-index key ids to avoid DB churn
            _key_cache: Dict[int, int] = {}
            bucket_map: Dict[tuple, set] = {}
            
            # Batch for new segments
            new_segments_batch = []

            # Process each trip
            for trip_id, trip_stop_times in trip_groups.items():
                if len(trip_stop_times) < 2:
                    continue

                # Sort by sequence
                trip_stop_times.sort(key=lambda x: x.stop_sequence)

                # optionally assign a TimeIndexKey for this trip
                if build_stop_index:
                    try:
                        # ensure TimeIndexKey exists for this trip
                        existing_key = session.query(TimeIndexKey).filter(TimeIndexKey.entity_type == 'trip', TimeIndexKey.entity_id == str(trip_id)).first()
                        if existing_key:
                            _key_cache[trip_id] = existing_key.id
                        else:
                            newk = TimeIndexKey(entity_type='trip', entity_id=str(trip_id))
                            session.add(newk)
                            session.flush()
                            _key_cache[trip_id] = newk.id
                    except Exception:
                        pass

                # Create segments (use authoritative railway_manager distances/day-offsets when available)
                trip_segments = []
                for i in range(len(trip_stop_times) - 1):
                    current = trip_stop_times[i]
                    next_stop = trip_stop_times[i + 1]

                    # Convert departure time
                    dep_dt = self._time_to_datetime(date, current.departure_time)

                    # Build in-memory graph departures (existing behavior)
                    self_stop_id = current.stop_id
                    self_depart_dt = dep_dt
                    departures[self_stop_id].append((self_depart_dt, trip_id))

                    # if building index, add key to bucket_map for this stop/time
                    if build_stop_index:
                        key_id = _key_cache.get(trip_id)
                        if key_id is not None and current.departure_time is not None:
                            minute_of_day = current.departure_time.hour * 60 + current.departure_time.minute
                            bucket_start = minute_of_day - (minute_of_day % 15)
                            bucket_map.setdefault((current.stop_id, bucket_start), set()).add(key_id)

                    # Default arrival datetime (may be adjusted by authoritative day_offset)
                    arr_dt = self._time_to_datetime(date, next_stop.arrival_time)

                    # Attempt to enrich with railway_manager (SQLite) authoritative segment data
                    distance_km, arrival_day_offset = self._fetch_authoritative_data(trip_stop_times[0].trip, current.stop, next_stop.stop)

                    # If authoritative arrival_day_offset present, use it to compute arrival datetime
                    if arrival_day_offset is not None:
                        arr_dt = self._time_to_datetime(date + timedelta(days=arrival_day_offset), next_stop.arrival_time)
                    else:
                        # Conservative fallback for overnight times if arrival < departure
                        while arr_dt < dep_dt:
                            arr_dt += timedelta(days=1)

                    duration_minutes = int((arr_dt - dep_dt).total_seconds() // 60)

                    # Distance fallback: if not found in railway_manager, use Haversine between stop coords
                    if distance_km is None:
                        s1 = current.stop
                        s2 = next_stop.stop
                        try:
                            distance_km = haversine_distance(s1.latitude, s1.longitude, s2.latitude, s2.longitude)
                        except Exception:
                            distance_km = 0.0

                    segment = RouteSegment(
                        trip_id=trip_id,
                        departure_stop_id=current.stop_id,
                        arrival_stop_id=next_stop.stop_id,
                        departure_time=dep_dt,
                        arrival_time=arr_dt,
                        duration_minutes=duration_minutes,
                        distance_km=round(float(distance_km or 0.0), 3),
                        fare=100.0,  # TODO: compute from fares table / ML pricing
                        train_name=getattr(trip_stop_times[0].trip.route, 'long_name', 'Unknown'),
                        train_number=str(trip_id)
                    )

                    trip_segments.append(segment)

                    # Add to departures index
                    departures[current.stop_id].append((dep_dt, trip_id))

                    # Add to arrivals index
                    arrivals[next_stop.stop_id].append((arr_dt, trip_id))
                    
                    # Add to Segment table population batch
                    if populate_segments:
                        new_segment = Segment(
                            id=str(uuid.uuid4()),
                            source_station_id=str(current.stop_id), # Assumes Stop.id can be cast to string or mapped
                            dest_station_id=str(next_stop.stop_id),
                            trip_id=trip_id,
                            transport_mode='train',
                            departure_time=current.departure_time,
                            arrival_time=next_stop.arrival_time,
                            arrival_day_offset=arrival_day_offset or 0,
                            duration_minutes=duration_minutes,
                            distance_km=segment.distance_km,
                            cost=segment.fare
                        )
                        new_segments_batch.append(new_segment)

                segments[trip_id] = trip_segments

                # --- Trip pattern indexing (stop-sequence -> trips) ---
                try:
                    stop_seq = tuple([s.stop_id for s in trip_stop_times])
                    # store canonical sequence (departure stops + final arrival)
                    route_patterns.setdefault(stop_seq, []).append(trip_id)
                except Exception:
                    # keep graph build robust
                    pass

            # Build transfer graph from authoritative Transfer table (fall back to a reasonable default)
            transfers = defaultdict(list)
            all_stops = session.query(Stop).all()

            for stop in all_stops:
                stops[stop.id] = stop

                # Pull explicit transfer rules from DB (if present)
                db_transfers = session.query(Transfer).filter(
                    or_(Transfer.from_stop_id == stop.id, Transfer.to_stop_id == stop.id)
                ).all()

                if db_transfers:
                    for dbtr in db_transfers:
                        # min_transfer_time is stored in seconds in Transfer model
                        mins = max(1, (dbtr.min_transfer_time // 60) if getattr(dbtr, 'min_transfer_time', None) else 15)
                        partner_stop = dbtr.to_stop_id if dbtr.from_stop_id == stop.id else dbtr.from_stop_id
                        transfer = TransferConnection(
                            station_id=partner_stop,
                            arrival_time=date.replace(hour=0, minute=0),
                            departure_time=date.replace(hour=23, minute=59),
                            duration_minutes=mins,
                            station_name=stop.name,
                            facilities_score=(stop.facilities_json.get('walking_time_factor') if getattr(stop, 'facilities_json', None) else 0.7),
                            safety_score=min(1.0, max(0.0, (getattr(stop, 'safety_score', 50.0) / 100.0)))
                        )
                        transfers[stop.id].append(transfer)
                else:
                    # Conservative default transfer (covers cases where transfer table is empty)
                    default_duration = 15
                    transfer = TransferConnection(
                        station_id=stop.id,
                        arrival_time=date.replace(hour=0, minute=0),
                        departure_time=date.replace(hour=23, minute=59),
                        duration_minutes=default_duration,
                        station_name=stop.name,
                        facilities_score=(stop.facilities_json.get('walking_time_factor') if getattr(stop, 'facilities_json', None) else 0.7),
                        safety_score=min(1.0, max(0.0, (getattr(stop, 'safety_score', 50.0) / 100.0)))
                    )
                    transfers[stop.id].append(transfer)

            # Build transfer_cache from transfers for O(1) pair lookups
            for from_stop, tlist in transfers.items():
                for t in tlist:
                    key = (from_stop, t.station_id)
                    transfer_cache.setdefault(key, []).append(t)

            # Persist stop-level buckets (Phase 1)
            if build_stop_index and bucket_map:
                try:
                    logger.info("Persisting StopDepartureBuckets (Phase 1)...")
                    # clear any stale rows and insert fresh buckets
                    session.query(StopDepartureBucket).delete()
                    for (stop_id, bucket_start), keyset in bucket_map.items():
                        try:
                            # prefer pyroaring if available for compactness
                            from pyroaring import BitMap as _RoaringBM
                            bm = _RoaringBM(keyset)
                        except Exception:
                            # fallback to the project's BitMap shim
                            from ...station_time_index import BitMap
                            bm = BitMap(keyset)
                        blob = bm.serialize()
                        row = StopDepartureBucket(id=str(uuid.uuid4()), stop_id=stop_id, bucket_start_minute=bucket_start, bitmap=blob, trips_count=len(keyset))
                        session.add(row)
                    session.commit()
                except Exception as e:
                    logger.error("Failed to persist StopDepartureBuckets: %s", e)
                    session.rollback()

            # Persist Segments (Phase 0)
            if populate_segments and new_segments_batch:
                try:
                    logger.info(f"Persisting {len(new_segments_batch)} segments (Phase 0)...")
                    session.bulk_save_objects(new_segments_batch)
                    session.commit()
                except Exception as e:
                    logger.error("Failed to persist Segments: %s", e)
                    session.rollback()

            return {
                'departures': departures,
                'arrivals': arrivals,
                'segments': segments,
                'transfers': transfers,
                'stops': stops,
                'route_patterns': route_patterns,
                'transfer_cache': transfer_cache
            }

        finally:
            session.close()

    def _fetch_authoritative_data(self, trip, src_stop, dst_stop) -> Tuple[Optional[float], Optional[int]]:
        """Fetch distance and day_offset from railway_manager.db"""
        distance_km = None
        arrival_day_offset = None
        
        try:
            train_identifier = getattr(trip, 'trip_id', None)
            src_code = getattr(src_stop, 'code', None)
            dst_code = getattr(dst_stop, 'code', None)

            if train_identifier and src_code and dst_code:
                # Assuming the file is 2 levels up from backend/core/route_engine
                sqlite_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "railway_manager.db"))
                if os.path.exists(sqlite_path):
                    conn = sqlite3.connect(sqlite_path)
                    cur = conn.cursor()
                    # First try exact train_no match with consecutive stations
                    cur.execute(
                        "SELECT station_code, distance_from_source, day_offset, seq_no FROM train_routes WHERE train_no = ? ORDER BY seq_no",
                        (str(train_identifier),)
                    )
                    rows = cur.fetchall()
                    if rows:
                        for r_idx in range(len(rows) - 1):
                            if rows[r_idx][0] == src_code and rows[r_idx + 1][0] == dst_code:
                                distance_km = float(rows[r_idx + 1][1] - rows[r_idx][1]) if rows[r_idx + 1][1] is not None and rows[r_idx][1] is not None else None
                                arrival_day_offset = int(rows[r_idx + 1][2] or 0)
                                break

                    # Fallback: find any train that has the consecutive pair (fast path)
                    if distance_km is None:
                        cur.execute(
                            """
                            SELECT t1.train_no, (t2.distance_from_source - t1.distance_from_source) AS distance_km, t2.day_offset
                            FROM train_routes t1
                            JOIN train_routes t2 ON t1.train_no = t2.train_no AND t2.seq_no = t1.seq_no + 1
                            WHERE t1.station_code = ? AND t2.station_code = ?
                            LIMIT 1
                            """,
                            (src_code, dst_code)
                        )
                        r = cur.fetchone()
                        if r:
                            distance_km = float(r[1]) if r[1] is not None else None
                            arrival_day_offset = int(r[2] or 0)

                    conn.close()
        except Exception:
            # don't break graph build on lookup failures
            pass
            
        return distance_km, arrival_day_offset

    def _get_active_service_ids(self, session, date: datetime) -> List[int]:
        """Get active service IDs for the given date"""
        # Check calendar dates first (exceptions)
        exception_services = session.query(CalendarDate.service_id).filter(
            and_(
                CalendarDate.date == date.date(),
                CalendarDate.exception_type == 1  # Added service
            )
        ).subquery()

        removed_services = session.query(CalendarDate.service_id).filter(
            and_(
                CalendarDate.date == date.date(),
                CalendarDate.exception_type == 2  # Removed service
            )
        ).subquery()

        # Get regular services
        weekday = date.strftime('%A').lower()
        regular_services = session.query(Calendar.id).filter(
            and_(
                getattr(Calendar, weekday) == True,
                Calendar.start_date <= date.date(),
                Calendar.end_date >= date.date()
            )
        ).subquery()

        # Combine: regular services + added - removed
        active_services = session.query(
            func.coalesce(exception_services.c.service_id, regular_services.c.id)
        ).filter(
            ~func.coalesce(exception_services.c.service_id, regular_services.c.id).in_(
                session.query(removed_services.c.service_id)
            )
        ).all()

        return [s[0] for s in active_services]

    def _time_to_datetime(self, date: datetime, t: time) -> datetime:
        """Convert time to datetime on given date"""
        return datetime.combine(date.date(), t)
