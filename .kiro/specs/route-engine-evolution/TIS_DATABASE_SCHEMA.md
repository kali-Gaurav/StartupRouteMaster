# Route Engine Evolution - TIS Database Schema

**Feature:** Transfer Intelligence Score (TIS)  
**Owner:** VAULT (Database Lead)  
**Status:** 🔄 DESIGN COMPLETE  
**Date:** 2026-05-08

---

## Overview

This document defines the database schema required for the Transfer Intelligence Score (TIS) feature and Corridor Safety Bus. The schema supports:

- Historical connection success rates by station pair
- Safety events tracking
- Corridor status monitoring
- Real-time safety scoring

---

## Schema Design Principles

1. **Performance:** Index-heavy design for O(1) lookups
2. **Scalability:** Partitioned by date for safety events
3. **Consistency:** Foreign key relationships for data integrity
4. **Analytics:** Materialized views for corridor aggregates

---

## Database: PostgreSQL 14+

---

## Tables

### 1. `transfer_success_rates`

Stores historical transfer success rates by station pair.

```sql
CREATE TABLE transfer_success_rates (
    id BIGSERIAL PRIMARY KEY,
    station_pair VARCHAR(10) NOT NULL,  -- e.g., 'NDLS-BCT'
    transfer_station VARCHAR(10) NOT NULL,  -- e.g., 'BCT'
    arrival_train_prefix VARCHAR(5) NOT NULL,  -- e.g., '1200' for 12001, 12002
    departure_train_prefix VARCHAR(5) NOT NULL,
    connection_time_bucket INTEGER NOT NULL,  -- 10, 15, 20, 25, 30, 45, 60+
    success_count INTEGER NOT NULL DEFAULT 0,
    total_count INTEGER NOT NULL DEFAULT 0,
    success_rate DECIMAL(5,4) NOT NULL DEFAULT 0.0,
    avg_delay_minutes INTEGER DEFAULT 0,
    sample_size INTEGER NOT NULL DEFAULT 0,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT uq_station_pair UNIQUE (station_pair, transfer_station, 
                                       arrival_train_prefix, departure_train_prefix, 
                                       connection_time_bucket)
);

-- Indexes for fast lookups
CREATE INDEX idx_transfer_station ON transfer_success_rates(transfer_station);
CREATE INDEX idx_station_pair ON transfer_success_rates(station_pair);
CREATE INDEX idx_success_rate ON transfer_success_rates(success_rate DESC);
CREATE INDEX idx_last_updated ON transfer_success_rates(last_updated DESC);
```

**Purpose:** O(1) lookup of historical success rates for TIS scoring

**Sample Data:**
```
station_pair | transfer_station | arrival_train_prefix | departure_train_prefix | connection_time_bucket | success_rate | sample_size
-------------|------------------|----------------------|------------------------|------------------------|--------------|------------
NDLS-BCT     | BCT              | 1200                 | 1295                   | 30                     | 0.8523       | 1523
NDLS-BCT     | BCT              | 1200                 | 1295                   | 45                     | 0.9234       | 892
```

---

### 2. `safety_events`

Stores real-time and historical safety events.

```sql
CREATE TYPE safety_event_type AS ENUM (
    'station_alert',
    'corridor_alert',
    'route_disruption',
    'weather_warning',
    'crowd_warning',
    'technical_issue'
);

CREATE TYPE safety_severity AS ENUM (
    'critical',
    'high',
    'moderate',
    'low',
    'minimal'
);

CREATE TABLE safety_events (
    id BIGSERIAL PRIMARY KEY,
    event_id VARCHAR(50) NOT NULL UNIQUE,
    event_type safety_event_type NOT NULL,
    corridor VARCHAR(20) NOT NULL,  -- e.g., 'NDLS-BCT'
    stations TEXT[] NOT NULL,  -- Array of affected station codes
    severity safety_severity NOT NULL,
    description TEXT NOT NULL,
    source VARCHAR(100),  -- e.g., 'SOS', 'weather_api', 'manual'
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE,
    safety_penalty DECIMAL(4,3) DEFAULT 0.5,  -- 0.0 to 1.0
    created_by VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for event queries
CREATE INDEX idx_event_corridor ON safety_events(corridor);
CREATE INDEX idx_event_stations ON safety_events USING GIN(stations);
CREATE INDEX idx_event_type ON safety_events(event_type);
CREATE INDEX idx_event_severity ON safety_events(severity);
CREATE INDEX idx_event_active ON safety_events(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_event_time ON safety_events(start_time DESC);

-- Partition by month for performance
CREATE TABLE safety_events_2026_05 PARTITION OF safety_events
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
CREATE TABLE safety_events_2026_06 PARTITION OF safety_events
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
```

**Purpose:** Track all safety events for corridor-based filtering

**Sample Data:**
```
event_id      | event_type       | corridor  | stations      | severity | description                    | is_active
--------------|------------------|-----------|---------------|----------|--------------------------------|----------
evt-001       | corridor_alert   | NDLS-BCT  | {NDLS,BCT}    | moderate | Heavy crowd expected           | true
evt-002       | weather_warning  | NDLS-BCT  | {NDLS,GWL}    | low      | Light rain forecast            | true
```

---

### 3. `corridor_status`

Current safety status for each corridor (materialized view + cache).

```sql
CREATE TABLE corridor_status (
    corridor VARCHAR(20) PRIMARY KEY,  -- e.g., 'NDLS-BCT'
    safety_score DECIMAL(5,4) NOT NULL DEFAULT 1.0,  -- 0.0 to 1.0
    risk_level safety_severity NOT NULL DEFAULT 'minimal',
    active_event_count INTEGER NOT NULL DEFAULT 0,
    affected_stations TEXT[] DEFAULT '{}',
    last_safety_update TIMESTAMP WITH TIME ZONE,
    last_event_time TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for fast corridor lookups
CREATE INDEX idx_corridor_status ON corridor_status(safety_score);
CREATE INDEX idx_risk_level ON corridor_status(risk_level);
```

**Purpose:** Cached current safety status for fast API responses

**Sample Data:**
```
corridor  | safety_score | risk_level | active_event_count | affected_stations
----------|--------------|------------|--------------------|-------------------
NDLS-BCT  | 0.9234       | low        | 0                  | {}
NDLS-CNB  | 0.7856       | moderate   | 1                  | {CNB}
```

---

### 4. `train_on_time_performance`

Historical on-time performance by train.

```sql
CREATE TABLE train_on_time_performance (
    id BIGSERIAL PRIMARY KEY,
    train_number VARCHAR(10) NOT NULL,
    station_code VARCHAR(10) NOT NULL,
    date DATE NOT NULL,
    scheduled_arrival TIME,
    actual_arrival TIME,
    scheduled_departure TIME,
    actual_departure,
    delay_minutes INTEGER DEFAULT 0,
    on_time BOOLEAN GENERATED ALWAYS AS (delay_minutes <= 15) STORED,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT uq_train_station_date UNIQUE (train_number, station_code, date)
);

-- Indexes
CREATE INDEX idx_train_number ON train_on_time_performance(train_number);
CREATE INDEX idx_station_code ON train_on_time_performance(station_code);
CREATE INDEX idx_date ON train_on_time_performance(date DESC);
CREATE INDEX idx_delay ON train_on_time_performance(delay_minutes DESC);
```

**Purpose:** Track train delays for connection time calculations

---

### 5. `tis_daily_stats`

Daily aggregated TIS statistics for analytics.

```sql
CREATE TABLE tis_daily_stats (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL,
    station_pair VARCHAR(10) NOT NULL,
    transfer_station VARCHAR(10) NOT NULL,
    avg_tis_score DECIMAL(5,2),
    avg_connection_time DECIMAL(5,2),
    total_connections INTEGER,
    successful_connections INTEGER,
    failed_connections INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT uq_station_pair_date UNIQUE (date, station_pair, transfer_station)
);

-- Indexes
CREATE INDEX idx_tis_stats_date ON tis_daily_stats(date DESC);
CREATE INDEX idx_tis_stats_station ON tis_daily_stats(station_pair);
```

**Purpose:** Analytics and monitoring of TIS performance

---

## Materialized Views

### `mv_corridor_safety_summary`

Aggregated safety metrics by corridor.

```sql
CREATE MATERIALIZED VIEW mv_corridor_safety_summary AS
SELECT 
    corridor,
    COUNT(*) FILTER (WHERE is_active) AS active_events,
    COUNT(*) AS total_events_7d,
    AVG(CASE WHEN is_active THEN safety_penalty ELSE NULL END) AS avg_active_penalty,
    MAX(CASE WHEN is_active THEN severity ELSE NULL END) AS max_severity,
    MIN(safety_score) AS min_safety_score,
    NOW() - MAX(start_time) AS longest_active_duration
FROM safety_events
WHERE start_time > NOW() - INTERVAL '7 days'
GROUP BY corridor;

-- Refresh daily
CREATE UNIQUE INDEX idx_mv_corridor ON mv_corridor_safety_summary(corridor);
```

---

## Migration Strategy

### Phase 1: Create Tables (Zero Downtime)

```sql
-- Run in transaction
BEGIN;

-- Create tables (without constraints initially)
CREATE TABLE IF NOT EXISTS transfer_success_rates (...);
CREATE TABLE IF NOT EXISTS safety_events (...);
CREATE TABLE IF NOT EXISTS corridor_status (...);
CREATE TABLE IF NOT EXISTS train_on_time_performance (...);
CREATE TABLE IF NOT EXISTS tis_daily_stats (...);

COMMIT;
```

### Phase 2: Backfill Historical Data

```python
# Backfill script for transfer_success_rates
async def backfill_transfer_rates():
    """Backfill historical connection data"""
    # Process historical booking data
    # Calculate success rates by station pair
    # Insert into transfer_success_rates
```

### Phase 3: Add Constraints and Indexes

```sql
-- After backfill, add constraints
ALTER TABLE transfer_success_rates 
    ADD CONSTRAINT uq_station_pair UNIQUE (...);

-- Create partitions for safety_events
CREATE TABLE safety_events_2026_05 PARTITION OF safety_events
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
```

---

## API Integration

### Get Transfer Success Rate

```python
async def get_transfer_success_rate(
    station_pair: str,
    transfer_station: str,
    arrival_train_prefix: str,
    departure_train_prefix: str,
    connection_time: int
) -> float:
    """Get historical success rate for TIS calculation"""
    # Query transfer_success_rates table
    # Return success_rate or default 0.65
```

### Get Corridor Safety Status

```python
async def get_corridor_safety(corridor: str) -> dict:
    """Get current safety status for a corridor"""
    # Query corridor_status table
    # If not cached, calculate from safety_events
    # Return safety_score and risk_level
```

### Publish Safety Event

```python
async def publish_safety_event(event: SafetyEvent) -> str:
    """Publish new safety event"""
    # Insert into safety_events
    # Update corridor_status
    # Invalidate related caches
    # Return event_id
```

---

## Performance Targets

| Operation | Target Latency | Index Required |
|-----------|----------------|----------------|
| Get transfer success rate | < 10ms | idx_station_pair |
| Get corridor safety | < 5ms | PRIMARY KEY |
| Publish safety event | < 50ms | idx_corridor |
| Query active events | < 20ms | idx_event_active |

---

## Cost Estimation

| Resource | Size | Monthly Cost |
|----------|------|--------------|
| PostgreSQL (RDS) | db.t3.medium | $50/month |
| Storage | 50GB | $10/month |
| Backups | 50GB | $5/month |
| **Total** | | **$65/month** |

---

## Action Items

| ID | Action | Owner | Status |
|----|--------|-------|--------|
| DB-01 | Create tables in staging | VAULT | 🔴 PENDING |
| DB-02 | Design backfill script | VAULT | 🔴 PENDING |
| DB-03 | Create partitions for safety_events | VAULT | 🔴 PENDING |
| DB-04 | Add indexes for performance | VAULT | 🔴 PENDING |
| DB-05 | Create materialized views | VAULT | 🔴 PENDING |
| DB-06 | Test migration with production data | VAULT | 🔴 PENDING |

---

## Related Documentation

- [API Contracts](../API_CONTRACTS.md)
- [Security Review](./SECURITY_REVIEW.md)
- [Transfer Intelligence Service](../../backend/services/routing/transfer_intelligence.py)

---

**Document Version:** 1.0  
**Next Review:** 2026-05-15