-- ============================================================================
-- Feature #5: Database Optimization - Production-Ready Schema
-- Date: 2026-07-29
-- Purpose: Add performance indexes, materialized views, and data retention
-- ============================================================================

-- ============================================================================
-- PHASE 1: ADD PERFORMANCE INDEXES
-- ============================================================================

-- RouteKnowledge indexes (critical for candidate generation)
CREATE INDEX IF NOT EXISTS idx_route_knowledge_search_count
  ON route_knowledge(search_count DESC)
  WHERE search_count > 0;

CREATE INDEX IF NOT EXISTS idx_route_knowledge_demand_score
  ON route_knowledge(demand_score DESC)
  WHERE reliability_score >= 0.75;

CREATE INDEX IF NOT EXISTS idx_route_knowledge_reliability
  ON route_knowledge(reliability_score DESC);

CREATE INDEX IF NOT EXISTS idx_route_knowledge_source_dest
  ON route_knowledge(source_code, destination_code);

CREATE INDEX IF NOT EXISTS idx_route_knowledge_frequency
  ON route_knowledge(frequency_daily DESC);

-- DemandSnapshot indexes (for trending routes)
CREATE INDEX IF NOT EXISTS idx_demand_snapshot_source_dest_date
  ON demand_snapshots(source_code, destination_code, travel_date DESC);

CREATE INDEX IF NOT EXISTS idx_demand_snapshot_demand_score
  ON demand_snapshots(demand_score DESC, travel_date DESC)
  WHERE demand_score >= 0.7;

CREATE INDEX IF NOT EXISTS idx_demand_snapshot_search_count
  ON demand_snapshots(search_count DESC, travel_date DESC);

CREATE INDEX IF NOT EXISTS idx_demand_snapshot_occupancy
  ON demand_snapshots(occupancy_rate DESC, travel_date DESC);

CREATE INDEX IF NOT EXISTS idx_demand_snapshot_date
  ON demand_snapshots(travel_date DESC);

-- UserTravelPreference indexes (for personalization)
CREATE INDEX IF NOT EXISTS idx_user_travel_preference_confidence
  ON user_travel_preferences(preference_confidence DESC, user_id);

CREATE INDEX IF NOT EXISTS idx_user_travel_preference_total_interactions
  ON user_travel_preferences(total_interactions DESC);

-- SearchOutcome indexes (for history & deduplication)
CREATE INDEX IF NOT EXISTS idx_search_outcome_user_date
  ON search_outcomes(user_id, created_at DESC);

-- ============================================================================
-- PHASE 2: ADD UNIQUENESS CONSTRAINTS (if not exists)
-- ============================================================================

-- Journey ID uniqueness for deduplication
-- Note: If this fails, run the deduplication script first:
-- DELETE FROM search_outcomes WHERE journey_id IN (
--   SELECT journey_id FROM search_outcomes GROUP BY journey_id HAVING COUNT(*) > 1
-- );
ALTER TABLE search_outcomes
  ADD CONSTRAINT uk_search_outcome_journey_id UNIQUE (journey_id);

-- ============================================================================
-- PHASE 3: CREATE MATERIALIZED VIEWS
-- ============================================================================

-- View 1: Trending Routes (top routes by combined popularity metrics)
CREATE VIEW IF NOT EXISTS trending_routes AS
SELECT
  rk.id,
  rk.source_code,
  rk.destination_code,
  rk.search_count,
  rk.booking_count,
  rk.reliability_score,
  rk.avg_fare,
  rk.conversion_rate,
  (
    (rk.search_count / NULLIF((SELECT MAX(search_count) FROM route_knowledge), 0) * 0.3) +
    (rk.booking_count / NULLIF((SELECT MAX(booking_count) FROM route_knowledge), 0) * 0.3) +
    (rk.reliability_score * 0.2) +
    (rk.conversion_rate * 0.2)
  ) AS trending_score,
  rk.last_updated
FROM route_knowledge rk
WHERE rk.search_count > 5 OR rk.booking_count > 2
ORDER BY trending_score DESC;

-- View 2: User Segmentation (group users by persona based on booking patterns)
CREATE VIEW IF NOT EXISTS user_segmentation AS
SELECT
  utp.user_id,
  CASE
    WHEN utp.price_sensitivity > 0.7 THEN 'PRICE_SENSITIVE'
    WHEN utp.price_sensitivity < 0.3 THEN 'PRICE_INSENSITIVE'
    ELSE 'BALANCED'
  END AS price_segment,
  CASE
    WHEN utp.avg_booking_advance_days > 14 THEN 'PLANNER'
    WHEN utp.avg_booking_advance_days < 7 THEN 'LAST_MINUTE'
    ELSE 'REGULAR'
  END AS booking_pattern,
  CASE
    WHEN utp.total_interactions > 50 THEN 'POWER_USER'
    WHEN utp.total_interactions > 10 THEN 'REGULAR_USER'
    ELSE 'NEW_USER'
  END AS user_type,
  utp.preference_confidence,
  utp.total_interactions,
  utp.cancellation_rate,
  utp.no_show_rate
FROM user_travel_preferences utp
WHERE utp.user_id IS NOT NULL;

-- View 3: Route Quality Scores (pre-computed for quick ranking)
CREATE VIEW IF NOT EXISTS route_quality_scores AS
SELECT
  rk.id,
  rk.source_code,
  rk.destination_code,
  rk.duration_minutes,
  rk.reliability_score,
  rk.on_time_percentage,
  rk.avg_delay_minutes,
  (
    (rk.reliability_score * 0.4) +
    ((100 - rk.avg_delay_minutes) / 100 * 0.3) +
    ((rk.on_time_percentage / 100) * 0.3)
  ) AS quality_score,
  rk.last_updated
FROM route_knowledge rk
WHERE rk.reliability_score >= 0.75;

-- ============================================================================
-- PHASE 4: CREATE NEW TABLES FOR USER PREFERENCE LEARNING
-- ============================================================================

-- UserBookingHistory: Track every booking for preference learning
CREATE TABLE IF NOT EXISTS user_booking_history (
  id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id VARCHAR(36) NOT NULL,
  booking_id VARCHAR(36) NOT NULL,
  route_id VARCHAR(36),
  source_code VARCHAR(10),
  destination_code VARCHAR(10),
  persona VARCHAR(20),
  fare FLOAT,
  booking_status VARCHAR(20),
  travel_date DATE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_booking_history_route FOREIGN KEY (route_id) REFERENCES route_knowledge(id) ON DELETE SET NULL
);

-- Indexes for UserBookingHistory
CREATE INDEX IF NOT EXISTS idx_user_booking_history_user_id
  ON user_booking_history(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_user_booking_history_route
  ON user_booking_history(route_id, booking_status);

CREATE INDEX IF NOT EXISTS idx_user_booking_history_travel_date
  ON user_booking_history(travel_date DESC);

-- UserPreferenceUpdate: Audit trail for preference changes
CREATE TABLE IF NOT EXISTS user_preference_updates (
  id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id VARCHAR(36) NOT NULL,
  field_name VARCHAR(100),
  old_value TEXT,
  new_value TEXT,
  change_reason VARCHAR(100),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Indexes for UserPreferenceUpdate
CREATE INDEX IF NOT EXISTS idx_user_preference_updates_user_id
  ON user_preference_updates(user_id, created_at DESC);

-- ============================================================================
-- PHASE 5: ADD DATA RETENTION COLUMNS
-- ============================================================================

-- Add soft-delete flag to tables with retention policies
ALTER TABLE demand_snapshots
  ADD COLUMN IF NOT EXISTS is_archived BOOLEAN DEFAULT FALSE;

ALTER TABLE search_outcomes
  ADD COLUMN IF NOT EXISTS is_archived BOOLEAN DEFAULT FALSE;

-- Add archive timestamp
ALTER TABLE demand_snapshots
  ADD COLUMN IF NOT EXISTS archived_at TIMESTAMP;

ALTER TABLE search_outcomes
  ADD COLUMN IF NOT EXISTS archived_at TIMESTAMP;

-- Create indexes for retention operations
CREATE INDEX IF NOT EXISTS idx_demand_snapshot_archived
  ON demand_snapshots(is_archived, archived_at DESC);

CREATE INDEX IF NOT EXISTS idx_search_outcome_archived
  ON search_outcomes(is_archived, archived_at DESC);

-- ============================================================================
-- PHASE 6: CREATE STORED PROCEDURES FOR DATA CLEANUP
-- ============================================================================

-- Archive old DemandSnapshot records (>90 days)
-- Note: Adapt for SQLite if needed (remove $1 syntax)
CREATE OR REPLACE FUNCTION archive_old_demand_snapshots()
RETURNS void AS $$
BEGIN
  UPDATE demand_snapshots
  SET is_archived = TRUE, archived_at = CURRENT_TIMESTAMP
  WHERE is_archived = FALSE
    AND travel_date < CURRENT_DATE - INTERVAL '90 days';
END;
$$ LANGUAGE plpgsql;

-- Archive old SearchOutcome records (>60 days)
CREATE OR REPLACE FUNCTION archive_old_search_outcomes()
RETURNS void AS $$
BEGIN
  UPDATE search_outcomes
  SET is_archived = TRUE, archived_at = CURRENT_TIMESTAMP
  WHERE is_archived = FALSE
    AND created_at < CURRENT_TIMESTAMP - INTERVAL '60 days';
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- PHASE 7: MIGRATION METADATA
-- ============================================================================

-- Add migration tracking
INSERT INTO schema_migrations (version, description, executed_at)
VALUES (
  '003_feature5_database_optimization',
  'Add performance indexes, materialized views, and user preference tracking',
  CURRENT_TIMESTAMP
) ON CONFLICT DO NOTHING;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Verify all indexes created:
-- SELECT indexname, indexdef FROM pg_indexes
-- WHERE schemaname='public' AND indexname LIKE 'idx_%';

-- Verify materialized views:
-- SELECT * FROM trending_routes LIMIT 5;
-- SELECT * FROM user_segmentation LIMIT 5;
-- SELECT * FROM route_quality_scores LIMIT 5;

-- Verify tables created:
-- \d user_booking_history
-- \d user_preference_updates

-- ============================================================================
-- END OF MIGRATION
-- ============================================================================
