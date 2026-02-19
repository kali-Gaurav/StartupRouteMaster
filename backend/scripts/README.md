# Backend Utility Scripts

Helper scripts for backend operations including data seeding, ML training, testing, and database maintenance.

## Data Seeding & Setup

### seed_stations.py
Seed the database with initial station/stop data from GTFS or CSV files.

```bash
python scripts/seed_stations.py --input data/stations.csv
```

### setup_ml_database.py
Initialize ML feature store and tables.

```bash
python scripts/setup_ml_database.py
```

## ML Training & Analytics

### ml_data_collection.py
Collect training data from routes and searches for ML models.

```bash
python scripts/ml_data_collection.py --days 30
```

### ml_training_pipeline.py
Train ML models for delay prediction, demand forecasting, and ranking.

```bash
python scripts/ml_training_pipeline.py --model delay_predictor
```

### run_ml_data_collection.py
Runner script for ML data collection (wrapper around ml_data_collection.py).

```bash
python scripts/run_ml_data_collection.py
```

### baseline_heuristic_models.py (ML subfolder)
Baseline rule-based models for comparison with ML models.

```bash
python scripts/ml/baseline_heuristic_models.py --evaluate
```

### shadow_inference_service.py (ML subfolder)
Shadow mode testing for ML models without production impact.

```bash
python scripts/ml/shadow_inference_service.py --duration 24h
```

### staging_rollout.py (ML subfolder)
A/B testing and staged rollout of models.

```bash
python scripts/ml/staging_rollout.py --model ranking_v2 --percentage 10
```

## Testing & Performance

### concurrency_load_tester.py
Load test the backend with concurrent requests.

```bash
python scripts/concurrency_load_tester.py --workers 100 --requests 10000
```

### simple_load_test.py
Quick load test script (simpler variant).

```bash
python scripts/simple_load_test.py
```

### mock_api_server.py
Mock API server for testing client code without backend.

```bash
python scripts/mock_api_server.py --port 8001
```

### test_booking_system.py
Integration test for booking system (Saga pattern, seat allocation, etc).

```bash
python scripts/test_booking_system.py --verbose
```

### test_chat_enhanced.py
Test the AI chat API functionality.

```bash
python scripts/test_chat_enhanced.py
```

### test_db_connectivity.py
Verify database connectivity and health.

```bash
python scripts/test_db_connectivity.py
```

### test_event_pipeline.py
Test Kafka event pipeline for real-time updates.

```bash
python scripts/test_event_pipeline.py
```

## Database Utilities

### check_db.py
Health check for the database (table counts, indexes, etc).

```bash
python scripts/check_db.py
```

### inspect_railway_db.py
Detailed inspection of railway_manager.db schema and data.

```bash
python scripts/inspect_railway_db.py --table stops
```

## Monitoring & Operations

### start_analytics_consumer.py
Start the Kafka consumer for analytics events.

```bash
python scripts/start_analytics_consumer.py --brokers localhost:9092
```

### audit_kafka_config.py
Audit and verify Kafka configuration.

```bash
python scripts/audit_kafka_config.py
```

### payment_reconciliation_worker.py (formerly worker.py)
Background worker for payment reconciliation.

```bash
python scripts/payment_reconciliation_worker.py --interval 5m
```

### search_worker.py
Background worker for search result caching and preprocessing.

```bash
python scripts/search_worker.py
```

## Usage Notes

- Scripts should be run from the backend root directory:
  ```bash
  cd backend/
  python scripts/script_name.py
  ```

- Most scripts support `--help` for detailed options:
  ```bash
  python scripts/script_name.py --help
  ```

- Database scripts assume `.env` configuration is set with database credentials

- ML scripts require ML feature store to be initialized via `setup_ml_database.py` first

## Organization

```
scripts/
├── __init__.py
├── README.md (this file)
├── seed_stations.py
├── check_db.py
├── inspect_railway_db.py
├── concurrency_load_tester.py
├── simple_load_test.py
├── mock_api_server.py
├── test_*.py (integration tests)
├── start_analytics_consumer.py
├── audit_kafka_config.py
├── payment_reconciliation_worker.py
├── search_worker.py
└── ml/
    ├── ml_data_collection.py
    ├── ml_training_pipeline.py
    ├── run_ml_data_collection.py
    ├── baseline_heuristic_models.py
    ├── shadow_inference_service.py
    └── staging_rollout.py
```

## See Also

- `../README.md` - Backend overview and architecture
- `../core/README.md` - Core routing engine documentation
- `../BACKEND_FEATURES.md` - Complete feature inventory
