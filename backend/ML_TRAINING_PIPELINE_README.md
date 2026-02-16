# RouteMaster ML Training Pipeline

## Overview

This pipeline transforms route search events into ML training datasets for delay prediction and Tatkal booking models. It implements a complete ML engineering workflow from event ingestion to model deployment.

## 🚨 Critical: Phased Rollout Strategy

**DO NOT train production models immediately after staging.**

Follow this disciplined sequence:

### Phase A: Data Collection Only (First 30 Days)
```bash
# Default behavior - data collection mode
python run_ml_data_collection.py
```

**Goals:**
- ✅ Store events in feature store
- ✅ Validate schema and data quality
- ✅ Monitor feature completeness
- ✅ Detect data anomalies
- ✅ Measure label availability

**What happens:** No models trained, only data validation.

### Phase B: Offline Training Validation (After 30 Days)
```bash
# Enable training mode
ML_DATA_COLLECTION_ONLY=false python run_ml_data_collection.py
```

**Goals:**
- ✅ Train models on historical data
- ✅ Evaluate against baseline heuristics
- ✅ Perform feature importance analysis
- ✅ Validate model quality metrics

### Phase C: Shadow Mode Deployment
- Deploy models in prediction-only mode
- Log predictions vs actual outcomes
- No user-facing changes

### Phase D: Controlled Influence
- 10% traffic influenced by ML
- A/B testing and monitoring
- Gradual rollout based on metrics

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐    ┌────────────────┐
│  Route Search   │ -> │  Feature Store   │ -> │  Dataset Build  │ -> │  Model Train   │
│    Events       │    │   (PostgreSQL)   │    │   (Parquet)     │    │   (XGBoost)    │
└─────────────────┘    └──────────────────┘    └─────────────────┘    └────────────────┘
        │                       │                        │                       │
        ▼                       ▼                        ▼                       ▼
   Kafka Events         Engineered Features       Labeled Dataset         Trained Model
   (Raw JSON)           (Structured Data)         (Train/Val/Test)        (Model Artifact)
```

## Components

### 1. Event Ingestion (`route_search_events` table)
- **Source**: Kafka route search events
- **Purpose**: Raw event storage for feature engineering
- **Retention**: 90 days rolling window
- **Indexing**: Search ID, timestamp, stations, user ID

### 2. Feature Store (`route_features` table)
- **Features**: 20+ engineered features across temporal, route, train, price, and user dimensions
- **Targets**: Delay minutes, Tatkal booking, booking confirmation
- **Labeling**: Delayed labeling from subsequent events (bookings, delays)
- **Quality**: Data validation constraints and quality metrics

### 3. Dataset Builder
- **Input**: Feature store with labels
- **Output**: Parquet datasets for training
- **Quality Checks**: Missing data %, duplicates, sample size
- **Versioning**: Timestamp-based dataset versions

### 4. Model Training
- **Algorithms**: XGBoost, LightGBM
- **Targets**: Delay prediction, Tatkal probability
- **Evaluation**: Train/Val/Test split with metrics
- **Registry**: Model metadata and performance tracking

## Feature Engineering

### Temporal Features
- `search_hour`: 0-23
- `search_day_of_week`: 0-6 (Monday=0)
- `days_to_travel`: Days between search and travel
- `is_weekend`: Boolean
- `is_peak_season`: Summer/Monsoon/Festival/Winter

### Route Features
- `origin_station`, `destination_station`: Station codes
- `distance_km`: Route distance
- `route_complexity`: Number of route options

### Train Features
- `train_count`: Available trains
- `avg_duration_minutes`: Average journey time
- `has_tatkal_available`: Tatkal availability
- `tatkal_slots_available`: Total Tatkal slots

### Price Features
- `min_price`, `max_price`: Price range
- `price_range`: Price spread
- `avg_price_per_km`: Price efficiency

### User Context
- `passenger_count`: Number of passengers
- `preferred_classes`: Preferred train classes (JSON)

## Target Variables

### Delay Prediction
- **Target**: `actual_delay_minutes`
- **Source**: Real-time delay events (30min TTL)
- **Type**: Regression (minutes)
- **Use Case**: Route delay prediction

### Tatkal Booking
- **Target**: `tatkal_booked`
- **Source**: Booking confirmation events
- **Type**: Binary classification
- **Use Case**: Tatkal recommendation

### Booking Confirmation
- **Target**: `booking_confirmed`
- **Source**: Payment success events
- **Type**: Binary classification
- **Use Case**: Booking conversion prediction

## Data Quality Monitoring

The pipeline includes comprehensive data quality monitoring to prevent training on bad data:

### Metrics Monitored
- **Missing Feature Rate**: < 10% acceptable
- **Label Coverage**: Delay/Tatkal/Booking label availability
- **Feature Extraction Success**: > 95% success rate
- **Label Delay**: < 1 hour p95 for timely labeling
- **Outlier Rate**: < 5% for data sanity

### Grafana Dashboard
View data quality metrics in the "ML Data Quality Monitoring" section:
- Total feature records accumulated
- Missing feature rates
- Label coverage percentages
- Feature extraction success rates
- Label delay distributions

### Quality Gates
**Before Phase B (Training):**
- ✅ 30+ days of data collected
- ✅ Missing feature rate < 5%
- ✅ Label coverage > 50% for target variables
- ✅ Feature extraction success > 95%

## Usage

### Phase A: Data Collection Mode (Default)

**Start ML Database:**
```bash
docker-compose up -d routemaster_ml_db
```

**Setup Schema:**
```bash
cd backend
python setup_ml_database.py
```

**Run Data Collection:**
```bash
python run_ml_data_collection.py
```

**Expected Output:**
```
🧠 RouteMaster ML Pipeline Starting
Data Collection Mode: True
📊 Running data quality checks...
📈 Data Quality Report:
   Total Records: 1,247
   Data Collection Days: 5
   Missing Feature Rate: 0.023
   Label Availability:
     delay_label_rate: 0.156
     tatkal_label_rate: 0.089
     booking_label_rate: 0.067
✅ Data collection mode active - no model training
```

### Phase B: Training Mode (After 30 Days)

**Enable Training:**
```bash
ML_DATA_COLLECTION_ONLY=false python run_ml_data_collection.py
```

**Monitor Training:**
```bash
# Check dataset quality
psql -d routemaster_ml -c "SELECT * FROM dataset_quality;"

# Check active models
psql -d routemaster_ml -c "SELECT * FROM active_models;"
```

## Data Flow

### Event Ingestion
1. Route search events arrive via Kafka
2. Stored in `route_search_events` table
3. Features extracted and stored in `route_features`
4. Initial features computed immediately

### Delayed Labeling
1. Delay events update `actual_delay_minutes`
2. Booking events update `tatkal_booked`, `booking_confirmed`
3. Labels applied with time-based joins (search → delay/booking)

### Dataset Creation
1. Query features with complete labels
2. Apply data quality filters
3. Split into train/validation/test sets
4. Save as versioned Parquet files

### Model Training
1. Load dataset by version
2. Train model with hyperparameter tuning
3. Evaluate on validation set
4. Register model with metadata
5. Deploy to model serving (future)

## Quality Assurance

### Data Quality Metrics
- **Missing Data %**: < 5% acceptable
- **Duplicates %**: < 1% acceptable
- **Sample Size**: > 1000 for training
- **Date Range**: Last 30 days minimum

### Model Quality Metrics
- **Delay Prediction**: MAE < 15 minutes
- **Tatkal Classification**: AUC > 0.8
- **Booking Classification**: AUC > 0.75

## Monitoring

### Prometheus Metrics
- `ml_feature_extraction_duration_seconds`: Feature extraction time
- `ml_dataset_build_duration_seconds`: Dataset building time
- `ml_model_train_duration_seconds`: Model training time

### Alert Rules
- Dataset build failures
- Model training failures
- Data quality degradation
- Model performance drops

## Scaling Considerations

### Storage
- Feature store: 90-day retention
- Datasets: Keep last 10 versions
- Models: Keep last 5 versions per type

### Performance
- Feature extraction: < 100ms per event
- Dataset build: < 30min for 30 days
- Model training: < 10min per model

### Reliability
- Idempotent event processing
- Transactional feature updates
- Graceful failure handling
- Comprehensive logging

## Future Enhancements

### Advanced Features
- Real-time feature serving
- Online learning updates
- Feature drift detection
- A/B testing framework

### Model Improvements
- Ensemble methods
- Deep learning approaches
- Multi-target prediction
- Uncertainty quantification

### Operational
- Automated retraining pipelines
- Model performance monitoring
- Feature importance tracking
- Explainability reports