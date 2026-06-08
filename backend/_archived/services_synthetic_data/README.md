# Synthetic Data Generation Framework

A comprehensive framework for generating synthetic data for cost-free route generation and ML training.

## Overview

The Synthetic Data Generation Framework enables:

- **Cost-Free Route Generation**: Generate routes without real-time API calls
- **ML Training Data**: Generate realistic data for ML model training
- **Validation**: Ensure data quality and statistical validity
- **Storage**: Efficient storage and retrieval for production use

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│              SYNTHETIC DATA GENERATION ENGINE                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    DATA SOURCES                              │    │
│  ├─────────────────────────────────────────────────────────────┤    │
│  │  - Real Train Schedules (10K)                               │    │
│  │  - Historical Fares (5M)                                    │    │
│  │  - Booking Patterns (2M)                                    │    │
│  │  - User Behavior (50K)                                      │    │
│  │  - Station Information (8.5K)                               │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                              │                                      │
│                              ▼                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │              GENERATION ENGINE                               │    │
│  ├─────────────────────────────────────────────────────────────┤    │
│  │  - Train Schedule Generator                                 │    │
│  │  - Fare Generator                                           │    │
│  │  - Availability Generator                                   │    │
│  │  - User Behavior Generator                                  │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                              │                                      │
│                              ▼                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │              VALIDATION LAYER                                │    │
│  ├─────────────────────────────────────────────────────────────┤    │
│  │  - Distribution Validation                                  │    │
│  │  - Statistical Validity Tests                               │    │
│  │  - Realism Scoring                                          │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                              │                                      │
│                              ▼                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │              STORAGE LAYER                                   │    │
│  ├─────────────────────────────────────────────────────────────┤    │
│  │  - PostgreSQL (Relational Data)                             │    │
│  │  - Redis (Cache & Fast Access)                              │    │
│  │  - Feature Store (ML Training)                              │    │
│  │  - Route Graph (Graph Database)                             │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Components

### 1. Generators

- **TrainScheduleGenerator**: Generates synthetic train schedules
- **FareGenerator**: Generates synthetic fare data with dynamic pricing
- **AvailabilityGenerator**: Generates synthetic availability with contextual factors
- **UserBehaviorGenerator**: Generates synthetic user behavior for personalization

### 2. Validation

- **DistributionValidator**: Validates distribution matching
- **StatisticalValidator**: Validates statistical properties
- **RealismScorer**: Scores data for realism

### 3. Storage

- **FeatureStore**: Stores features for ML training
- **RouteGraph**: Stores route connections for fast queries

## Installation

```bash
# Install dependencies
pip install numpy pandas scipy redis psycopg2-binary

# Or use the project's requirements
pip install -r requirements.txt
```

## Usage

### Basic Usage

```python
from backend.services.synthetic_data_service import get_synthetic_data_service

# Get the service instance
service = get_synthetic_data_service()

# Generate all synthetic data
results = service.generate_all_data()

# Get routes without real-time API
routes = service.get_routes(
    from_station="NDLS",
    to_station="BCT",
    travel_date="2026-05-15"
)

# Check availability
availability = service.get_availability(
    train_number="12001",
    travel_date="2026-05-15",
    travel_class="3A"
)
```

### Advanced Usage

```python
from backend.services.synthetic_data.generators import (
    TrainScheduleGenerator,
    FareGenerator,
    AvailabilityGenerator,
    UserBehaviorGenerator,
)

# Create generators
schedule_gen = TrainScheduleGenerator()
fare_gen = FareGenerator(schedule_gen)
availability_gen = AvailabilityGenerator(schedule_gen)
behavior_gen = UserBehaviorGenerator()

# Generate specific data types
schedules = schedule_gen.generate(10000)
fares = fare_gen.generate(2000000)
availability = availability_gen.generate(10000000)
behavior = behavior_gen.generate(5000000)
```

### Validation

```python
from backend.services.synthetic_data.validation import validate_synthetic_data
import pandas as pd

# Load data
real_data = pd.read_csv('data/real_fares.csv')
synthetic_data = pd.read_csv('data/synth_fares.csv')

# Validate
results = validate_synthetic_data(real_data, synthetic_data)

print(f"Overall Score: {results['overall_score']}")
print(f"Passed: {results['passed']}")
```

## API Endpoints

### Generate Data

```bash
POST /api/v1/synthetic/generate
Content-Type: application/json

{
    "counts": {
        "schedules": 1000000,
        "fares": 2000000,
        "availability": 10000000,
        "behavior": 5000000
    }
}
```

### Validate Data

```bash
POST /api/v1/synthetic/validate
Content-Type: application/json

{
    "real_data_path": "data/real_fares.csv",
    "synthetic_data_path": "data/synth_fares.csv"
}
```

### Get Routes

```bash
POST /api/v1/synthetic/routes
Content-Type: application/json

{
    "from_station": "NDLS",
    "to_station": "BCT",
    "travel_date": "2026-05-15",
    "max_transfers": 2
}
```

### Get Availability

```bash
POST /api/v1/synthetic/availability
Content-Type: application/json

{
    "train_number": "12001",
    "travel_date": "2026-05-15",
    "travel_class": "3A"
}
```

## Configuration

### Environment Variables

```bash
# Redis
REDIS_URL=redis://localhost:6379

# PostgreSQL
POSTGRES_URL=postgresql://localhost:5432/synthetic_data
```

### Docker

```bash
# Start services
docker-compose up -d

# Run generation
python -m backend.services.synthetic_data_service generate
```

## Data Quality

### Validation Metrics

| Metric | Target | Description |
|--------|--------|-------------|
| Distribution Similarity | >95% | KS test, chi-square test |
| Statistical Validity | >99% | Hypothesis tests |
| Realism Score | >90% | Human evaluation |
| Training Performance | >85% | ML model accuracy |

### Data Volumes

| Data Type | Real Data | Synthetic Target | Total |
|-----------|-----------|------------------|-------|
| Train Schedules | 10K | 1M+ | 1,010K+ |
| Fare Records | 500K | 2M+ | 2,500K+ |
| Availability | 0 | 10M+ | 10M+ |
| User Behavior | 50K | 5M+ | 5,050K+ |

## Performance

### Generation Speed

| Metric | Target |
|--------|--------|
| Generation Speed | >10,000 records/second |
| Query Latency (Route) | <100ms |
| Query Latency (Availability) | <50ms |
| Generation Time (Full Dataset) | <4 hours |

### Storage

| Component | Size | Notes |
|-----------|------|-------|
| PostgreSQL | <50GB | Relational data |
| Redis | <10GB | Cache |
| Total | <100GB | |

## Development

### Setup

```bash
# Clone repository
git clone <repository>
cd <project>

# Install dependencies
pip install -r requirements.txt

# Start development services
docker-compose up -d

# Run tests
pytest backend/tests/test_synthetic_data.py
```

### Adding New Generators

1. Create generator class in `generators.py`
2. Implement `generate()` method
3. Add to `__init__.py` exports
4. Update service integration

### Adding New Validation Tests

1. Create validator class in `validation.py`
2. Implement validation logic
3. Add to validation pipeline
4. Update tests

## Monitoring

### Metrics

- Generation speed (records/second)
- Query latency (P50, P95, P99)
- Data quality scores
- Storage usage

### Alerts

- Generation speed < threshold
- Data quality < threshold
- Query latency > threshold

## Troubleshooting

### Common Issues

1. **Connection Errors**
   - Check Redis and PostgreSQL are running
   - Verify connection URLs

2. **Data Quality Issues**
   - Review validation results
   - Adjust generation parameters

3. **Performance Issues**
   - Check system resources
   - Optimize queries

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Submit a pull request

## License

MIT License - See LICENSE file for details.