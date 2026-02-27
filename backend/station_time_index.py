"""Station-centric time-series lookup index (Phase-1).

Loads `station_departures` + `time_index_keys` from the DB into RAM as
Roaring bitmaps for extremely fast lookups.

API:
  - StationTimeIndex(db_session)  # loads into memory
  - query(station_id, time_minute, lookahead_minutes=60) -> list of {entity_type, entity_id}
  - save_cache(path) / load_cache(path)

Notes:
  - Uses Roaring BitMap (pyroaring) for compact, fast bit operations.
  - Buckets are minutes-since-midnight floored to the chosen interval (default 15).
"""
from __future__ import annotations

import pickle
from typing import Dict, Optional, List, Tuple
try:
    from pyroaring import BitMap
except Exception:
    # Local shim when pyroaring is not installed (tests / lightweight use)
    import pickle
    class BitMap:
        def __init__(self, iterable=None):
            self._s = set(iterable or [])
        def __ior__(self, other):
            self._s |= (other._s if isinstance(other, BitMap) else set(other))
            return self
        def __or__(self, other):
            return BitMap(self._s | (other._s if isinstance(other, BitMap) else set(other)))
        def __iter__(self):
            return iter(self._s)
        def serialize(self):
            return pickle.dumps(sorted(self._s))
        @classmethod
        def deserialize(cls, blob):
            try:
                data = pickle.loads(blob)
            except Exception:
                data = []
            return BitMap(data)
from datetime import time

from sqlalchemy.orm import Session

from database.models import StationDepartureBucket, StopDepartureBucket, TimeIndexKey


class StationTimeIndex:
    def __init__(self, db: Session, bucket_minutes: int = 15, cache_path: Optional[str] = None):
        self.db = db
        self.bucket_minutes = bucket_minutes
        # station_id -> {bucket_start_minute: BitMap}
        self.index: Dict[str, Dict[int, BitMap]] = {}
        # key_id -> (entity_type, entity_id)
        self.key_map: Dict[int, Tuple[str, str]] = {}

        if cache_path:
            try:
                self.load_cache(cache_path)
                return
            except Exception:
                # fallback to DB load
                pass
        self._load_from_db()

    def _load_from_db(self):
        # load keys
        for k in self.db.query(TimeIndexKey).all():
            self.key_map[k.id] = (k.entity_type, k.entity_id)

        # load station buckets (railway_manager stations)
        for row in self.db.query(StationDepartureBucket).all():
            station = row.station_id
            bucket = row.bucket_start_minute
            try:
                bm = BitMap.deserialize(row.bitmap)
            except Exception:
                bm = BitMap()
            self.index.setdefault(station, {})[bucket] = bm

        # load stop buckets (GTFS stops) — keys are integers
        for row in self.db.query(StopDepartureBucket).all():
            stop = row.stop_id
            bucket = row.bucket_start_minute
            try:
                bm = BitMap.deserialize(row.bitmap)
            except Exception:
                bm = BitMap()
            self.index.setdefault(stop, {})[bucket] = bm

    def query(self, station_id, minute_of_day: int, lookahead_minutes: int = 60) -> List[Dict[str, str]]:
        """Return list of entity dicts (entity_type, entity_id) available from station
        between minute_of_day and minute_of_day + lookahead_minutes (inclusive).

        station_id can be a string (Station.id) or integer (Stop.id).
        """
        key = station_id
        # allow string/int interchangeability
        if station_id not in self.index and isinstance(station_id, int):
            key = station_id
        if key not in self.index:
            return []

        start_bucket = minute_of_day - (minute_of_day % self.bucket_minutes)
        end_minute = minute_of_day + lookahead_minutes
        buckets = list(range(start_bucket, end_minute + 1, self.bucket_minutes))

        agg = BitMap()
        station_buckets = self.index.get(key, {})
        for b in buckets:
            bm = station_buckets.get(b)
            if bm:
                agg |= bm

        result = []
        for key_id in agg:
            mapping = self.key_map.get(key_id)
            if not mapping:
                continue
            entity_type, entity_id = mapping
            result.append({"entity_type": entity_type, "entity_id": entity_id})
        return result

    def save_cache(self, path: str):
        payload = {
            'bucket_minutes': self.bucket_minutes,
            'key_map': self.key_map,
            'index': {s: {b: bm.serialize() for b, bm in buckets.items()} for s, buckets in self.index.items()},
        }
        with open(path, 'wb') as fh:
            pickle.dump(payload, fh)

    def load_cache(self, path: str):
        with open(path, 'rb') as fh:
            payload = pickle.load(fh)
        self.bucket_minutes = payload['bucket_minutes']
        self.key_map = payload['key_map']
        self.index = {}
        for s, buckets in payload['index'].items():
            self.index[s] = {int(b): BitMap.deserialize(v) for b, v in buckets.items()}


if __name__ == '__main__':
    # quick local demo (requires a DB session)
    from database import SessionLocal

    db = SessionLocal()
    idx = StationTimeIndex(db)
    sample_station = next(iter(idx.index.keys())) if idx.index else None
    if sample_station:
        print('Sample buckets for', sample_station, '->', list(idx.index[sample_station].keys())[:5])
    else:
        print('No station buckets found (run ETL first).')
