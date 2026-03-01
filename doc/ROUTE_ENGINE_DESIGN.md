# Route Generation and Transit Data Architecture

This document captures the current architecture for building the route graph, the
structure of the `transit_graph.db` and `railway_data.db` databases, and a plan to
apply the station-centric / train-centric data views you described for faster,
accurate multi-transfer route searches.

## 🔁 Core concepts already implemented

- **Station-centric view** is built in memory by `GraphBuilder`:
  `departures_by_stop: stop_id -> [(departure_dt, trip_id), ...]` and
  `arrivals_by_stop`.
- **Train-centric view** is represented by
  `trip_segments[trip_id] = [RouteSegment,...]` where each segment contains both
  departure/arrival times and station IDs.
- `TimeDependentGraph` wraps these dictionaries and provides helpers used by the
  RAPTOR implementations (`OptimizedRAPTOR` / `HybridRAPTOR`).

These two views satisfy the requirement that every station knows which trains
pass through it, and every train knows its ordered list of stations.

## 🗃 Database schema overview

`transit_graph.db` (SQLite):

- `stops` (8 119 rows)
- `segments` (139 054 rows) – one row per leg of a train
- `trips` (9 878 rows)
- `stop_times` (148 932 rows)
- `calendar` / `calendar_dates` (service schedules)
- `gtfs_routes` (train metadata)

`railway_data.db` is an earlier copy with 0 rows in most tables; it’s not used
for routing presently.

## ✅ Desired enhancements

To make routing faster and more transparent, maintain **persistent
station_schedule** and **train_path** tables (in both SQLite & Postgres):

```sql
CREATE TABLE station_schedule (
  station_id   INTEGER NOT NULL,
  train_id     INTEGER NOT NULL,
  arrival      TIME,
  departure    TIME,
  day_of_week  VARCHAR(9),
  stop_seq     INTEGER,
  PRIMARY KEY (station_id, train_id, stop_seq)
);

CREATE INDEX idx_station_schedule_station ON station_schedule(station_id, day_of_week, departure);
CREATE INDEX idx_station_schedule_train   ON station_schedule(train_id, stop_seq);

CREATE TABLE train_path (
  train_id    INTEGER NOT NULL,
  station_id  INTEGER NOT NULL,
  arrival     TIME,
  departure   TIME,
  stop_seq    INTEGER,
  day_of_week VARCHAR(9),
  PRIMARY KEY (train_id, stop_seq)
);

CREATE INDEX idx_train_path_station ON train_path(station_id);
```

These schemas provide:

- O(1) lookups of trains serving a station (ordered by departure time).
- O(1) reconstruction of a train’s route – useful for verifying direct
  connections without running RAPTOR.

## ⚙ Implementation plan

1. **Extend ETL** (`backend/etl/sqlite_to_postgres.py` or similar) to populate the
   new tables each night.
2. **GraphBuilder** enhancements:
   - Write station_schedule & train_path into the snapshot file.
   - Add `get_station_schedule()` and `get_train_path()` helpers.
3. **SearchService optimisations**:
   - Pre‑check direct connectivity via `station_schedule` or `train_path`.
   - Terminate transfers tiers early when sufficient direct/1‑transfer journeys
     are found.
4. **Add unit/integration tests** to validate population and correctness.
5. **Consider bitmask day‑of‑week and transfer cache** for further speedups.

## 📈 Benefits

- Instant awareness of which stations/trains are connected.
- Reduced time spent building the graph for every query.
- Simplified logic for de‑duplication and dominance pruning.
- Easier debugging and analytics: you can query the database with SQL.

> This design mirrors how production systems (Google Maps, IRCTC, etc.)
structure transit data internally.

Once the new tables exist, routing searches will automatically become faster and
more accurate, with direct results returned before fallbacks to more expensive
RAPTOR searches.


---

Feel free to extend this file with additional notes or implementation details as
you proceed.