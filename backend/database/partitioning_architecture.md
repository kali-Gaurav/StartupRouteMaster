# 🏗️ RouteMaster: Industrial Partitioning & Archival Architecture

## 1. Objectives
- **Zero-Latency Scalability**: Prevent sequential scans on `SearchLogs` and `Heartbeats`.
- **Atomic Retention**: Use `DROP TABLE` for archival instead of expensive `DELETE` queries.
- **Lock Contention Distribution**: Distribute concurrent writes to station heartbeats.

---

## 2. Partition Strategy

### 🔹 `route_search_logs`
- **Type**: `RANGE (created_at)`
- **Granularity**: Daily
- **Retention**: 7 Days (Hot), 30 Days (Warm/Cold Storage)
- **SQL Template**:
  ```sql
  CREATE TABLE route_search_logs_p20260422 PARTITION OF route_search_logs
  FOR VALUES FROM ('2026-04-22 00:00:00') TO ('2026-04-23 00:00:00');
  ```

### 🔹 `station_realtime_heartbeats`
- **Type**: `HASH (station_code)`
- **Segments**: 32 (Balanced for ~10,000 stations)
- **Why**: Major hubs (NDLS, BCT) receive 100x more updates. Hashing prevents "Hot Table" syndrome.
- **SQL Template**:
  ```sql
  CREATE TABLE station_heartbeats_p0 PARTITION OF station_realtime_heartbeats
  FOR VALUES WITH (MODULUS 32, REMAINDER 0);
  ```

---

## 3. Data Retention Policy (BailiffAgent)

| Table | Policy | Action |
| :--- | :--- | :--- |
| **Search Logs** | 7 Days | Move to S3/Cold Storage, then DROP partition. |
| **Heartbeats** | 1 Hour | Drop sub-partitions aggressively. |
| **Fraud Alerts** | 1 Year | Keep for legal audit. |
| **Identity Fingerprints**| Indefinite | Keep for long-term behavioral profiling. |

---

## 4. Query Routing Layer (SQLAlchemy Logic)

The `PartitionRouter` will intercept queries to:
1.  Append `created_at` filters automatically to hit specific partitions.
2.  Prevent "Cross-Partition Scans" by enforcing station_code in all heartbeat lookups.

---

## 5. Failure Boundary: "Partition Overflow"
If a partition for tomorrow is not created (Worker Failure), the system routes to a `route_search_logs_default` table and triggers a **CRITICAL** alert to the `ForgeAgent`.
