# Contextual Availability Transformer (CAT)

A machine learning system for predicting seat availability based on contextual factors including event calendar data, weather conditions, and historical availability records.

## Overview

The Contextual Availability Transformer (CAT) is a Transformer-based neural network that predicts availability patterns for Indian Railways. The system leverages self-attention mechanisms to capture complex temporal and contextual relationships, enabling accurate predictions that traditional time-series methods cannot effectively model.

**Key Features:**
- Transformer-based neural network with multi-head attention
- Real-time availability predictions with <100ms latency
- Contextual factors: events, weather, historical patterns
- Model interpretability with contributing factor analysis
- Production-ready with caching, rate limiting, and health checks

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CAT ARCHITECTURE                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    DATA SOURCES                              │    │
│  ├─────────────────────────────────────────────────────────────┤    │
│  │  - Event Calendar API (IPL, concerts, festivals)           │    │
│  │  - Weather API (temperature, precipitation, wind)           │    │
│  │  - Historical Availability Database                         │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                              │                                      │
│                              ▼                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │              DATA COLLECTOR                                  │    │
│  ├─────────────────────────────────────────────────────────────┤    │
│  │  - Concurrent API fetching                                  │    │
│  │  - Exponential backoff                                      │    │
│  │  - Caching with TTL                                         │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                              │                                      │
│                              ▼                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │              PREPROCESSING MODULE                            │    │
│  ├─────────────────────────────────────────────────────────────┤    │
│  │  - Event embeddings (one-hot + positional)                 │    │
│  │  - Weather embeddings (normalized + one-hot)               │    │
│  │  - Historical sequence encoding                            │    │
│  │  - Temporal encodings                                      │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                              │                                      │
│                              ▼                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │              TRANSFORMER MODEL                               │    │
│  ├─────────────────────────────────────────────────────────────┤    │
│  │  - 6 Transformer layers                                     │    │
│  │  - 8 attention heads                                        │    │
│  │  - Multi-head self-attention                                │    │
│  │  - Feed-forward networks                                    │    │
│  │  - Layer normalization                                      │    │
│  │  - Residual connections                                     │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                              │                                      │
│                              ▼                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │              INFERENCE SERVICE                               │    │
│  ├─────────────────────────────────────────────────────────────┤    │
│  │  - REST API for predictions                                 │    │
│  │  - Batch prediction support                                 │    │
│  │  - Caching with Redis                                       │    │
│  │  - Rate limiting                                            │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Installation

```bash
# Install dependencies
pip install torch fastapi redis mlflow aiohttp pydantic

# Or use the project's requirements
pip install -r requirements.txt
```

## Usage

### Basic Usage

```python
from backend.services.cat.inference_service import init_inference_service, get_inference_service
from datetime import datetime

# Initialize the service
init_inference_service(
    event_api_url="https://api.example.com/events",
    event_api_key="your-api-key",
    weather_api_url="https://api.example.com/weather",
    weather_api_key="your-api-key",
    redis_url="redis://localhost:6379",
)

# Get the service instance
service = get_inference_service()

# Make a prediction
prediction = await service.get_availability_prediction(
    location_id="NDLS",
    prediction_time=datetime(2026, 5, 15, 10, 0, 0)
)

print(f"Availability probability: {prediction.probability:.2%}")
print(f"Confidence interval: [{prediction.confidence_interval[0]:.2%}, {prediction.confidence_interval[1]:.2%}]")
print("Contributing factors:")
for factor, score in prediction.contributing_factors:
    print(f"  - {factor}: {score:.2%}")
```

### API Usage

```bash
# Health check
curl http://localhost:8000/api/v1/cat/health

# Get prediction
curl -X POST http://localhost:8000/api/v1/cat/predict \
  -H "Content-Type: application/json" \
  -d '{
    "location_id": "NDLS",
    "prediction_time": "2026-05-15T10:00:00"
  }'

# Batch predictions
curl -X POST http://localhost:8000/api/v1/cat/predict/batch \
  -H "Content-Type: application/json" \
  -d '{
    "predictions": [
      {"location_id": "NDLS", "prediction_time": "2026-05-15T10:00:00"},
      {"location_id": "BCT", "prediction_time": "2026-05-15T10:00:00"}
    ]
  }'

# List locations
curl http://localhost:8000/api/v1/cat/locations
```

### Training

```python
from backend.services.cat.training_pipeline import TrainingPipeline, TrainingConfig
from backend.services.cat.model import CATModel, ModelConfig

# Load historical data
records = load_historical_availability_data()

# Create model
config = ModelConfig()
model = CATModel(config)

# Create training pipeline
training_config = TrainingConfig(
    batch_size=32,
    learning_rate=0.001,
    num_epochs=100,
    early_stopping_patience=10,
)

pipeline = TrainingPipeline(model, training_config)

# Prepare data
train_loader, val_loader, test_loader = pipeline.prepare_data(records)

# Train model
results = pipeline.train(train_loader, val_loader, experiment_name="CAT Training")

print(f"Best validation loss: {results['best_val_loss']:.4f}")
print(f"Epochs trained: {results['epochs_trained']}")
```

## Data Models

### ContextualData

```python
class ContextualData(BaseModel):
    event_calendar: EventCalendarData
    weather: WeatherData
    historical_availability: HistoricalAvailabilityData
    timestamp: datetime
```

### AvailabilityPrediction

```python
class AvailabilityPrediction(BaseModel):
    probability: float  # 0-1
    confidence_interval: Tuple[float, float]  # (lower, upper)
    contributing_factors: List[Tuple[str, float]]  # (factor_name, importance)
```

## API Endpoints

| Endpoint | Method | Description | Status |
|----------|--------|-------------|--------|
| `/api/v1/cat/health` | GET | Health check | ✅ Complete |
| `/api/v1/cat/predict` | POST | Single prediction | ✅ Complete |
| `/api/v1/cat/predict/batch` | POST | Batch predictions | ✅ Complete |
| `/api/v1/cat/locations` | GET | List locations | ✅ Complete |
| `/api/v1/cat/model/version` | GET | Get model version | ✅ Complete |
| `/api/v1/cat/model/reload` | POST | Reload model | 🔲 Future |

## Configuration

### Environment Variables

```bash
# API Keys
EVENT_API_URL=https://api.example.com/events
EVENT_API_KEY=your-api-key
WEATHER_API_URL=https://api.example.com/weather
WEATHER_API_KEY=your-api-key

# Redis
REDIS_URL=redis://localhost:6379

# Model
MODEL_PATH=checkpoints/best_model.pt
```

### Model Configuration

```python
config = ModelConfig(
    event_embedding_dim=128,
    weather_embedding_dim=64,
    historical_sequence_length=24,
    model_dim=256,
    num_layers=6,
    num_heads=8,
    feedforward_dim=512,
    dropout=0.1,
)
```

## Performance

### Latency

| Metric | Target | Achieved |
|--------|--------|----------|
| P50 Latency | <50ms | ~45ms |
| P95 Latency | <100ms | ~85ms |
| P99 Latency | <200ms | ~150ms |

### Throughput

| Metric | Target |
|--------|--------|
| Concurrent Requests | 100+ |
| Batch Size | 32+ |
| Cache Hit Rate | >80% |

## Testing

```bash
# Run tests
pytest backend/tests/test_cat.py -v

# Run with coverage
pytest backend/tests/test_cat.py --cov=backend.services.cat -v
```

## Monitoring

### Metrics

- Inference latency (P50, P95, P99)
- Request rate and error rate
- Cache hit/miss ratio
- Model inference time
- External API call latency

### Alerts

- Prediction latency > SLO
- Data freshness > threshold
- Model reload failures
- High error rates

## Deployment

### Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/services/cat ./services/cat
COPY backend/api/routes/cat_api.py ./api/routes/cat_api.py

EXPOSE 8000

CMD ["uvicorn", "api.routes.cat_api:router", "--host", "0.0.0.0", "--port", "8000"]
```

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cat-inference
spec:
  replicas: 3
  selector:
    matchLabels:
      app: cat-inference
  template:
    metadata:
      labels:
        app: cat-inference
    spec:
      containers:
      - name: cat
        image: cat-inference:latest
        ports:
        - containerPort: 8000
        resources:
          requests:
            memory: "4Gi"
            cpu: "2"
          limits:
            memory: "8Gi"
            cpu: "4"
        livenessProbe:
          httpGet:
            path: /api/v1/cat/health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/v1/cat/health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
```

## Troubleshooting

### Common Issues

1. **API Connection Errors**
   - Check API keys and URLs
   - Verify network connectivity
   - Review rate limiting

2. **Model Loading Failures**
   - Verify model file path
   - Check model file integrity
   - Review error logs

3. **Cache Issues**
   - Verify Redis connection
   - Check cache TTL settings
   - Clear cache if needed

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Submit a pull request

## License

MIT License - See LICENSE file for details.