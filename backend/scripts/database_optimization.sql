-- Database Performance Optimization Script
-- Phase 1: Table Partitioning, Index Tuning, and Materialized Views
-- Target: Sub-10ms query performance at scale

BEGIN;

-- =============================================================================
-- STEP 1: TABLE PARTITIONING (SEAT INVENTORY)
-- =============================================================================

-- 1. Rename existing seat_inventory to backed up name
ALTER TABLE IF EXISTS seat_inventory RENAME TO seat_inventory_old;

-- 2. Create partitioned seat_inventory table
-- Note: PK must include the partition key (date)
CREATE TABLE seat_inventory (
    id VARCHAR(36) NOT NULL,
    trip_id INTEGER NOT NULL,
    segment_from_stop_id INTEGER NOT NULL,
    segment_to_stop_id INTEGER NOT NULL,
    date DATE NOT NULL,
    quota_type VARCHAR(50) NOT NULL,
    total_seats INTEGER NOT NULL,
    available_seats INTEGER NOT NULL,
    booked_seats INTEGER NOT NULL DEFAULT 0,
    blocked_seats INTEGER NOT NULL DEFAULT 0,
    current_waitlist_position INTEGER NOT NULL DEFAULT 0,
    rac_count INTEGER NOT NULL DEFAULT 0,
    last_updated TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (id, date)
) PARTITION BY RANGE (date);

-- 3. Create partitions for the next 6 months (Dynamic generation usually better, but for rollout we do it manually)
CREATE TABLE seat_inventory_2026_02 PARTITION OF seat_inventory 
    FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');
CREATE TABLE seat_inventory_2026_03 PARTITION OF seat_inventory 
    FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');
CREATE TABLE seat_inventory_2026_04 PARTITION OF seat_inventory 
    FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');
CREATE TABLE seat_inventory_2026_05 PARTITION OF seat_inventory 
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
CREATE TABLE seat_inventory_2026_06 PARTITION OF seat_inventory 
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
CREATE TABLE seat_inventory_default PARTITION OF seat_inventory DEFAULT;

-- 4. Move data from old table to new if any exists
-- Wrapped in DO block to handle table existence check
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename  = 'seat_inventory_old') THEN
        INSERT INTO seat_inventory (id, trip_id, segment_from_stop_id, segment_to_stop_id, date, quota_type, total_seats, available_seats, booked_seats, blocked_seats, current_waitlist_position, rac_count, last_updated, created_at)
        SELECT id, trip_id, segment_from_stop_id, segment_to_stop_id, date, quota_type, total_seats, available_seats, booked_seats, blocked_seats, current_waitlist_position, rac_count, last_updated, created_at
        FROM seat_inventory_old;
    END IF;
END $$;

-- =============================================================================
-- STEP 2: TABLE PARTITIONING (PNR RECORDS / BOOKINGS)
-- =============================================================================

ALTER TABLE IF EXISTS pnr_records RENAME TO pnr_records_old;

CREATE TABLE pnr_records (
    id VARCHAR(36) NOT NULL,
    pnr_number VARCHAR(10) NOT NULL,
    user_id VARCHAR(36) NOT NULL,
    travel_date DATE NOT NULL,
    total_passengers INTEGER NOT NULL,
    total_fare NUMERIC(10, 2) NOT NULL,
    booking_status VARCHAR(50) NOT NULL,
    payment_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    payment_id VARCHAR(100),
    segments_json JSON NOT NULL,
    cancelled_at TIMESTAMP WITHOUT TIME ZONE,
    refund_amount NUMERIC(10, 2),
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (pnr_number, travel_date)
) PARTITION BY RANGE (travel_date);

CREATE TABLE pnr_records_2026_02 PARTITION OF pnr_records FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');
CREATE TABLE pnr_records_2026_03 PARTITION OF pnr_records FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');
CREATE TABLE pnr_records_2026_04 PARTITION OF pnr_records FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');
CREATE TABLE pnr_records_default PARTITION OF pnr_records DEFAULT;

DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename  = 'pnr_records_old') THEN
        INSERT INTO pnr_records SELECT * FROM pnr_records_old;
    END IF;
END $$;


-- =============================================================================
-- STEP 3: MATERIALIZED VIEWS (FOR AGGREGATED QUERIES)
-- =============================================================================

-- Availability Summary View (Refreshed every 60s in production)
CREATE MATERIALIZED VIEW availability_summary_mv AS
SELECT 
    trip_id, 
    date, 
    quota_type,
    SUM(available_seats) as total_available,
    SUM(booked_seats) as total_booked,
    SUM(total_seats) as capacity,
    MIN(current_waitlist_position) as min_wl
FROM seat_inventory
GROUP BY trip_id, date, quota_type;

CREATE INDEX idx_avail_mv_lookup ON availability_summary_mv (trip_id, date, quota_type);

-- Train Status Summary View
CREATE MATERIALIZED VIEW train_status_summary_mv AS
SELECT 
    trip_id,
    train_number,
    status,
    AVG(delay_minutes) as mean_delay,
    COUNT(*) as state_updates
FROM train_states
GROUP BY trip_id, train_number, status;

-- =============================================================================
-- STEP 4: INDEX OPTIMIZATION (COMPOSITE & BRIN)
-- =============================================================================

-- Composite index for seat search - critical for performance
CREATE INDEX idx_seat_search_composite ON seat_inventory (trip_id, date, segment_from_stop_id, segment_to_stop_id, quota_type);

-- BRIN index for date-based range scans on large tables (very efficient for massive tables)
CREATE INDEX idx_seat_inventory_date_brin ON seat_inventory USING BRIN (date);
CREATE INDEX idx_pnr_date_brin ON pnr_records USING BRIN (travel_date);

-- Index for segment overlap checks
CREATE INDEX idx_segment_overlap ON seat_inventory (trip_id, date, segment_from_stop_id, segment_to_stop_id);

COMMIT;
