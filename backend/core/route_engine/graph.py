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
                # JSON saves [["f1", "i4"]] -> need [("f1", "i4")] for np.dtype
                dtype_obj = np.dtype([tuple(i) if isinstance(i, list) else i for i in dtype_raw])
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

    _pattern_segments_data: Optional[np.ndarray] = None
    _pattern_segments_index: Optional[np.ndarray] = None
    _pattern_id_map: Dict[int, int] = field(default_factory=dict)
    
    # Nexus Indices
    _trip_stop_pos_map: Dict[int, Dict[int, int]] = field(default_factory=dict)
    _trip_to_pid: Dict[int, int] = field(default_factory=dict)
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
    
    # [Task 146] Cluster Reachability Matrix
    cluster_reachability: Any = None
    
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

    def __getstate__(self):
        """[Task 121: Elite] Exclude large memmapped arrays from pickling to avoid RAM spikes."""
        state = self.__dict__.copy()
        # Null out all memmapped arrays; they will be recovered via remap()
        for attr in list(state.keys()):
            if isinstance(state[attr], np.ndarray):
                state[attr] = None
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        # Arrays remain None until remap() is called by the Manager

    def remap(self):
        """[Task 121: Elite] Recover memmapped arrays from disk based on snapshot date."""
        ts = int(self.date.timestamp())
        logger.info(f"⚡ [NEXUS:REMAP] Re-linking MemMaps for {self.date.date()} (ts={ts})...")
        
        self._departures_data = MemMapManager.load_array(f"deps_{ts}")
        self._departures_index = MemMapManager.load_array(f"deps_idx_{ts}")
        self._arrivals_data = MemMapManager.load_array(f"arrs_{ts}")
        self._arrivals_index = MemMapManager.load_array(f"arrs_idx_{ts}")
        
        self._pattern_deps_data = MemMapManager.load_array(f"p_deps_{ts}")
        self._pattern_deps_index = MemMapManager.load_array(f"p_deps_idx_{ts}")
        
        self._pattern_segments_data = MemMapManager.load_array(f"p_segs_{ts}")
        self._pattern_segments_index = MemMapManager.load_array(f"p_segs_idx_{ts}")
        
        self._trip_reachability_bitset = MemMapManager.load_array(f"reach_{ts}")
        
        self._transfers_data = MemMapManager.load_array(f"transfers_{ts}")
        self._transfers_index = MemMapManager.load_array(f"transfers_idx_{ts}")
        
        # [Task 146.5] Load Cluster Matrix
        from .reachability import ClusterReachabilityMatrix
        from database.config import Config
        self.cluster_reachability = ClusterReachabilityMatrix.load(self.date, Config.MEMMAP_DIR)
        
        # [Task 121: Elite Persistence] Restore TBR structures
        self.tbr_trip_nodes = MemMapManager.load_array(f"tbr_nodes_{ts}")
        
        # Restore indices (if they were saved/pickled - or reload from separate meta)
        # For simplicity, we assume they were pickled or we reload them.
        # Let's ensure they are also saved as memmaps if they were excluded.
        
        self.coordinate_matrix = MemMapManager.load_array("coordinate_matrix")
        
        logger.info("✅ [NEXUS:REMAP] Arrays re-linked successfully.")

    def is_cluster_reachable(self, src_cluster: str, dst_cluster: str) -> bool:
        """Convenience wrapper for gatekeeper checks."""
        if not self.cluster_reachability: return True # Fail-safe
        return self.cluster_reachability.is_reachable(src_cluster, dst_cluster)


    def pattern_for_trip(self, trip_id: int) -> Tuple[int, ...]:
        segs = self.trip_segments.get(trip_id, [])
        return tuple(seg.departure_stop_id for seg in segs) + ((segs[-1].arrival_stop_id,) if segs else ())

    def vectorize(self, tbr_data: Optional[Dict] = None):
        ts = int(self.date.timestamp())
        
        # [Nexus Patch] Ensure objects loaded from old pickles have space for new indices
        if tbr_data:
            self.tbr_trip_nodes = tbr_data.get('tbr_trip_nodes')
            self.tbr_trip_index = tbr_data.get('tbr_trip_index')
            self.tbr_stop_index = tbr_data.get('tbr_stop_index')

        nexus_attrs = ['_trip_stop_pos_map', '_trip_to_pid', '_pattern_id_map', '_pattern_segments_data', '_pattern_segments_index']
        for attr in nexus_attrs:
            if not hasattr(self, attr) or getattr(self, attr) is None:
                is_dict = "map" in attr or "pid" in attr
                setattr(self, attr, {} if is_dict else None)

        # [Nexus Fix] Use stable mapping from builder if available; otherwise create it once.
        if not self.stop_id_to_idx:
             all_sids = sorted(list(set(self.departures_by_stop.keys()) | set(self.arrivals_by_stop.keys())))
             self.stop_id_to_idx = {sid: i for i, sid in enumerate(all_sids)}
        
        self._stop_id_map = self.stop_id_to_idx
        all_sids = sorted(self._stop_id_map.keys())
        NUM_STOPS = len(all_sids)

        # [Task 146] Hub Intel Pre-calculation
        # Pre-resolve indices for major hubs to enable zero-latency reachability pruning
        from core.hubs import MEGA_HUBS, MAJOR_HUBS
        all_hub_codes = MEGA_HUBS | MAJOR_HUBS
        rev_stop_cache = {s.code: s.id for s in self.stop_cache.values()}
        hub_ids = [rev_stop_cache.get(code) for code in all_hub_codes if code in rev_stop_cache]
        self._hub_indices = [self._stop_id_map.get(hid) for hid in hub_ids]
        self._hub_indices = [i for i in self._hub_indices if i is not None]

        if self.departures_by_stop:
            all_deps = []; all_p_deps = []
            idx = np.zeros((len(all_sids), 2), dtype=np.int32)
            p_idx = np.zeros((len(all_sids), 2), dtype=np.int32)
            off = 0; p_off = 0
            
            for i, sid in enumerate(all_sids):
                deps = self.departures_by_stop.get(sid, [])
                idx[i] = [off, len(deps)]
                p_map = defaultdict(list)
                for dt, tid in deps:
                    all_deps.append([int(dt.timestamp()), tid])
                    pid = hash(self.pattern_for_trip(tid)) & 0x7FFFFFFF
                    p_map[pid].append([pid, int(dt.timestamp()), tid])
                off += len(deps)
                
                # [FIX] Sort by timestamp within the stop slice to enable bisect search
                stop_p_deps = []
                for pid in p_map:
                    stop_p_deps.extend(p_map[pid])
                stop_p_deps.sort(key=lambda x: x[1]) # Sort by ts (index 1)
                
                all_p_deps.extend(stop_p_deps)
                p_idx[i] = [p_off, len(stop_p_deps)]
                p_off += len(stop_p_deps)
            
            MemMapManager.save_array(f"deps_{ts}", np.array(all_deps, dtype=np.int64))
            self._departures_data = MemMapManager.load_array(f"deps_{ts}")
            MemMapManager.save_array(f"deps_idx_{ts}", idx)
            self._departures_index = MemMapManager.load_array(f"deps_idx_{ts}")
            
            MemMapManager.save_array(f"p_deps_{ts}", np.array(all_p_deps, dtype=np.int64))
            self._pattern_deps_data = MemMapManager.load_array(f"p_deps_{ts}")
            MemMapManager.save_array(f"p_deps_idx_{ts}", p_idx)
            self._pattern_deps_index = MemMapManager.load_array(f"p_deps_idx_{ts}")

        # 1.1 Arrivals (New Vectorized Store)
        if self.arrivals_by_stop:
            all_arrs = []
            idx = np.zeros((len(all_sids), 2), dtype=np.int32)
            off = 0
            
            for i, sid in enumerate(all_sids):
                arrs = self.arrivals_by_stop.get(sid, [])
                idx[i] = [off, len(arrs)]
                for dt, tid in arrs:
                    all_arrs.append([int(dt.timestamp()), tid])
                off += len(arrs)
            
            MemMapManager.save_array(f"arrs_{ts}", np.array(all_arrs, dtype=np.int64))
            self._arrivals_data = MemMapManager.load_array(f"arrs_{ts}")
            MemMapManager.save_array(f"arrs_idx_{ts}", idx)
            self._arrivals_index = MemMapManager.load_array(f"arrs_idx_{ts}")

        # 2. Pattern-Based Segments & Bitsets
        if self.trip_segments:
            pattern_to_segs = {}
            pattern_to_trips = defaultdict(list)
            
            # Group trips by unique stop sequence
            for tid, segs in self.trip_segments.items():
                # [Task 121: Elite Nexus Map] O(1) Trip-Stop Position Map
                pos_map = {}
                for idx, seg in enumerate(segs):
                    pos_map[seg.departure_stop_id] = idx
                if segs:
                    pos_map[segs[-1].arrival_stop_id] = len(segs)
                self._trip_stop_pos_map[tid] = pos_map
                
                p_key = self.pattern_for_trip(tid)
                if p_key not in pattern_to_segs:
                    pattern_to_segs[p_key] = segs
                pattern_to_trips[p_key].append(tid)

            # Vectorize Patterns
            all_pattern_segs = []
            sorted_patterns = sorted(pattern_to_segs.keys())
            p_idx = np.zeros((len(sorted_patterns), 2), dtype=np.int32)
            p_off = 0
            
            for i, p_key in enumerate(sorted_patterns):
                segs = pattern_to_segs[p_key]
                p_idx[i] = [p_off, len(segs)]
                pid = hash(p_key) & 0x7FFFFFFF
                self._pattern_id_map[pid] = i
                
                # [Task 121: Elite Yield] Link all trips to this pattern
                for tid in pattern_to_trips[p_key]:
                    self._trip_to_pid[tid] = pid

                for s in segs:
                    all_pattern_segs.append([
                        0, s.departure_stop_id, s.arrival_stop_id, 
                        int(s.departure_time.timestamp()) % 86400, # Relative time
                        int(s.arrival_time.timestamp()) % 86400,
                        int(s.distance_km * 1000), s.service_mask, s.stop_sequence
                    ])
                p_off += len(segs)

            ts = int(self.date.timestamp())
            MemMapManager.save_array(f"p_segs_{ts}", np.array(all_pattern_segs, dtype=np.int64))
            self._pattern_segments_data = MemMapManager.load_array(f"p_segs_{ts}")
            MemMapManager.save_array(f"p_segs_idx_{ts}", p_idx)
            self._pattern_segments_index = MemMapManager.load_array(f"p_segs_idx_{ts}")

            # Bitsets (Trip-specific)
            tids = sorted(self.trip_segments.keys())
            self._trip_id_map = {tid: i for i, tid in enumerate(tids)}
            NUM_STOPS = 65536 # Expanded limit
            BITSET_WORDS = (NUM_STOPS // 64) + 1
            reach_bits = np.zeros((len(tids), BITSET_WORDS), dtype=np.uint64)

            # [Task RO-012] Build stop-to-stop spatial reachability via DFS for 100% coverage
            stop_adj = defaultdict(set)
            for tid, segs in self.trip_segments.items():
                for s in segs:
                    stop_adj[s.departure_stop_id].add(s.arrival_stop_id)
            if hasattr(self, 'transfer_graph') and self.transfer_graph:
                for sid, xfers in self.transfer_graph.items():
                    for x in xfers:
                        stop_adj[sid].add(x.to_stop_id)
            
            stop_reach = {}
            for sid in self._stop_id_map.keys():
                visited = set()
                queue = [sid]
                while queue:
                    curr = queue.pop()
                    if curr not in visited:
                        visited.add(curr)
                        for neighbor in stop_adj[curr]:
                            if neighbor not in visited:
                                queue.append(neighbor)
                stop_reach[sid] = visited

            for i, tid in enumerate(tids):
                # [Nexus: Elite Reach Fix] include ALL stops in bitset for perfect discovery
                pos_map = self._trip_stop_pos_map.get(tid, {})
                sids = []
                if pos_map:
                    sids = list(pos_map.keys())
                elif self.tbr_trip_index and tid in self.tbr_trip_index:
                    off, count = self.tbr_trip_index[tid]
                    sids = [int(self.tbr_trip_nodes[off + j]['stop_id']) for j in range(count)]
                
                # Expand using DFS transitive closure
                full_sids = set()
                for sid in sids:
                    full_sids.update(stop_reach.get(sid, {sid}))
                
                for sid in full_sids:
                    s_idx = self._stop_id_map.get(sid)
                    if s_idx is not None and s_idx < NUM_STOPS:
                        reach_bits[i, s_idx // 64] |= np.uint64(1) << np.uint64(s_idx % 64)

            
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

        # [Nexus Patch] Only clear if we actually had source data to vectorize from
        has_source = bool(self.trip_segments or self.departures_by_stop)
        if has_source:
             self.departures_by_stop.clear()
             self.arrivals_by_stop.clear()
             self.trip_segments.clear()
             self.transfer_graph.clear()
             self.train_path.clear()
             self.station_schedule.clear()
             self.station_ids_by_trip.clear()
             logger.info(f"✅ Graph Vectorization Complete. Legacy data cleared.")
        else:
             logger.debug("⚠️ [NEXUS] Vectorize called on already-vectorized or empty snapshot. Skipping clear.")

        # 4. TBR Data [Task 121: Persistence Alignment]
        if tbr_data:
            self.tbr_trip_nodes = tbr_data.get('tbr_trip_nodes')
            self.tbr_trip_index = tbr_data.get('tbr_trip_index', {})
            self.tbr_stop_index = tbr_data.get('tbr_stop_index', {})
            
            # Save to MemMap for disk recovery
            if isinstance(self.tbr_trip_nodes, np.ndarray):
                ts = int(self.date.timestamp())
                MemMapManager.save_array(f"tbr_nodes_{ts}", self.tbr_trip_nodes)

        logger.info(f"🚀 Vectorization Complete for {self.date.date()}.")

    version: str = "v10.0" 

class RealtimeOverlay:
    def __init__(self):
        self.delays: Dict[int, int] = {}
        self.cancellations: Set[int] = set()
        self.platform_changes: Dict[Tuple[int, int], str] = {}
        self.version: int = 0

    def get_trip_delay(self, tid: int) -> int: return self.delays.get(tid, 0)
    def set_trip_delay(self, tid: int, delay: int):
        self.delays[tid] = delay
        self.version += 1
        
    def is_cancelled(self, tid: int) -> bool: return tid in self.cancellations
    def mark_cancelled(self, tid: int):
        self.cancellations.add(tid)
        self.version += 1

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
        # [Task 121: Elite O(1) Code Map]
        self._stop_code_map = {s.code.upper(): s for s in self.stop_cache.values()}

    def get_stop_by_code(self, code: str) -> Optional[Stop]:
        return self._stop_code_map.get(code.upper().strip())

    def can_reach_destination(self, tid: int, dst_id: int) -> bool:
        if not self.snapshot or self.snapshot._trip_reachability_bitset is None: return True
        t_idx = self.snapshot._trip_id_map.get(tid)
        dst_idx = self.snapshot._stop_id_map.get(dst_id)
        
        if t_idx is None or dst_idx is None:
            # logger.debug(f"Reach: Missing tid={tid}({t_idx}) or sid={dst_id}({dst_idx})")
            return True
            
        words = self.snapshot._trip_reachability_bitset.shape[1]
        word_idx = dst_idx // 64
        if word_idx >= words:
            return True
            
        mask = np.uint64(1) << np.uint64(dst_idx % 64)
        word = self.snapshot._trip_reachability_bitset[t_idx, word_idx]
        return bool(word & mask)

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
                pid = hash(str(tid)) & 0x7FFFFFFF # Hashing trip_id to get pid for legacy
                results[pid].append((dt, tid))
            return results
            
        s_idx = self.snapshot._stop_id_map.get(stop_id)
        if s_idx is None: return {}
        
        off, count = self.snapshot._pattern_deps_index[s_idx]
        data_slice = self.snapshot._pattern_deps_data[off : off + count]
        
        after_ts = int(after_time.timestamp())
        limit_ts = after_ts + (lookahead * 60)
        
        # Use bisect_left to find the starting index
        # data_slice is structured as (pid, ts, tid), so we compare against ts (index 1)
        
        # Create a dummy array for bisect search.
        # This is a bit of a hack. A better way would be to store timestamps separately
        # or have a specialized bisect for structured arrays.
        timestamps = data_slice[:, 1] # Assuming ts is the second column
        
        start_pos = bisect_left(timestamps, after_ts)
        
        for i in range(start_pos, count):
            pid, ts, tid = data_slice[i]
            if ts > limit_ts: break # Stop if beyond lookahead
            
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
        data_slice = self.snapshot._departures_data[off : off + count]
        
        after_ts = int(after.timestamp())
        limit_ts = after_ts + (lookahead * 60)
        
        res = []
        
        # Use bisect_left to find the starting index
        timestamps = data_slice[:, 0] # Assuming ts is the first column
        start_pos = bisect_left(timestamps, after_ts)
        
        for i in range(start_pos, count):
            ts, tid = data_slice[i]
            if ts > limit_ts: break # Stop if beyond lookahead
            
            if not self.overlay.is_cancelled(tid):
                eff_ts = ts + (self.overlay.get_trip_delay(tid) * 60)
                if after_ts <= eff_ts <= limit_ts:
                    res.append((self.safe_fromtimestamp(eff_ts), int(tid)))
        return res

    def can_reach_destination(self, tid: int, dest_sid: int) -> bool:
        """[Task 146] O(1) Trip-Stop Reachability Check using Bitsets."""
        if not self.snapshot or self.snapshot._trip_reachability_bitset is None:
            return True
        
        t_idx = self.snapshot._trip_id_map.get(tid)
        if t_idx is None: return True
        
        s_idx = self.snapshot._stop_id_map.get(dest_sid)
        if s_idx is None: return True # Could be a new station or out of index
        
        # Check the bit in the bitset (packed uint64 words)
        try:
             word_idx = s_idx // 64
             bit_idx = s_idx % 64
             return bool(self.snapshot._trip_reachability_bitset[t_idx, word_idx] & (np.uint64(1) << np.uint64(bit_idx)))
        except IndexError:
             return True # Safety fallback

    def can_reach_any_hub(self, tid: int) -> bool:
        """[Task 146] Check if trip hits any major Hub for multi-hop expansion."""
        if not self.snapshot or self.snapshot._trip_reachability_bitset is None:
            return True
        t_idx = self.snapshot._trip_id_map.get(tid)
        if t_idx is None: return True
        
        hub_indices = getattr(self.snapshot, '_hub_indices', [])
        if not hub_indices: return True
        
        bitset_row = self.snapshot._trip_reachability_bitset[t_idx]
        for h_idx in hub_indices:
            try:
                if bitset_row[h_idx // 64] & (np.uint64(1) << np.uint64(h_idx % 64)):
                    return True
            except: continue
        return False

    def _get_strategic_road_bridges(self, sid: int, depth: str = "SHALLOW") -> List[TransferConnection]:
        """[Task 138] Inject strategic Geo-Bridges (40-50km) for Deep Discovery."""
        if depth == "SHALLOW": return []
        
        # In a real system, this is populated from self.snapshot.road_bridges
        # For now, we use a curated strategic list or distance-based heuristic
        bridges = []
        
        # [Task 138.3] Heuristic: Any station in the same city cluster but > 2km away
        center_stop = self.stop_cache.get(sid)
        if not center_stop or not center_stop.city: return []
        
        cluster_sids = self.snapshot.city_clusters.get(center_stop.city, []) if self.snapshot else []
        for target_sid in cluster_sids:
            if target_sid == sid: continue
            
            target = self.stop_cache.get(target_sid)
            if not target: continue
            
            # Simple Euclidean Distance (40-50km max)
            dist_km = ((center_stop.latitude - target.latitude)**2 + (center_stop.longitude - target.longitude)**2)**0.5 * 111.0
            
            # [Task 138.5] Thresholds
            # Depth MEDIUM: up to 30km
            # Depth DEEP: up to 50km
            limit = 60.0 if depth == "DEEP" else 30.0
            
            if 2.0 < dist_km <= limit:
                # Estimate duration: 25 mins + (1.5 mins per km)
                duration = int(25 + (dist_km * 1.5))
                bridges.append(TransferConnection(
                    target_id=target_sid,
                    target_code=target.code,
                    valid_from=datetime.min, 
                    valid_to=datetime.max,
                    duration_minutes=duration,
                    target_name=target.name,
                    is_multi_station=True,
                    transfer_type="TAXI"
                ))
        return bridges

    def get_transfers_from_stop(self, sid: int, arr: datetime, min_transfer_time: int = 15, 
                                incoming_trip_id: int = None, search_depth: str = "SHALLOW") -> List[TransferConnection]:
        feasible = []
        
        # [Task 143] Dynamic Scaling Intelligence
        eff_min_tr = min_transfer_time
        if sid in self.stop_cache:
            stop = self.stop_cache[sid]
            # Use reliability intelligence if available for incoming trip
            rel_score = self.snapshot.reliability_scores.get(incoming_trip_id, 0.5) if (self.snapshot and incoming_trip_id) else 0.5
            from core.hubs import get_smart_transfer_buffer
            eff_min_tr = get_smart_transfer_buffer(stop.code, rel_score)
            
            # If user explicitly requested a MINIMUM time, respect it if it's higher
            eff_min_tr = max(eff_min_tr, min_transfer_time)

        # 1. In-station transfer (buffer time)
        if sid in self.stop_cache:
            s = self.stop_cache[sid]
            feasible.append(TransferConnection(sid, s.code, datetime.min, datetime.max, max(eff_min_tr, 15), s.name, is_multi_station=False))
            
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
                    
                    # Allow any positive transfer duration up to 24h (avoid filtering valid boundaries)
                    if dur > 0 and dur <= 1440:
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
        
        # 3. [Task 138] Multi-Modal Intelligent Bridges (Dynamic)
        if search_depth in ("MEDIUM", "DEEP"):
            bridges = self._get_strategic_road_bridges(sid, search_depth)
            # Deduplicate (If transfer already exists in graph, don't add bridge)
            existing_targets = {f.target_id for f in feasible}
            for b in bridges:
                if b.target_id not in existing_targets:
                    feasible.append(b)

        return feasible

    def get_pattern_segments(self, pid: int) -> Optional[np.ndarray]:
        if self.snapshot and self.snapshot._pattern_segments_data is not None:
            p_idx = self.snapshot._pattern_id_map.get(pid)
            if p_idx is None: return None
            off, count = self.snapshot._pattern_segments_index[p_idx]
            return self.snapshot._pattern_segments_data[off : off + count]
        return None

    def get_stop_sequence_in_trip(self, tid: int, sid: int) -> int:
        if not self.snapshot: return -1
        # [Task 121: Elite O(1) Lookup]
        if self.snapshot._trip_stop_pos_map:
            return self.snapshot._trip_stop_pos_map.get(tid, {}).get(sid, -1)
            
        # [Task 121: Elite Fallback] Scan TBR nodes if map missing
        if self.snapshot.tbr_trip_index and tid in self.snapshot.tbr_trip_index:
            off, count = self.snapshot.tbr_trip_index[tid]
            if self.snapshot.tbr_trip_nodes is not None:
                for i in range(count):
                    if self.snapshot.tbr_trip_nodes[off + i]['stop_id'] == sid:
                        return i
        return -1

    def get_trip_segments_raw(self, tid: int) -> Optional[np.ndarray]:
        if not self.snapshot or not self.snapshot._trip_to_pid: return None
        pid = self.snapshot._trip_to_pid.get(tid)
        if pid is not None:
            return self.get_pattern_segments(pid)
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
                trip_id=tid, 
                departure_stop_id=int(row[1]), 
                arrival_stop_id=int(row[2]),
                departure_time=self.safe_fromtimestamp(int(row[3]) + delay),
                arrival_time=self.safe_fromtimestamp(int(row[4]) + delay),
                duration_minutes=duration, 
                distance_km=float(row[5]/1000.0), 
                service_mask=int(row[6]),
                train_number=self.snapshot.trip_to_train.get(tid, "") if self.snapshot else ""
            ))
        return res

    def get_train_path(self, tid: int) -> List[Dict[str, Any]]:
        return self.snapshot.train_path.get(tid, []) if self.snapshot else []

    def get_station_schedule(self, sid: int) -> List[Dict[str, Any]]:
        return self.snapshot.station_schedule.get(sid, []) if self.snapshot else []
