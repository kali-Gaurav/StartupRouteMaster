from dataclasses import dataclass, field
from datetime import datetime, timedelta, date
from typing import Any, Dict, List, Tuple, Optional, Set, Union
from collections import defaultdict
import logging
import numpy as np
import os
import json
import time
import pickle
import zlib
from bisect import bisect_left

from database.models import Stop
from core.data_structures import RouteSegment, TransferConnection, Route

logger = logging.getLogger(__name__)

class MemMapManager:
    @staticmethod
    def save_array(name: str, array: np.ndarray) -> str:
        from database.config import Config
        os.makedirs(Config.MEMMAP_DIR, exist_ok=True)
        timestamp = int(time.time() * 1000)
        filename = f"{name}_{timestamp}.dat"
        path = os.path.join(Config.MEMMAP_DIR, filename)
        meta_path = os.path.join(Config.MEMMAP_DIR, f"{name}.meta")
        
        # [Gap 17] Garbage Collection: Keep only last 3 versions
        try:
            files = sorted([f for f in os.listdir(Config.MEMMAP_DIR) if f.startswith(name + "_") and f.endswith(".dat")])
            for old_file in files[:-3]:
                old_path = os.path.join(Config.MEMMAP_DIR, old_file)
                try: 
                    if os.path.exists(old_path): os.remove(old_path)
                except OSError as e:
                    # Log but continue - don't crash the save process
                    logger.debug(f"MemMap GC: Could not remove {old_file} (likely locked): {e}")
        except Exception as e:
            logger.warning(f"MemMap GC failed: {e}")

        dtype_desc = array.dtype.descr if array.dtype.names else str(array.dtype)
        
        with open(meta_path, 'w') as f:
            json.dump({
                "latest_file": filename,
                "shape": array.shape, 
                "dtype": dtype_desc,
                "created_at": timestamp
            }, f)

        for attempt in range(5):
            try:
                fp = np.memmap(path, dtype=array.dtype, mode='w+', shape=array.shape)
                fp[:] = array[:]
                fp.flush()
                del fp 
                return path
            except OSError:
                time.sleep(0.5)
        return path

    @staticmethod
    def load_array(name: str, mode: str = 'r') -> Optional[np.ndarray]:
        from database.config import Config
        meta_path = os.path.join(Config.MEMMAP_DIR, f"{name}.meta")
        if not os.path.exists(meta_path): 
            logger.debug(f"MemMap: No meta file for {name} at {meta_path}")
            return None
            
        try:
            with open(meta_path, 'r') as f:
                meta = json.load(f)
            
            latest_file = meta.get("latest_file")
            if not latest_file: return None
            
            # [Task 8] Robust Path Construction
            path = os.path.join(Config.MEMMAP_DIR, os.path.basename(latest_file))
            if not os.path.exists(path): 
                logger.warning(f"MemMap: Meta exists but data file missing: {path}")
                return None

            def _restore_tuples(obj):
                if isinstance(obj, list):
                    return tuple(_restore_tuples(i) for i in obj)
                return obj

            dtype_raw = meta.get('dtype')
            if isinstance(dtype_raw, list):
                dtype_obj = np.dtype(_restore_tuples(dtype_raw))
            else:
                dtype_obj = np.dtype(dtype_raw)
                
            shape = tuple(meta.get('shape', ()))
            if not shape: return None
            
            # [Task 8] Integrity check: verify file size matches expected shape
            expected_size = int(np.prod(shape)) * dtype_obj.itemsize

            for attempt in range(3):
                try:
                    if os.path.exists(path) and os.path.getsize(path) != expected_size:
                        logger.warning(f"MemMap: Integrity check failed for {name}. Size mismatch for {path}")
                        return None
                        
                    mmap = np.memmap(path, dtype=dtype_obj, mode=mode, shape=shape)
                    return mmap
                except (OSError, ValueError) as e:
                    logger.debug(f"MemMap Load Attempt {attempt+1} failed for {name}: {e}")
                    time.sleep(0.1)
        except Exception as e:
            logger.error(f"Error loading {name} memmap: {e}")
        return None

@dataclass
class StaticGraphSnapshot:
    date: datetime
    version: str = "v10.0" # [Issue 6] Pinned version for cache stability
    
    # Vectorized Core
    _departures_data: Optional[np.ndarray] = None
    _departures_index: Optional[np.ndarray] = None
    _arrivals_data: Optional[np.ndarray] = None
    _arrivals_index: Optional[np.ndarray] = None
    _stop_id_map: Dict[int, int] = field(default_factory=dict)

    _pattern_deps_data: Optional[np.ndarray] = None
    _pattern_deps_index: Optional[np.ndarray] = None

    _segments_data: Optional[np.ndarray] = None
    _segments_index: Optional[np.ndarray] = None
    _trip_id_map: Dict[int, int] = field(default_factory=dict)
    _trip_reachability_bitset: Optional[np.ndarray] = None

    _transfers_data: Optional[np.ndarray] = None
    _transfers_index: Optional[np.ndarray] = None
    _transfer_stop_map: Dict[int, int] = field(default_factory=dict)

    # TBR Structures (Additive)
    tbr_trip_nodes: Optional[np.ndarray] = None
    tbr_trip_index: Dict[int, Tuple[int, int]] = field(default_factory=dict)
    tbr_stop_index: Dict[int, List[Tuple[int, int]]] = field(default_factory=dict)

    # Metadata & Caches
    stop_cache: Dict[int, Stop] = field(default_factory=dict)
    city_clusters: Dict[str, List[int]] = field(default_factory=lambda: defaultdict(list))
    hub_direct_adj: Dict[int, Set[int]] = field(default_factory=lambda: defaultdict(set))
    station_time_index: Dict[int, List[List[Tuple[datetime, int]]]] = field(default_factory=lambda: defaultdict(lambda: [[] for _ in range(24)]))
    
    # [Task 1] Mapping for Real-time Propagation
    trip_to_train: Dict[int, str] = field(default_factory=dict)
    train_to_trips: Dict[str, List[int]] = field(default_factory=lambda: defaultdict(list))
    
    # Legacy fallbacks (For Builder process)
    departures_by_stop: Dict[int, List[Tuple[datetime, int]]] = field(default_factory=lambda: defaultdict(list))
    arrivals_by_stop: Dict[int, List[Tuple[datetime, int]]] = field(default_factory=lambda: defaultdict(list))
    trip_segments: Dict[int, List[RouteSegment]] = field(default_factory=lambda: defaultdict(list))
    transfer_graph: Dict[int, List[TransferConnection]] = field(default_factory=lambda: defaultdict(list))
    train_path: Dict[int, List[Dict[str, Any]]] = field(default_factory=lambda: defaultdict(list))
    station_schedule: Dict[int, List[Dict[str, Any]]] = field(default_factory=lambda: defaultdict(list))
    
    # Missing fields for builder compatibility
    route_patterns: Dict[Tuple[int, ...], List[int]] = field(default_factory=dict)
    stop_index: Dict[int, int] = field(default_factory=dict)
    reliability_scores: Dict[Tuple[int, int], float] = field(default_factory=dict)
    station_ids_by_trip: Dict[int, Set[int]] = field(default_factory=lambda: defaultdict(set))
    coordinate_matrix: Optional[np.ndarray] = None
    stop_id_to_idx: Dict[int, int] = field(default_factory=dict)
    idx_to_stop_id: List[int] = field(default_factory=list)

    def pattern_for_trip(self, trip_id: int) -> Tuple[int, ...]:
        segs = self.trip_segments.get(trip_id, [])
        return tuple(seg.departure_stop_id for seg in segs) + ((segs[-1].arrival_stop_id,) if segs else ())

    def vectorize(self, tbr_data: Optional[Dict] = None):
        ts = int(self.date.timestamp())
        
        # 1. Departures & Patterns
        if self.departures_by_stop:
            all_deps = []; all_p_deps = []
            stop_ids = sorted(self.departures_by_stop.keys())
            idx = np.zeros((len(stop_ids), 2), dtype=np.int32)
            p_idx = np.zeros((len(stop_ids), 2), dtype=np.int32)
            off = 0; p_off = 0
            self._stop_id_map = {sid: i for i, sid in enumerate(stop_ids)}
            
            for i, sid in enumerate(stop_ids):
                deps = self.departures_by_stop[sid]
                idx[i] = [off, len(deps)]
                p_map = defaultdict(list)
                for dt, tid in deps:
                    all_deps.append([int(dt.timestamp()), tid])
                    pid = hash(self.pattern_for_trip(tid)) & 0x7FFFFFFF
                    p_map[pid].append([pid, int(dt.timestamp()), tid])
                off += len(deps)
                
                p_count = 0
                for pid in sorted(p_map.keys()):
                    entries = p_map[pid]
                    all_p_deps.extend(entries)
                    p_count += len(entries)
                p_idx[i] = [p_off, p_count]
                p_off += p_count
            
            MemMapManager.save_array(f"deps_{ts}", np.array(all_deps, dtype=np.int64))
            self._departures_data = MemMapManager.load_array(f"deps_{ts}")
            MemMapManager.save_array(f"deps_idx_{ts}", idx)
            self._departures_index = MemMapManager.load_array(f"deps_idx_{ts}")
            
            MemMapManager.save_array(f"p_deps_{ts}", np.array(all_p_deps, dtype=np.int64))
            self._pattern_deps_data = MemMapManager.load_array(f"p_deps_{ts}")
            MemMapManager.save_array(f"p_deps_idx_{ts}", p_idx)
            self._pattern_deps_index = MemMapManager.load_array(f"p_deps_idx_{ts}")

        # 2. Segments & Bitsets
        if self.trip_segments:
            all_segs = []
            tids = sorted(self.trip_segments.keys())
            t_idx = np.zeros((len(tids), 2), dtype=np.int32)
            t_off = 0
            self._trip_id_map = {tid: i for i, tid in enumerate(tids)}
            
            NUM_STOPS = 32768
            BITSET_WORDS = (NUM_STOPS // 64) + 1
            reach_bits = np.zeros((len(tids), BITSET_WORDS), dtype=np.uint64)

            for i, tid in enumerate(tids):
                segs = self.trip_segments[tid]
                t_idx[i] = [t_off, len(segs)]
                for s in segs:
                    all_segs.append([
                        tid, s.departure_stop_id, s.arrival_stop_id, 
                        int(s.departure_time.timestamp()), int(s.arrival_time.timestamp()), 
                        int(s.distance_km * 1000), s.service_mask, s.stop_sequence
                    ])
                    for sid in [s.departure_stop_id, s.arrival_stop_id]:
                        if sid < NUM_STOPS: reach_bits[i, sid // 64] |= np.uint64(1) << np.uint64(sid % 64)
                t_off += len(segs)
            
            MemMapManager.save_array(f"segs_{ts}", np.array(all_segs, dtype=np.int64))
            self._segments_data = MemMapManager.load_array(f"segs_{ts}")
            MemMapManager.save_array(f"segs_idx_{ts}", t_idx)
            self._segments_index = MemMapManager.load_array(f"segs_idx_{ts}")
            MemMapManager.save_array(f"reach_{ts}", reach_bits)
            self._trip_reachability_bitset = MemMapManager.load_array(f"reach_{ts}")

        # 3. Transformed Transfers (Audit: Added Vectorization)
        if self.transfer_graph:
            all_transfers = []
            stop_ids = sorted(self.transfer_graph.keys())
            t_idx = np.zeros((len(stop_ids), 2), dtype=np.int32)
            t_off = 0
            self._transfer_stop_map = {sid: i for i, sid in enumerate(stop_ids)}
            
            # [Task 1] Build Trip-to-Train mappings for faster Overlay sync
            for tid, segs in self.trip_segments.items():
                if segs:
                    t_no = segs[0].train_number
                    self.trip_to_train[tid] = t_no
                    self.train_to_trips[t_no].append(tid)
            
            # Type map: WALK=0, METRO=1, TAXI=2, SHUTTLE=3
            t_type_map = {"WALK": 0, "METRO": 1, "TAXI": 2, "SHUTTLE": 3}

            for i, sid in enumerate(stop_ids):
                edges = self.transfer_graph[sid]
                t_idx[i] = [t_off, len(edges)]
                for e in edges:
                    # [Audit] Handling both TransferEdge and legacy dicts
                    to_sid = getattr(e, 'to_stop_id', e.get('to_stop_id') if isinstance(e, dict) else 0)
                    dur = getattr(e, 'duration_minutes', e.get('duration_minutes', 15) if isinstance(e, dict) else 15)
                    multi = 1 if getattr(e, 'is_multi_station', False) else 0
                    t_type_str = getattr(e, 'transfer_type', "WALK")
                    t_type_idx = t_type_map.get(t_type_str, 0)
                    
                    all_transfers.append([to_sid, dur, multi, t_type_idx])
                t_off += len(edges)
            
            MemMapManager.save_array(f"transfers_{ts}", np.array(all_transfers, dtype=np.int32))
            self._transfers_data = MemMapManager.load_array(f"transfers_{ts}")
            MemMapManager.save_array(f"transfers_idx_{ts}", t_idx)
            self._transfers_index = MemMapManager.load_array(f"transfers_idx_{ts}")

        # 4. TBR Data
        if tbr_data:
            self.tbr_trip_nodes = tbr_data.get('tbr_trip_nodes')
            self.tbr_trip_index = tbr_data.get('tbr_trip_index', {})
            self.tbr_stop_index = tbr_data.get('tbr_stop_index', {})

        logger.info(f"🚀 Vectorization Complete for {self.date.date()}.")

    version: str = "v10.0" 

class RealtimeOverlay:
    def __init__(self):
        self.delays: Dict[int, int] = {}
        self.cancellations: Set[int] = set()
        self.platform_changes: Dict[Tuple[int, int], str] = {}
        self.version: int = 0

    def get_trip_delay(self, tid: int) -> int: return self.delays.get(tid, 0)
    def is_cancelled(self, tid: int) -> bool: return tid in self.cancellations

    async def sync_with_db(self, db, travel_date: date, snapshot: Optional['StaticGraphSnapshot'] = None):
        """
        [Task 1.3] Consolidated Real-time Sync.
        Fetches cancellations and delays mapping them to Trip IDs.
        """
        from sqlalchemy import text
        from datetime import datetime, timedelta
        ds = travel_date.strftime("%Y-%m-%d")
        try:
            # 1. Cancellations
            self.cancellations = set()
            rows = db.execute(text("SELECT train_no FROM cancelled_trains WHERE travel_date = :dt"), {"dt": ds}).fetchall()
            # If we have a snapshot, map train_no to trip_ids
            for r in rows:
                t_no = str(r[0])
                if snapshot:
                    for tid in snapshot.train_to_trips.get(t_no, []):
                        self.cancellations.add(tid)
                else:
                    try: self.cancellations.add(int(t_no))
                    except: pass
            
            # 2. GTFS Scheduled Cancellations
            gtfs_rows = db.execute(text("""
                SELECT t.id 
                FROM calendar_dates cd 
                JOIN trips t ON cd.service_id = t.service_id 
                WHERE cd.date = :dt AND cd.exception_type = 2
            """), {"dt": ds}).fetchall()
            for r in gtfs_rows: self.cancellations.add(int(r[0]))

            # 3. Delays (Fresh updates only - last 4 hours)
            fresh_cutoff = datetime.utcnow() - timedelta(hours=4)
            delay_rows = db.execute(text("""
                SELECT train_number, delay_minutes 
                FROM train_live_updates 
                WHERE recorded_at >= :cutoff 
                ORDER BY recorded_at DESC
            """), {"cutoff": fresh_cutoff}).fetchall()
            
            live_train_delays = {}
            for row in delay_rows:
                if row[0] not in live_train_delays:
                    live_train_delays[row[0]] = int(row[1])
            
            # Apply to delays mapping
            self.delays = {}
            if snapshot:
                for t_no, d in live_train_delays.items():
                    for tid in snapshot.train_to_trips.get(str(t_no), []):
                        self.delays[tid] = d
            
            self.version += 1
        except Exception as e: 
            logger.warning(f"Overlay sync failed: {e}")

class TimeDependentGraph:
    def __init__(self, snapshot: Optional[StaticGraphSnapshot] = None, overlay: Optional[RealtimeOverlay] = None):
        self.snapshot = snapshot
        self.overlay = overlay or RealtimeOverlay()
        self.stop_cache = snapshot.stop_cache if snapshot else {}

    def get_stop_by_code(self, code: str) -> Optional[Stop]:
        c = code.upper().strip()
        for s in self.stop_cache.values():
            if s.code == c: return s
        return None

    def can_reach_destination(self, tid: int, dst_id: int) -> bool:
        if not self.snapshot or self.snapshot._trip_reachability_bitset is None: return True
        t_idx = self.snapshot._trip_id_map.get(tid)
        if t_idx is None or dst_id >= 32768: return True
        return bool(self.snapshot._trip_reachability_bitset[t_idx, dst_id // 64] & (np.uint64(1) << np.uint64(dst_id % 64)))

    @staticmethod
    def safe_fromtimestamp(ts: Union[int, float]) -> datetime:
        try:
            capped_ts = min(32535215999, max(315532800, int(ts)))
            return datetime.fromtimestamp(capped_ts)
        except: return datetime(1980, 1, 1)

    def get_pattern_departures(self, stop_id: int, after_time: datetime, lookahead: int = 1440) -> Dict[int, List[Tuple[datetime, int]]]:
        results = defaultdict(list)
        if not self.snapshot or self.snapshot._pattern_deps_data is None:
            base = self.get_departures_from_stop(stop_id, after_time, lookahead)
            for dt, tid in base:
                pid = hash(str(tid)) & 0x7FFFFFFF
                results[pid].append((dt, tid))
            return results
        s_idx = self.snapshot._stop_id_map.get(stop_id)
        if s_idx is None: return {}
        off, count = self.snapshot._pattern_deps_index[s_idx]
        data = self.snapshot._pattern_deps_data[off : off + count]
        after_ts = int(after_time.timestamp()); limit_ts = after_ts + (lookahead * 60)
        for pid, ts, tid in data:
            if after_ts <= ts <= limit_ts:
                if not self.overlay.is_cancelled(tid):
                    eff_ts = ts + (self.overlay.get_trip_delay(tid) * 60)
                    if after_ts <= eff_ts <= limit_ts:
                        results[int(pid)].append((self.safe_fromtimestamp(eff_ts), int(tid)))
        return results

    def get_departures_from_stop(self, sid: int, after: datetime, lookahead: int = 1440) -> List[Tuple[datetime, int]]:
        if not self.snapshot or self.snapshot._departures_data is None: return []
        s_idx = self.snapshot._stop_id_map.get(sid)
        if s_idx is None: return []
        off, count = self.snapshot._departures_index[s_idx]
        data = self.snapshot._departures_data[off : off + count]
        after_ts = int(after.timestamp()); limit_ts = after_ts + (lookahead * 60)
        res = []
        for ts, tid in data:
            if after_ts <= ts <= limit_ts:
                if not self.overlay.is_cancelled(tid):
                    eff_ts = ts + (self.overlay.get_trip_delay(tid) * 60)
                    if after_ts <= eff_ts <= limit_ts:
                        res.append((self.safe_fromtimestamp(eff_ts), int(tid)))
        return sorted(res, key=lambda x: x[0])

    def get_transfers_from_stop(self, sid: int, arr: datetime, min_transfer_time: int = 15, incoming_trip_id: int = None) -> List[TransferConnection]:
        feasible = []
        # 1. In-station transfer (buffer time)
        if sid in self.stop_cache:
            s = self.stop_cache[sid]
            feasible.append(TransferConnection(sid, s.code, datetime.min, datetime.max, max(min_transfer_time, 15), s.name, is_multi_station=False))
            
        # 2. Vectorized inter-station/complex transfers
        if self.snapshot and self.snapshot._transfers_data is not None:
            t_idx = self.snapshot._transfer_stop_map.get(sid)
            if t_idx is not None:
                off, count = self.snapshot._transfers_index[t_idx]
                t_type_rev = {0: "WALK", 1: "METRO", 2: "TAXI", 3: "SHUTTLE"}
                
                for row in self.snapshot._transfers_data[off : off + count]:
                    target_sid = int(row[0])
                    dur = int(row[1])
                    is_multi = bool(row[2])
                    t_type = t_type_rev.get(int(row[3]), "WALK")
                    
                    if min_transfer_time <= dur <= 1440:
                        target = self.stop_cache.get(target_sid)
                        feasible.append(TransferConnection(
                            target_sid, 
                            target.code if target else "", 
                            datetime.min, datetime.max, 
                            dur, 
                            target.name if target else f"Stop {target_sid}",
                            is_multi_station=is_multi,
                            transfer_type=t_type
                        ))
        return feasible

    def get_trip_segments_raw(self, tid: int) -> Optional[np.ndarray]:
        if self.snapshot and self.snapshot._segments_data is not None:
            t_idx = self.snapshot._trip_id_map.get(tid)
            if t_idx is None: return None
            off, count = self.snapshot._segments_index[t_idx]
            return self.snapshot._segments_data[off : off + count]
        return None

    def get_trip_segments(self, tid: int) -> List[RouteSegment]:
        raw = self.get_trip_segments_raw(tid)
        if raw is None: return []
        delay = self.overlay.get_trip_delay(tid) * 60
        res = []
        for row in raw:
            # [Task 9 Standardized Duration]
            duration = int((row[4] - row[3]) // 60)
            if duration < 0: duration += 1440 # Handle midnight wraparound if timestamp is time-of-day
            
            res.append(RouteSegment(
                trip_id=int(row[0]), 
                departure_stop_id=int(row[1]), 
                arrival_stop_id=int(row[2]),
                departure_time=self.safe_fromtimestamp(int(row[3]) + delay),
                arrival_time=self.safe_fromtimestamp(int(row[4]) + delay),
                duration_minutes=duration, 
                distance_km=float(row[5]/1000.0), 
                service_mask=int(row[6]),
                train_number=self.snapshot.trip_to_train.get(int(row[0]), "") if self.snapshot else ""
            ))
        return res

    def get_train_path(self, tid: int) -> List[Dict[str, Any]]:
        return self.snapshot.train_path.get(tid, []) if self.snapshot else []

    def get_station_schedule(self, sid: int) -> List[Dict[str, Any]]:
        return self.snapshot.station_schedule.get(sid, []) if self.snapshot else []
