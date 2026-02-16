-- RouteMaster ML Feature Store Schema
-- ===================================
--
-- This migration creates tables for the ML training pipeline:
-- 1. route_search_events - Raw event storage
-- 2. route_features - Engineered features
-- 3. training_datasets - Dataset metadata
-- 4. model_metadata - Model registry

-- Create route_search_events table
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='route_search_events' AND xtype='U')
CREATE TABLE route_search_events (
    id INT IDENTITY(1,1) PRIMARY KEY,
    search_id NVARCHAR(50) UNIQUE NOT NULL,
    timestamp DATETIMEOFFSET NOT NULL,
    user_id NVARCHAR(50),
    origin_station NVARCHAR(10) NOT NULL,
    destination_station NVARCHAR(10) NOT NULL,
    search_date DATE NOT NULL,
    train_classes NVARCHAR(MAX),
    passenger_count INT DEFAULT 1,
    raw_request NVARCHAR(MAX),
    raw_response NVARCHAR(MAX),
    processing_time_ms FLOAT,
    created_at DATETIMEOFFSET DEFAULT GETUTCDATE()
);

-- Indexes for route_search_events
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name='idx_route_search_events_search_id')
CREATE INDEX idx_route_search_events_search_id ON route_search_events(search_id);

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name='idx_route_search_events_timestamp')
CREATE INDEX idx_route_search_events_timestamp ON route_search_events(timestamp);

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name='idx_route_search_events_user_id')
CREATE INDEX idx_route_search_events_user_id ON route_search_events(user_id);

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name='idx_route_search_events_stations')
CREATE INDEX idx_route_search_events_stations ON route_search_events(origin_station, destination_station);

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name='idx_route_search_events_search_date')
CREATE INDEX idx_route_search_events_search_date ON route_search_events(search_date);

-- Create route_features table (feature store)
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='route_features' AND xtype='U')
CREATE TABLE route_features (
    id INT IDENTITY(1,1) PRIMARY KEY,
    search_id NVARCHAR(50) UNIQUE NOT NULL,
    timestamp DATETIMEOFFSET NOT NULL,

    -- Temporal features
    search_hour INT CHECK (search_hour >= 0 AND search_hour <= 23),
    search_day_of_week INT CHECK (search_day_of_week >= 0 AND search_day_of_week <= 6),
    days_to_travel INT CHECK (days_to_travel >= 0),
    is_weekend BIT DEFAULT 0,
    is_peak_season BIT DEFAULT 0,

    -- Route features
    origin_station NVARCHAR(10) NOT NULL,
    destination_station NVARCHAR(10) NOT NULL,
    distance_km FLOAT CHECK (distance_km >= 0),
    route_complexity FLOAT CHECK (route_complexity >= 0),

    -- Train features
    train_count INT DEFAULT 0 CHECK (train_count >= 0),
    avg_duration_minutes FLOAT CHECK (avg_duration_minutes >= 0),
    has_tatkal_available BIT DEFAULT 0,
    tatkal_slots_available INT DEFAULT 0 CHECK (tatkal_slots_available >= 0),

    -- Price features
    min_price FLOAT CHECK (min_price >= 0),
    max_price FLOAT CHECK (max_price >= 0),
    price_range FLOAT CHECK (price_range >= 0),
    avg_price_per_km FLOAT CHECK (avg_price_per_km >= 0),

    -- Feature versioning for schema evolution
    feature_version NVARCHAR(20) DEFAULT 'v1.0',

    -- Target variables (populated by delayed labeling)
    actual_delay_minutes FLOAT,  -- Populated from delay events
    tatkal_booked BIT,           -- Populated from booking events
    booking_confirmed BIT,       -- Populated from booking events

    created_at DATETIMEOFFSET DEFAULT GETUTCDATE()
);

-- Indexes for route_features
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name='idx_route_features_search_id')
CREATE INDEX idx_route_features_search_id ON route_features(search_id);

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name='idx_route_features_timestamp')
CREATE INDEX idx_route_features_timestamp ON route_features(timestamp);

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name='idx_route_features_stations')
CREATE INDEX idx_route_features_stations ON route_features(origin_station, destination_station);

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name='idx_route_features_temporal')
CREATE INDEX idx_route_features_temporal ON route_features(search_hour, search_day_of_week, days_to_travel);

-- Create training_datasets table
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='training_datasets' AND xtype='U')
CREATE TABLE training_datasets (
    id INT IDENTITY(1,1) PRIMARY KEY,
    dataset_name NVARCHAR(100) UNIQUE NOT NULL,
    version NVARCHAR(20) NOT NULL,
    created_at DATETIMEOFFSET DEFAULT GETUTCDATE(),

    -- Dataset metadata
    record_count INT NOT NULL CHECK (record_count > 0),
    feature_count INT NOT NULL CHECK (feature_count > 0),
    date_range_start DATETIMEOFFSET,
    date_range_end DATETIMEOFFSET,
    target_variable NVARCHAR(50) NOT NULL,

    -- Data quality metrics
    missing_data_pct FLOAT CHECK (missing_data_pct >= 0 AND missing_data_pct <= 100),
    duplicate_pct FLOAT CHECK (duplicate_pct >= 0 AND duplicate_pct <= 100),

    -- Dataset snapshot hash for reproducibility
    dataset_hash NVARCHAR(64),

    -- Storage paths
    s3_path NVARCHAR(500),
    local_path NVARCHAR(500)
);

-- Indexes for training_datasets
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name='idx_training_datasets_name')
CREATE INDEX idx_training_datasets_name ON training_datasets(dataset_name);

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name='idx_training_datasets_target')
CREATE INDEX idx_training_datasets_target ON training_datasets(target_variable);

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name='idx_training_datasets_created')
CREATE INDEX idx_training_datasets_created ON training_datasets(created_at DESC);

-- Create model_metadata table (model registry)
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='model_metadata' AND xtype='U')
CREATE TABLE model_metadata (
    id INT IDENTITY(1,1) PRIMARY KEY,
    model_name NVARCHAR(100) NOT NULL,
    version NVARCHAR(20) NOT NULL,
    created_at DATETIMEOFFSET DEFAULT GETUTCDATE(),

    -- Model info
    algorithm NVARCHAR(50) NOT NULL,
    hyperparameters NVARCHAR(MAX),
    feature_importance NVARCHAR(MAX),

    -- Performance metrics
    train_accuracy FLOAT CHECK (train_accuracy >= 0 AND train_accuracy <= 1),
    validation_accuracy FLOAT CHECK (validation_accuracy >= 0 AND validation_accuracy <= 1),
    test_accuracy FLOAT CHECK (test_accuracy >= 0 AND test_accuracy <= 1),

    -- Deployment
    s3_path NVARCHAR(500),
    local_path NVARCHAR(500),
    is_active BIT DEFAULT 0,

    UNIQUE(model_name, version)
);

-- Indexes for model_metadata
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name='idx_model_metadata_name')
CREATE INDEX idx_model_metadata_name ON model_metadata(model_name);

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name='idx_model_metadata_active')
CREATE INDEX idx_model_metadata_active ON model_metadata(is_active) WHERE is_active = 1;

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name='idx_model_metadata_created')
CREATE INDEX idx_model_metadata_created ON model_metadata(created_at DESC);

-- Create views for common queries

-- View: Latest active models
IF EXISTS (SELECT * FROM sys.views WHERE name='active_models')
DROP VIEW active_models;
GO
CREATE VIEW active_models AS
SELECT
    model_name,
    version,
    algorithm,
    test_accuracy,
    created_at
FROM model_metadata
WHERE is_active = 1
ORDER BY created_at DESC;
GO

-- View: Dataset quality overview
IF EXISTS (SELECT * FROM sys.views WHERE name='dataset_quality')
DROP VIEW dataset_quality;
GO
CREATE VIEW dataset_quality AS
SELECT
    dataset_name,
    version,
    record_count,
    ROUND(missing_data_pct, 2) as missing_pct,
    ROUND(duplicate_pct, 2) as duplicate_pct,
    target_variable,
    date_range_start,
    date_range_end
FROM training_datasets
ORDER BY created_at DESC;
GO

-- View: Feature engineering stats
IF EXISTS (SELECT * FROM sys.views WHERE name='feature_stats')
DROP VIEW feature_stats;
GO
CREATE VIEW feature_stats AS
SELECT
    CAST(timestamp AS DATE) as date,
    COUNT(*) as searches,
    AVG(route_complexity) as avg_complexity,
    AVG(train_count) as avg_train_count,
    AVG(distance_km) as avg_distance,
    COUNT(CASE WHEN has_tatkal_available = 1 THEN 1 END) as tatkal_available_count
FROM route_features
WHERE timestamp >= DATEADD(DAY, -30, GETUTCDATE())
GROUP BY CAST(timestamp AS DATE)
ORDER BY date DESC;
GO

-- Comments for documentation
/*
COMMENT ON TABLE route_search_events IS 'Raw route search events from Kafka for ML training';
COMMENT ON TABLE route_features IS 'Engineered features for ML models (feature store)';
COMMENT ON TABLE training_datasets IS 'Metadata for created training datasets';
COMMENT ON TABLE model_metadata IS 'Model registry with performance metrics';

COMMENT ON COLUMN route_features.actual_delay_minutes IS 'Target variable: actual delay in minutes (populated from delay events)';
COMMENT ON COLUMN route_features.tatkal_booked IS 'Target variable: whether user booked Tatkal (populated from booking events)';
COMMENT ON COLUMN route_features.booking_confirmed IS 'Target variable: whether booking was confirmed (populated from booking events)';
*/