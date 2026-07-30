# Database Schema Storage Review

## Executive Summary

The StartupRouteMaster application implements a multi-layered database storage architecture with distinct concerns:
1. **Backend SQL Schema** - PostgreSQL with complex relational structure
2. **ML Feature Store** - SQL Server-based tables for ML training pipeline
3. **R2 Cloud Sync** - Cloudflare R2 backup and sync for ephemeral deployments
4. **Frontend IndexedDB** - Client-side caching using Dexie

The implementation demonstrates solid architectural patterns but has room for optimization in schema design, migration management, and sync resilience.

---

## 1. Backend SQL Schema Architecture

### 1.1 Schema Evolution & Migrations

**File**: `backend/alembic/versions/3207f768fa56_sync_user_schema.py`

**Observations**:
- **Large Single Migration**: 2,175 lines in one migration file - massive refactoring executed in one atomic operation
- **Table Destruction & Recreation**: Drops 25+ tables including `booking_requests`, `stations`, `refunds`, `frequencies`, `waiting_list`, `leads`, etc.
- **Column Type Changes**: Converts data types (e.g., INTEGER → VARCHAR, BOOLEAN → INTEGER for calendar weekdays)
- **Foreign Key Restructuring**: Updates relationships across multiple tables (e.g., bookings → trips foreign key removed)

**Strengths**:
- ✅ Proper IF EXISTS checks for idempotency
- ✅ Comprehensive index creation and management
- ✅ Bidirectional upgrade/downgrade logic

**Weaknesses**:
- ⚠️ Monolithic migration makes rollback risky for large production databases
- ⚠️ No documented business logic for why specific tables were dropped
- ⚠️ No data migration strategy documented for destructive changes
- ⚠️ Lacks downtime planning or gradual migration approach

**Recommendation**: 
- Split massive migrations into smaller, logical chunks
- Add migration guards with data validation before dropping tables
- Document the reasoning for schema changes in migration file comments

### 1.2 Current Schema Structure

**File**: `backend/alembic/versions/41af9fd39336_empty_baseline_for_existing_schema.py`

**Core Tables** (Baseline):
- `routes` - Route definitions with segments, duration, cost
- `stations` / `stations_master` - Station metadata and master data
- `users` - User accounts with authentication
- `vehicles` - Transportation vehicles (train, bus, flight)
- `bookings` - Booking records linked to users and routes
- `segments` - Route segments between stations
- `payments` - Payment tracking with Razorpay integration
- `reviews` - User ratings and comments on bookings

**Extended Tables** (From sync migration):
- `cancelled_trains` - Train cancellation records
- `etl_metadata` - ETL pipeline tracking
- `metro_station_groups` - Station grouping/clustering
- `station_realtime_heartbeats` - Live station status updates
- `station_transit_index` - Transit graph storage (text and binary formats)
- `train_running_status_cache` - Train status cache
- `station_cluster_mapping` - Station clustering relationships
- `station_health_index` - Station infrastructure/safety scores
- `station_rank` - Connectivity ranking for stations
- `station_schedules` / `train_paths` - Schedule patterns
- `seat_availability` / `seat_inventory` - Seat management
- `payment_sessions` - Session-based payment tracking
- `commission_tracking` - Partner commission tracking
- `sos_events` / `sos_telemetry` - Safety alert system
- `wallet` / `credit_transactions` - User credit/balance system
- `subscriptions` - User subscription management
- `user_heartbeats` - Location tracking during journeys
- `rl_feedback_logs` - Reinforcement learning feedback

**Strengths**:
- ✅ Comprehensive coverage of domain entities
- ✅ Proper foreign key constraints
- ✅ Strategic indexing on frequently queried columns
- ✅ JSON support for flexible data (booking_details, transaction_history)

**Weaknesses**:
- ⚠️ **Schema Sprawl**: 80+ tables - complexity increases maintenance burden
- ⚠️ **Duplicate Concerns**: Multiple station-related tables (stations, stations_master, station_realtime_heartbeats, station_transit_index, metro_station_groups)
- ⚠️ **Missing Partitioning**: No time-based partitioning for high-volume tables (seat_availability, train_running_status_cache)
- ⚠️ **Unclear Normalization**: Some denormalization without clear performance rationale documented

### 1.3 Index Strategy

**Current Indexes**:
- Composite indexes: `[source+destination]`, `[from_stop_id, to_stop_id]`
- Time-based: `created_at DESC`, `timestamp`, `journey_date`
- Business logic: `is_active`, `status`, `booking_status`
- Unique constraints on identifiers: `search_id`, `train_number + journey_date`

**Issues**:
- ⚠️ Inconsistent naming convention: `ix_*` vs `idx_*` prefixes
- ⚠️ Many UNIQUE indexes on non-primary keys (e.g., `upi_tx_id`, `upi_utr_hash`) - may create constraint violations during bulk operations
- ⚠️ Spatial index (GIST on `geom`) created but geometry column later dropped - orphaned index

---

## 2. ML Feature Store Schema

**File**: `backend/database/storage/ml_feature_store_schema.sql`

### 2.1 Schema Design

**Tables**:
1. **route_search_events** - Raw events from Kafka
   - Columns: 14 (search_id, timestamp, user_id, stations, train_classes, raw_request/response)
   - Indexes: 5 (search_id UNIQUE, timestamp, user_id, stations, date)
   - Purpose: Event streaming ingestion

2. **route_features** - Feature-engineered data
   - Columns: 25+ (temporal, route, train, price, target variables)
   - Constraints: CHECK for value ranges (0-23 for hour, >= 0 for distance)
   - Versioning: `feature_version` column for schema evolution
   - Target Variables: actual_delay_minutes, tatkal_booked, booking_confirmed (delayed labeling)

3. **training_datasets** - Dataset metadata
   - Columns: 11 (dataset_name, version, record_count, data quality metrics)
   - Storage Paths: S3 and local paths for reproducibility
   - Hash: dataset_hash for snapshot reproducibility

4. **model_metadata** - Model registry
   - Columns: 13 (model_name, version, algorithm, hyperparameters, performance metrics)
   - Deployment: Dual storage (S3 + local) with is_active flag
   - Performance Tracking: train/validation/test accuracy

**Views**:
- `active_models` - Latest active model versions
- `dataset_quality` - Data quality overview for datasets
- `feature_stats` - 30-day rolling statistics on features

**Strengths**:
- ✅ Proper separation of concerns (raw events → features → datasets → models)
- ✅ Feature versioning enables schema evolution
- ✅ CHECK constraints enforce data integrity (non-negative values)
- ✅ Delayed labeling pattern for target variables
- ✅ Metadata storage for reproducibility (hash, version, date ranges)
- ✅ Views provide convenient query patterns

**Weaknesses**:
- ⚠️ **T-SQL Specific**: Uses SQL Server syntax (`GETUTCDATE()`, `IDENTITY`, `sysobjects`) - not portable to PostgreSQL
- ⚠️ **Large Binary Columns**: `raw_request/response` stored as NVARCHAR(MAX) - no compression, poor for large payloads
- ⚠️ **Feature Store Coupling**: `route_features` tightly coupled to route domain - won't scale for multi-domain ML
- ⚠️ **No Time Partitioning**: Missing partitioning on timestamp for efficient historical queries
- ⚠️ **Incomplete Metadata**: No dataset schema definition, feature descriptions, or data lineage tracking
- ⚠️ **No Soft Deletes**: No way to track data retention/archival of old datasets

---

## 3. Cloud Storage Sync Architecture

### 3.1 R2 Storage Manager

**File**: `backend/services/data/storage_sync.py`

**Design Pattern**:
```
Local DB Files ↔ (Compress/Decompress) ↔ R2 Bucket (S3-compatible)
                      SHA256 Verification
```

**Key Features**:
- **Bi-directional Sync**: `sync_from_r2()` (download) and `sync_to_r2()` (upload)
- **Compression**: Zstandard (level 3) with `.zst` extension
- **Checksum Verification**: SHA256 hashes stored in R2 object metadata
- **Atomic Operations**: Uses `.tmp` files with `os.replace()` for atomic swaps
- **Directory Support**: Recursively walks and syncs directory trees
- **Periodic Sync**: Background task with 1-hour default interval

**Database Targets**:
```python
db_paths = [
    "database/user_store.db",
    "database/transit_graph.db",
    "database/railway_data.db",
    "database/snapshots",  # Directory
    "nexus_vitals.mmap"
]
```

**Strengths**:
- ✅ Checksum-based change detection (skip redundant uploads)
- ✅ Compression reduces storage cost (~3x for SQLite)
- ✅ Atomic file operations prevent partial writes
- ✅ Async/await pattern allows non-blocking operations
- ✅ Comprehensive error handling with try-catch logging
- ✅ CLI entry point for manual sync operations

**Weaknesses**:
- ⚠️ **Sync Latency**: 1-hour interval may lose recent data in crash scenarios
- ⚠️ **No Conflict Resolution**: If local and remote diverge, "first one wins"
- ⚠️ **File Size Limits**: No handling for large files that timeout during sync
- ⚠️ **No Progress Tracking**: Can't monitor sync status mid-operation
- ⚠️ **Lack of Bandwidth Throttling**: May saturate network on large datasets
- ⚠️ **Directory Sync Complexity**: Line 142-151 has unfinished logic for directory handling
- ⚠️ **Fixed Compression Level**: No adaptive compression based on file type
- ⚠️ **SQLite-Centric**: Hardcoded for SQLite databases - not suitable for general-purpose data

### 3.2 R2 Storage Wrapper

**File**: `backend/utils/storage.py`

**Interface**:
```python
class R2Storage:
    upload_file(file_path, object_name, metadata)
    download_file(object_name, file_path)
    get_object_metadata(object_name)
    delete_object(object_name)
    list_objects(prefix="")
```

**Strengths**:
- ✅ Clean S3-compatible API abstraction
- ✅ Metadata support for custom attributes
- ✅ Comprehensive error logging

**Weaknesses**:
- ⚠️ **Configuration Validation**: Silently accepts incomplete credentials (logs warning, doesn't fail fast)
- ⚠️ **No Retry Logic**: Single attempt on failures
- ⚠️ **No Rate Limiting**: May hit R2 API limits on bulk operations
- ⚠️ **Blocking Operations**: Uses `run_in_executor()` in sync manager, but no connection pooling
- ⚠️ **Missing Methods**: No multipart upload for large files, no streaming support

---

## 4. Frontend Storage & Caching

**File**: `frontend/src/services/storageService.ts`

### 4.1 IndexedDB Schema

**Database**: `RailAssistantDB` (Dexie)

**Tables**:

| Table | Primary Key | Indexes | Purpose |
|-------|-------------|---------|---------|
| `cachedRoutes` | `++id` | `[source+destination]`, `timestamp` | Route result cache (24h TTL) |
| `userStats` | `id` | None | User aggregation metrics |
| `recentSearches` | `++id` | `timestamp`, `[source+destination]` | Search history |
| `favorites` | `[source+destination]` | `count` | Favorite routes with frequency |

**Schema Versioning**:
- Version 2 → Version 3 migration adds `count` index on `favorites` table
- Upgrade handler ensures all favorites have count property

**Strengths**:
- ✅ Client-side caching reduces API calls
- ✅ Proper TTL enforcement (24 hours for routes)
- ✅ Version migration handling for schema evolution
- ✅ Composite keys for efficient lookups
- ✅ Error handling with try-catch blocks
- ✅ Favorite tracking with frequency counting

**Weaknesses**:
- ⚠️ **No Sync Logic**: Browser cache diverges from backend over time
- ⚠️ **Limited Storage**: IndexedDB quota ~50MB per origin (application-dependent)
- ⚠️ **No Conflict Resolution**: If backend data changes, browser still serves stale cache
- ⚠️ **Manual Index Management**: Line 128-137 checks for index existence (indicates index creation uncertainty)
- ⚠️ **Missing Clear/Eviction**: No bulk cache clearing strategy for low storage scenarios
- ⚠️ **Timestamp-Only Validation**: TTL relies only on insertion time, not update frequency

---

## 5. Cross-Layer Integration Issues

### 5.1 Database Layer Isolation

**Problem**: SQL schema (PostgreSQL) completely disconnected from ML schema (SQL Server)
- ML pipeline ingests from Kafka, creates its own schema
- No shared data model between transactional DB and ML feature store
- Dual data copies increase maintenance burden

**Current Flow**:
```
Kafka Events → ML Feature Store (SQL Server)
            → Application DB (PostgreSQL) [separate path]
```

### 5.2 Missing Data Lineage

- No tracking of which raw events produce which features
- Dataset versioning exists but no lineage to source events
- Model registry doesn't track training dataset used

### 5.3 R2 Sync Gaps

- **SQLite-specific**: Designed for ephemeral deployments with local SQLite, not PostgreSQL
- **Not integrated with PostgreSQL**: No mechanism to backup PostgreSQL to R2
- **Heartbeat mechanism missing**: No health checks to verify sync succeeded

---

## 6. Performance & Scalability Concerns

### 6.1 Missing Partitioning

High-volume tables need time-based partitioning:
- `route_search_events` - rows grow with each search
- `seat_availability` - refreshes daily for thousands of trains
- `sos_telemetry` - continuous location tracking

### 6.2 Join Complexity

The migration introduced multiple station tables but no clear denormalization strategy:
- `stations` vs `stations_master` vs `station_realtime_heartbeats`
- Queries may require 3-way joins degrading performance

### 6.3 IndexedDB Overflow

No strategy when browser storage quota exceeded:
- Application silently fails to cache
- User experience degrades without notification

---

## 7. Data Integrity & Consistency

### 7.1 Strengths
- ✅ Foreign key constraints across tables
- ✅ CHECK constraints in feature store
- ✅ UNIQUE constraints on identifiers (search_id, upi_tx_id)

### 7.2 Weaknesses
- ⚠️ **No Referential Integrity on JSON**: `booking_details` stored as JSON without validation
- ⚠️ **Soft Deletes Missing**: No audit trail for deleted records (e.g., cancelled_trains)
- ⚠️ **Timestamp Consistency**: Mixed UTC (DATETIMEOFFSET) and local time handling
- ⚠️ **No Change Data Capture**: Can't track who modified what when

---

## 8. Security Considerations

### 8.1 Strengths
- ✅ Encrypted credentials storage (`encrypted_irctc_creds`, `creds_iv` in users table)
- ✅ Credential versioning with IV
- ✅ Secure hash storage for UPI transactions

### 8.2 Weaknesses
- ⚠️ **Metadata Exposure**: SHA256 hashes visible in R2 metadata (doesn't leak data but reveals file sizes)
- ⚠️ **No Access Control**: R2 sync has no per-file ACL
- ⚠️ **Plain Text Logging**: Error messages may contain sensitive data
- ⚠️ **No Audit Trail**: R2 object metadata has no modification tracking

---

## 9. Recommendations

### 9.1 Critical (High Impact, High Effort)

1. **Unify ML and Application Schemas**
   - Create shared fact tables in PostgreSQL for Kafka events
   - Remove SQL Server dependency; migrate ML feature store to PostgreSQL
   - Implement data lineage tracking (event_id → feature_id → model_id)

2. **Partition High-Volume Tables**
   - Implement time-based partitioning on `route_search_events` (monthly)
   - Partition `seat_availability` by train_number or date
   - Set up archival/retention policies for old partitions

3. **Redesign Station Entity Model**
   - Consolidate `stations`, `stations_master`, `station_realtime_heartbeats` into single entity
   - Use event-sourced approach: `station_snapshots` (versioned) with `station_updates` (events)
   - Eliminates join complexity

### 9.2 High Priority (Medium Impact, Medium Effort)

4. **Improve R2 Sync Resilience**
   - Add retry logic with exponential backoff
   - Implement progress tracking and resumable uploads
   - Add health checks: verify sync integrity with block-level checksums
   - Support incremental sync (only changed blocks)

5. **Add Data Integrity Layer**
   - Implement soft deletes with audit timestamps
   - Add change data capture (CDC) events for audit trail
   - Validate JSON columns on insert/update (add NOT NULL constraints)

6. **Migration Management**
   - Split large migrations into <200-line chunks
   - Add migration guards (data validation before destructive operations)
   - Document business reasoning in migration comments
   - Test rollback procedures before production deployment

7. **Frontend Sync Strategy**
   - Implement backend-driven cache invalidation (WebSockets/Server-Sent Events)
   - Add storage quota monitoring with user notification
   - Clear cache on backend schema version mismatch

### 9.3 Medium Priority (Low Impact, Low Effort)

8. **Index Standardization**
   - Adopt consistent naming: `idx_tablename_columnname` for all indexes
   - Document slow query plans and justify complex indexes
   - Remove unused indexes (audit current usage)

9. **Monitoring & Observability**
   - Track schema migration execution time
   - Alert on R2 sync failures
   - Monitor IndexedDB quota usage per user
   - Log all schema changes with timestamp and user

10. **Documentation**
    - Document ER diagram (current schema complexity requires visual reference)
    - Add rationale for each major table (why it exists, what problem it solves)
    - Maintain migration changelog (not just code but business context)
    - Create runbook for disaster recovery scenarios

---

## 10. Architecture Decision Records (ADRs)

### ADR: SQL Server for ML Feature Store

**Current State**: Separate T-SQL schema in SQL Server  
**Issues**: 
- Not portable to PostgreSQL ecosystem
- Doubles maintenance burden
- Manual data sync between systems

**Decision**: Migrate feature store to PostgreSQL with proper time-series support
- Use PostgreSQL JSON operators for flexible schema
- Implement TimescaleDB extension for time-series optimization
- Single database reduces operational complexity

### ADR: R2 Sync for Ephemeral Deployments

**Current State**: 1-hour sync interval for SQLite backups  
**Issues**:
- Designed only for SQLite, not PostgreSQL
- Loses data if deployment crashes between syncs
- No conflict resolution strategy

**Decision**: 
- Keep for SQLite backup layer
- Add PostgreSQL WAL (Write-Ahead Logging) backup to R2
- Implement point-in-time recovery capability
- Reduce sync interval to 15 minutes for critical deployments

---

## Conclusion

The StartupRouteMaster database architecture demonstrates thoughtful domain modeling with comprehensive entity coverage. However, it suffers from:

1. **Fragmentation**: Multiple schemas (PostgreSQL, SQL Server, IndexedDB) create consistency challenges
2. **Complexity**: 80+ tables without clear organization or documentation
3. **Migration Risk**: Monolithic migrations and destructive operations threaten data safety
4. **Scalability**: Missing partitioning and optimization for high-volume tables
5. **Integration Gaps**: ML pipeline isolated from transactional data

**Priority**: Unify schemas and implement robust migration framework before adding new features. Current architecture can support medium-scale operations but needs architectural refactoring for high-growth scenarios.

**Estimated Effort**: 4-6 weeks for critical recommendations, 2-3 weeks additional for high-priority items.
