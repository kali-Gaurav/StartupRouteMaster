-- RouteMaster ML Feature Store Schema
-- ===================================
--
-- This migration creates tables for the ML training pipeline:
-- 1. route_search_events - Raw event storage
-- 2. route_features - Engineered features
-- 3. training_datasets - Dataset metadata
-- 4. model_metadata - Model registry

-- Create route_search_events table
CREATE TABLE IF NOT EXISTS route_search_events (
    id SERIAL PRIMARY KEY,
    search_id VARCHAR(50) UNIQUE NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    user_id VARCHAR(50),
    origin_station VARCHAR(10) NOT NULL,
    destination_station VARCHAR(10) NOT NULL,
    search_date DATE NOT NULL,
    train_classes JSONB,
    passenger_count INTEGER DEFAULT 1,
    raw_request JSONB,
    raw_response JSONB,
    processing_time_ms FLOAT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for route_search_events
CREATE INDEX IF NOT EXISTS idx_route_search_events_search_id ON route_search_events(search_id);
CREATE INDEX IF NOT EXISTS idx_route_search_events_timestamp ON route_search_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_route_search_events_user_id ON route_search_events(user_id);
CREATE INDEX IF NOT EXISTS idx_route_search_events_stations ON route_search_events(origin_station, destination_station);
CREATE INDEX IF NOT EXISTS idx_route_search_events_search_date ON route_search_events(search_date);

-- Create route_features table (feature store)
CREATE TABLE IF NOT EXISTS route_features (
    id SERIAL PRIMARY KEY,
    search_id VARCHAR(50) UNIQUE NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,

    -- Temporal features
    search_hour INTEGER CHECK (search_hour >= 0 AND search_hour <= 23),
    search_day_of_week INTEGER CHECK (search_day_of_week >= 0 AND search_day_of_week <= 6),
    days_to_travel INTEGER CHECK (days_to_travel >= 0),
    is_weekend BOOLEAN DEFAULT FALSE,
    is_peak_season BOOLEAN DEFAULT FALSE,

    -- Route features
    origin_station VARCHAR(10) NOT NULL,
    destination_station VARCHAR(10) NOT NULL,
    distance_km FLOAT CHECK (distance_km >= 0),
    route_complexity FLOAT CHECK (route_complexity >= 0),

    -- Train features
    train_count INTEGER DEFAULT 0 CHECK (train_count >= 0),
    avg_duration_minutes FLOAT CHECK (avg_duration_minutes >= 0),
    has_tatkal_available BOOLEAN DEFAULT FALSE,
    tatkal_slots_available INTEGER DEFAULT 0 CHECK (tatkal_slots_available >= 0),

    -- Price features
    min_price FLOAT CHECK (min_price >= 0),
    max_price FLOAT CHECK (max_price >= 0),
    price_range FLOAT CHECK (price_range >= 0),
    avg_price_per_km FLOAT CHECK (avg_price_per_km >= 0),

    -- Feature versioning for schema evolution
    feature_version VARCHAR(20) DEFAULT 'v1.0',

    -- Target variables (populated by delayed labeling)
    actual_delay_minutes FLOAT,  -- Populated from delay events
    tatkal_booked BOOLEAN,       -- Populated from booking events
    booking_confirmed BOOLEAN,   -- Populated from booking events

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for route_features
CREATE INDEX IF NOT EXISTS idx_route_features_search_id ON route_features(search_id);
CREATE INDEX IF NOT EXISTS idx_route_features_timestamp ON route_features(timestamp);
CREATE INDEX IF NOT EXISTS idx_route_features_stations ON route_features(origin_station, destination_station);
CREATE INDEX IF NOT EXISTS idx_route_features_temporal ON route_features(search_hour, search_day_of_week, days_to_travel);

-- Create training_datasets table
CREATE TABLE IF NOT EXISTS training_datasets (
    id SERIAL PRIMARY KEY,
    dataset_name VARCHAR(100) UNIQUE NOT NULL,
    version VARCHAR(20) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Dataset metadata
    record_count INTEGER NOT NULL CHECK (record_count > 0),
    feature_count INTEGER NOT NULL CHECK (feature_count > 0),
    date_range_start TIMESTAMP WITH TIME ZONE,
    date_range_end TIMESTAMP WITH TIME ZONE,
    target_variable VARCHAR(50) NOT NULL,

    -- Data quality metrics
    missing_data_pct FLOAT CHECK (missing_data_pct >= 0 AND missing_data_pct <= 100),
    duplicate_pct FLOAT CHECK (duplicate_pct >= 0 AND duplicate_pct <= 100),

    -- Dataset snapshot hash for reproducibility
    dataset_hash VARCHAR(64),

    -- Storage paths
    s3_path VARCHAR(500),
    local_path VARCHAR(500)
);

-- Indexes for training_datasets
CREATE INDEX IF NOT EXISTS idx_training_datasets_name ON training_datasets(dataset_name);
CREATE INDEX IF NOT EXISTS idx_training_datasets_target ON training_datasets(target_variable);
CREATE INDEX IF NOT EXISTS idx_training_datasets_created ON training_datasets(created_at DESC);

-- Create model_metadata table (model registry)
CREATE TABLE IF NOT EXISTS model_metadata (
    id SERIAL PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL,
    version VARCHAR(20) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Model info
    algorithm VARCHAR(50) NOT NULL,
    hyperparameters JSONB,
    feature_importance JSONB,

    -- Performance metrics
    train_accuracy FLOAT CHECK (train_accuracy >= 0 AND train_accuracy <= 1),
    validation_accuracy FLOAT CHECK (validation_accuracy >= 0 AND validation_accuracy <= 1),
    test_accuracy FLOAT CHECK (test_accuracy >= 0 AND test_accuracy <= 1),

    -- Deployment
    s3_path VARCHAR(500),
    local_path VARCHAR(500),
    is_active BOOLEAN DEFAULT FALSE,

    UNIQUE(model_name, version)
);

-- Indexes for model_metadata
CREATE INDEX IF NOT EXISTS idx_model_metadata_name ON model_metadata(model_name);
CREATE INDEX IF NOT EXISTS idx_model_metadata_active ON model_metadata(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_model_metadata_created ON model_metadata(created_at DESC);

-- Create views for common queries

-- View: Latest active models
CREATE OR REPLACE VIEW active_models AS
SELECT
    model_name,
    version,
    algorithm,
    test_accuracy,
    created_at
FROM model_metadata
WHERE is_active = TRUE
ORDER BY created_at DESC;

-- View: Dataset quality overview
CREATE OR REPLACE VIEW dataset_quality AS
SELECT
    dataset_name,
    version,
    record_count,
    ROUND(missing_data_pct::numeric, 2) as missing_pct,
    ROUND(duplicate_pct::numeric, 2) as duplicate_pct,
    target_variable,
    date_range_start,
    date_range_end
FROM training_datasets
ORDER BY created_at DESC;

-- View: Feature engineering stats
CREATE OR REPLACE VIEW feature_stats AS
SELECT
    DATE_TRUNC('day', timestamp) as date,
    COUNT(*) as searches,
    AVG(route_complexity) as avg_complexity,
    AVG(train_count) as avg_train_count,
    AVG(distance_km) as avg_distance,
    COUNT(CASE WHEN has_tatkal_available THEN 1 END) as tatkal_available_count
FROM route_features
WHERE timestamp >= NOW() - INTERVAL '30 days'
GROUP BY DATE_TRUNC('day', timestamp)
ORDER BY date DESC;

-- Comments for documentation
COMMENT ON TABLE route_search_events IS 'Raw route search events from Kafka for ML training';
COMMENT ON TABLE route_features IS 'Engineered features for ML models (feature store)';
COMMENT ON TABLE training_datasets IS 'Metadata for created training datasets';
COMMENT ON TABLE model_metadata IS 'Model registry with performance metrics';

COMMENT ON COLUMN route_features.actual_delay_minutes IS 'Target variable: actual delay in minutes (populated from delay events)';
COMMENT ON COLUMN route_features.tatkal_booked IS 'Target variable: whether user booked Tatkal (populated from booking events)';
COMMENT ON COLUMN route_features.booking_confirmed IS 'Target variable: whether booking was confirmed (populated from booking events)';