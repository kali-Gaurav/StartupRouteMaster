-- Route Engine Evolution - TIS Database Migration
-- Migration ID: 20260508_route_engine_tis
-- Description: Creates tables for Transfer Intelligence Score and Corridor Safety Bus
-- Author: VAULT (Database Lead)
-- Date: 2026-05-08

-- Run this migration with: psql -d routemaster -f 20260508_route_engine_tis.sql

-- ============================================================================
-- PART 1: Create Enum Types (if not exists)
-- ============================================================================

DO $$ BEGIN
    CREATE TYPE safety_event_type AS ENUM (
        'station_alert',
        'corridor_alert',
        'route_disruption',
        'weather_warning',
        'crowd_warning',
        'technical_issue'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE safety_severity AS ENUM (
        'critical',
        'high',
        'moderate',
        'low',
        'minimal'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE risk_level AS ENUM (
        'low',
        'medium',
        'high',
        'unknown'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- ============================================================================
-- PART 2: Create Tables
-- ============================================================================

-- Table: transfer_success_rates
-- Stores historical transfer success rates by station pair
CREATE TABLE IF NOT EXISTS transfer_success_rates (
    id BIGSERIAL PRIMARY KEY,
    station_pair VARCHAR(10) NOT NULL,
    transfer_station VARCHAR(10) NOT NULL,
    arrival_train_prefix VARCHAR(5) NOT NULL,
    departure_train_prefix VARCHAR(5) NOT NULL,
    connection_time_bucket INTEGER NOT NULL,
    success_count INTEGER NOT NULL DEFAULT 0,
    total_count INTEGER NOT NULL DEFAULT 0,
    success_rate DECIMAL(5,4) NOT NULL DEFAULT 0.0,
    avg_delay_minutes INTEGER DEFAULT 0,
    sample_size INTEGER NOT NULL DEFAULT 0,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT uq_station_pair UNIQUE (
        station_pair, 
        transfer_station, 
        arrival_train_prefix, 
        departure_train_prefix, 
        connection_time_bucket
    )
);

-- Indexes for transfer_success_rates
CREATE INDEX IF NOT EXISTS idx_transfer_station ON transfer_success_rates(transfer_station);
CREATE INDEX IF NOT EXISTS idx_tsr_station_pair ON transfer_success_rates(station_pair);
CREATE INDEX IF NOT EXISTS idx_tsr_success_rate ON transfer_success_rates(success_rate DESC);
CREATE INDEX IF NOT EXISTS idx_tsr_last_updated ON transfer_success_rates(last_updated DESC);

COMMENT ON TABLE transfer_success_rates IS 'Historical transfer success rates by station pair for TIS scoring';
COMMENT ON COLUMN transfer_success_rates.station_pair IS 'Source-destination pair (e.g., NDLS-BCT)';
COMMENT ON COLUMN transfer_success_rates.transfer_station IS 'Transfer station code';
COMMENT ON COLUMN transfer_success_rates.arrival_train_prefix IS 'Train number prefix (e.g., 1200 for 12001, 12002)';
COMMENT ON COLUMN transfer_success_rates.departure_train_prefix IS 'Departure train number prefix';
COMMENT ON COLUMN transfer_success_rates.connection_time_bucket IS 'Connection time bucket (10, 15, 20, 25, 30, 45, 60+)';
COMMENT ON COLUMN transfer_success_rates.success_rate IS 'Historical success rate (0.0 to 1.0)';

-- ============================================================================

-- Table: safety_events
-- Stores real-time and historical safety events
CREATE TABLE IF NOT EXISTS safety_events (
    id BIGSERIAL PRIMARY KEY,
    event_id VARCHAR(50) NOT NULL UNIQUE,
    event_type safety_event_type NOT NULL,
    corridor VARCHAR(20) NOT NULL,
    stations TEXT[] NOT NULL,
    severity safety_severity NOT NULL,
    description TEXT NOT NULL,
    source VARCHAR(100),
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE,
    safety_penalty DECIMAL(4,3) DEFAULT 0.5,
    created_by VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for safety_events
CREATE INDEX IF NOT EXISTS idx_se_corridor ON safety_events(corridor);
CREATE INDEX IF NOT EXISTS idx_se_stations ON safety_events USING GIN(stations);
CREATE INDEX IF NOT EXISTS idx_se_event_type ON safety_events(event_type);
CREATE INDEX IF NOT EXISTS idx_se_severity ON safety_events(severity);
CREATE INDEX IF NOT EXISTS idx_se_active ON safety_events(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_se_time ON safety_events(start_time DESC);

COMMENT ON TABLE safety_events IS 'Safety events for corridor-based route filtering';
COMMENT ON COLUMN safety_events.event_id IS 'Unique event identifier';
COMMENT ON COLUMN safety_events.corridor IS 'Affected corridor (e.g., NDLS-BCT)';
COMMENT ON COLUMN safety_events.stations IS 'Array of affected station codes';
COMMENT ON COLUMN safety_events.safety_penalty IS 'Penalty to apply to routes (0.0 to 1.0)';

-- ============================================================================

-- Table: corridor_status
-- Current safety status for each corridor (cache table)
CREATE TABLE IF NOT EXISTS corridor_status (
    corridor VARCHAR(20) PRIMARY KEY,
    safety_score DECIMAL(5,4) NOT NULL DEFAULT 1.0,
    risk_level safety_severity NOT NULL DEFAULT 'minimal',
    active_event_count INTEGER NOT NULL DEFAULT 0,
    affected_stations TEXT[] DEFAULT '{}',
    last_safety_update TIMESTAMP WITH TIME ZONE,
    last_event_time TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for corridor_status
CREATE INDEX IF NOT EXISTS idx_cs_safety_score ON corridor_status(safety_score);
CREATE INDEX IF NOT EXISTS idx_cs_risk_level ON corridor_status(risk_level);

COMMENT ON TABLE corridor_status IS 'Cached current safety status for fast API responses';

-- ============================================================================

-- Table: train_on_time_performance
-- Historical on-time performance by train
CREATE TABLE IF NOT EXISTS train_on_time_performance (
    id BIGSERIAL PRIMARY KEY,
    train_number VARCHAR(10) NOT NULL,
    station_code VARCHAR(10) NOT NULL,
    date DATE NOT NULL,
    scheduled_arrival TIME,
    actual_arrival TIME,
    scheduled_departure TIME,
    actual_departure TIME,
    delay_minutes INTEGER DEFAULT 0,
    on_time BOOLEAN GENERATED ALWAYS AS (delay_minutes <= 15) STORED,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT uq_train_station_date UNIQUE (train_number, station_code, date)
);

-- Indexes for train_on_time_performance
CREATE INDEX IF NOT EXISTS idx_top_train_number ON train_on_time_performance(train_number);
CREATE INDEX IF NOT EXISTS idx_top_station_code ON train_on_time_performance(station_code);
CREATE INDEX IF NOT EXISTS idx_top_date ON train_on_time_performance(date DESC);
CREATE INDEX IF NOT EXISTS idx_top_delay ON train_on_time_performance(delay_minutes DESC);

COMMENT ON TABLE train_on_time_performance IS 'Historical train delay data for connection time calculations';

-- ============================================================================

-- Table: tis_daily_stats
-- Daily aggregated TIS statistics for analytics
CREATE TABLE IF NOT EXISTS tis_daily_stats (
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

-- Indexes for tis_daily_stats
CREATE INDEX IF NOT EXISTS idx_tds_date ON tis_daily_stats(date DESC);
CREATE INDEX IF NOT EXISTS idx_tds_station ON tis_daily_stats(station_pair);

COMMENT ON TABLE tis_daily_stats IS 'Daily aggregated TIS statistics for monitoring and analytics';

-- ============================================================================
-- PART 3: Create Materialized Views
-- ============================================================================

-- Materialized View: mv_corridor_safety_summary
-- Aggregated safety metrics by corridor
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_corridor_safety_summary AS
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
GROUP BY corridor
WITH DATA;

-- Index for materialized view
CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_corridor ON mv_corridor_safety_summary(corridor);

COMMENT ON MATERIALIZED VIEW mv_corrier_safety_summary IS 'Aggregated safety metrics by corridor (refresh daily)';

-- ============================================================================
-- PART 4: Create Functions and Triggers
-- ============================================================================

-- Function: update_updated_at_column()
-- Automatically updates the updated_at column on modification
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger: update_corridor_status_updated_at
CREATE TRIGGER update_corridor_status_updated_at
    BEFORE UPDATE ON corridor_status
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger: update_safety_events_updated_at
CREATE TRIGGER update_safety_events_updated_at
    BEFORE UPDATE ON safety_events
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- PART 5: Create Views for API
-- ============================================================================

-- View: v_active_safety_events
-- Returns active safety events for API consumption
CREATE OR REPLACE VIEW v_active_safety_events AS
SELECT 
    event_id,
    event_type,
    corridor,
    stations,
    severity,
    description,
    start_time,
    end_time,
    safety_penalty
FROM safety_events
WHERE is_active = TRUE
ORDER BY 
    CASE severity
        WHEN 'critical' THEN 1
        WHEN 'high' THEN 2
        WHEN 'moderate' THEN 3
        WHEN 'low' THEN 4
        WHEN 'minimal' THEN 5
    END,
    start_time DESC;

COMMENT ON VIEW v_active_safety_events IS 'Active safety events for API responses';

-- ============================================================================
-- PART 6: Insert Initial Data
-- ============================================================================

-- Insert default corridor statuses for popular corridors
INSERT INTO corridor_status (corridor, safety_score, risk_level, active_event_count)
VALUES 
    ('NDLS-BCT', 1.0, 'minimal', 0),
    ('NDLS-CNB', 1.0, 'minimal', 0),
    ('BCT-ADI', 1.0, 'minimal', 0),
    ('MAS-BCT', 1.0, 'minimal', 0),
    ('NDLS-BLR', 1.0, 'minimal', 0)
ON CONFLICT (corridor) DO NOTHING;

-- Insert sample transfer success rates for testing
INSERT INTO transfer_success_rates 
    (station_pair, transfer_station, arrival_train_prefix, departure_train_prefix, 
     connection_time_bucket, success_count, total_count, success_rate, sample_size)
VALUES
    ('NDLS-BCT', 'BCT', '1200', '1295', 30, 1523, 1786, 0.8523, 1523),
    ('NDLS-BCT', 'BCT', '1200', '1295', 45, 892, 966, 0.9234, 892),
    ('NDLS-CNB', 'CNB', '1200', '1210', 25, 456, 523, 0.8719, 456),
    ('BCT-ADI', 'ADI', '1900', '1915', 35, 234, 267, 0.8764, 234)
ON CONFLICT DO NOTHING;

-- ============================================================================
-- PART 7: Grant Permissions (adjust as needed for your setup)
-- ============================================================================

-- GRANT SELECT ON ALL TABLES IN SCHEMA public TO api_user;
-- GRANT INSERT, UPDATE, DELETE ON safety_events TO admin_user;
-- GRANT SELECT ON transfer_success_rates TO readonly_user;

-- ============================================================================
-- Verification Queries
-- ============================================================================

-- Check table sizes
-- SELECT 
--     relname AS table_name,
--     pg_size_pretty(pg_relation_size(relid)) AS size
-- FROM pg_stat_user_tables
-- WHERE schemaname = 'public'
-- ORDER BY pg_relation_size(relid) DESC;

-- Check index sizes
-- SELECT 
--     indexname,
--     pg_size_pretty(pg_relation_size(relid)) AS size
-- FROM pg_stat_user_indexes
-- WHERE schemaname = 'public';

-- ============================================================================
-- Rollback Script (if needed)
-- ============================================================================

-- DROP TABLE IF EXISTS transfer_success_rates CASCADE;
-- DROP TABLE IF EXISTS safety_events CASCADE;
-- DROP TABLE IF EXISTS corridor_status CASCADE;
-- DROP TABLE IF EXISTS train_on_time_performance CASCADE;
-- DROP TABLE IF EXISTS tis_daily_stats CASCADE;
-- DROP MATERIALIZED VIEW IF EXISTS mv_corridor_safety_summary CASCADE;
-- DROP TYPE IF EXISTS safety_event_type CASCADE;
-- DROP TYPE IF EXISTS safety_severity CASCADE;
-- DROP TYPE IF EXISTS risk_level CASCADE;
-- DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE;

-- ============================================================================
-- Migration Complete
-- ============================================================================

DO $$ 
BEGIN 
    RAISE NOTICE 'Migration 20260508_route_engine_tis completed successfully';
    RAISE NOTICE 'Tables created: transfer_success_rates, safety_events, corridor_status, train_on_time_performance, tis_daily_stats';
    RAISE NOTICE 'Materialized views created: mv_corridor_safety_summary';
    RAISE NOTICE 'Run "SELECT refresh_materialized_view CONCURRENTLY mv_corridor_safety_summary;" to initialize';
END $$;