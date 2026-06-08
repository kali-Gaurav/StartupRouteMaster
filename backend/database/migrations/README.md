# Route Engine Evolution - Database Migrations

This directory contains database migrations for the Route Engine Evolution features.

## Migration Files

| File | Description | Status |
|------|-------------|--------|
| `20260508_route_engine_tis.sql` | TIS and Safety Bus tables | ✅ Ready |

## Running Migrations

### Development (Local PostgreSQL)

```bash
# Run migration
psql -d routemaster -f 20260508_route_engine_tis.sql

# Verify tables created
psql -d routemaster -c "\dt transfer_*"
psql -d routemaster -c "\dt safety_*"
psql -d routemaster -c "\dt corridor_*"
```

### Staging/Production (AWS RDS)

```bash
# Using psql with SSL
psql "host=routemaster-db.xxxxx.rds.amazonaws.com dbname=routemaster user=admin sslmode=require" \
  -f 20260508_route_engine_tis.sql

# Or using AWS CLI
aws rds download-db-log-file-portion \
  --db-instance-identifier routemaster-staging \
  --log-file-name error/postgresql.log.0000000001 \
  --starting-token 0 \
  --output text
```

### Using Alembic (Recommended)

```bash
# Create new migration
alembic revision -m "add_route_engine_tis"

# Generate migration from SQL files
alembic upgrade head

# Check current version
alembic current
```

## Table Overview

### Core Tables

| Table | Purpose | Size Estimate |
|-------|---------|---------------|
| `transfer_success_rates` | Historical connection success rates | ~10MB |
| `safety_events` | Real-time safety events | ~5MB |
| `corridor_status` | Cached safety status | ~1MB |
| `train_on_time_performance` | Train delay data | ~50MB |
| `tis_daily_stats` | Daily TIS analytics | ~2MB |

### Materialized Views

| View | Purpose | Refresh Frequency |
|------|---------|-------------------|
| `mv_corridor_safety_summary` | Aggregated safety metrics | Daily |

## Initial Data

The migration includes:
- Default corridor statuses for popular routes (NDLS-BCT, NDLS-CNB, etc.)
- Sample transfer success rates for testing
- View definitions for API consumption

## Rollback

To rollback the migration:

```sql
-- Run rollback script at the end of the migration file
DROP TABLE IF EXISTS transfer_success_rates CASCADE;
DROP TABLE IF EXISTS safety_events CASCADE;
DROP TABLE IF EXISTS corridor_status CASCADE;
DROP TABLE IF EXISTS train_on_time_performance CASCADE;
DROP TABLE IF EXISTS tis_daily_stats CASCADE;
DROP MATERIALIZED VIEW IF EXISTS mv_corridor_safety_summary CASCADE;
DROP TYPE IF EXISTS safety_event_type CASCADE;
DROP TYPE IF EXISTS safety_severity CASCADE;
DROP TYPE IF EXISTS risk_level CASCADE;
```

## Performance Considerations

### Indexes

All necessary indexes are created automatically:
- `idx_transfer_station` - Fast lookup by transfer station
- `idx_tsr_station_pair` - Fast corridor lookups
- `idx_se_active` - Partial index for active events only
- `idx_se_stations` - GIN index for array queries

### Partitioning

The `safety_events` table should be partitioned by date for large datasets:

```sql
-- Example partition creation
CREATE TABLE safety_events_2026_05 PARTITION OF safety_events
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');

CREATE TABLE safety_events_2026_06 PARTITION OF safety_events
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
```

### Vacuum and Analyze

Regular maintenance is recommended:

```sql
-- Weekly maintenance
VACUUM ANALYZE transfer_success_rates;
VACUUM ANALYZE safety_events;
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_corridor_safety_summary;
```

## Monitoring

### Query Performance

Monitor slow queries:

```sql
-- Log slow queries (add to postgresql.conf)
log_min_duration_statement = 1000

-- Check for slow queries
SELECT 
    query,
    calls,
    mean_time,
    total_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;
```

### Table Statistics

```sql
-- Check table sizes
SELECT 
    relname AS table_name,
    pg_size_pretty(pg_relation_size(relid)) AS size,
    n_live_tup AS row_count
FROM pg_stat_user_tables
WHERE schemaname = 'public'
ORDER BY pg_relation_size(relid) DESC;
```

## Related Documentation

- [TIS Database Schema](../../.kiro/specs/route-engine-evolution/TIS_DATABASE_SCHEMA.md)
- [API Contracts](../../.kiro/specs/route-engine-evolution/API_CONTRACTS.md)
- [Security Review](../../.kiro/specs/route-engine-evolution/SECURITY_REVIEW.md)