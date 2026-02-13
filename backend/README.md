# RouteMaster Backend API

High-performance route optimization and booking platform built with FastAPI and SQLAlchemy.

## Features

- **Fast Route Search**: Multi-segment route generation in <100ms using optimized Dijkstra's algorithm
- **Intelligent Caching**: LRU cache for recent searches with automatic TTL expiration
- **A* Heuristic Pruning**: Uses haversine distance for efficient path exploration
- **Razorpay Integration**: Secure payment processing for route unlock (₹39)
- **Booking Management**: Complete booking lifecycle from search to confirmation
- **Admin Dashboard API**: Comprehensive booking analytics and management
- **Time-Expanded Graph**: Efficient representation of transport networks with temporal constraints

## Project Structure

```
backend/
├── app.py                 # FastAPI application entry point
├── config.py              # Configuration management
├── database.py            # SQLAlchemy setup and connection pooling
├── models.py              # Database ORM models
├── schemas.py             # Pydantic request/response schemas
│
├── services/              # Business logic layer
│   ├── route_engine.py    # Core route generation algorithm
│   ├── cache_service.py   # LRU cache implementation
│   ├── payment_service.py # Razorpay integration
│   └── booking_service.py # Booking persistence
│
├── api/                   # API endpoints
│   ├── search.py         # Route search endpoints
│   ├── routes.py         # Route detail endpoints
│   ├── payments.py       # Payment endpoints
│   └── admin.py          # Admin management endpoints
│
├── utils/                # Utility functions
│   ├── time_utils.py     # Time calculations and formatting
│   ├── validators.py     # Input validation
│   └── graph_utils.py    # Graph operations and algorithms
│
├── tests/                # Automated tests
│   ├── test_search.py
│   ├── test_route_engine.py
│   └── test_payment.py
│
├── requirements.txt      # Python dependencies
├── .env.example         # Environment variable template
└── README.md            # This file
```

## Installation

### Prerequisites

- Python 3.9+
- PostgreSQL 12+ (Supabase or local)
- pip

### Setup

1. **Clone and navigate to backend directory:**
   ```bash
   cd backend
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   ```bash
   cp .env.example .env
   ```

   Edit `.env` and set:
   ```
   SUPABASE_URL=your_supabase_url
   SUPABASE_KEY=your_supabase_anon_key
   DATABASE_URL=postgresql://user:password@host:5432/routemaster

   RAZORPAY_KEY_ID=your_razorpay_key_id
   RAZORPAY_KEY_SECRET=your_razorpay_key_secret

   ADMIN_API_TOKEN=your_secure_admin_token
   ```

5. **Seed database:**
   ```bash
   python -c "from database import init_db; import asyncio; asyncio.run(init_db())"
   ```

## Running the Server

### Development Mode
```bash
python app.py
```

The API will be available at `http://localhost:8000`

### Production Mode
```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --workers 4
```

## API Documentation

### Interactive Docs
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## API Endpoints

### Search Routes

#### `POST /api/search`
Search for routes between two locations.

**Request:**
```json
{
  "source": "Mumbai",
  "destination": "Goa",
  "date": "2025-12-25",
  "budget": "economy"
}
```

**Response:**
```json
{
  "success": true,
  "routes": [
    {
      "id": "route-uuid",
      "source": "Mumbai",
      "destination": "Goa",
      "segments": [...],
      "total_duration": "12h 30m",
      "total_cost": 600,
      "budget_category": "economy",
      "num_transfers": 1
    }
  ],
  "cached": false,
  "duration_ms": 95
}
```

### Route Details

#### `GET /api/route/{route_id}`
Get detailed information about a specific route.

**Response:**
```json
{
  "success": true,
  "route": {
    "id": "route-uuid",
    "source": "Mumbai",
    "destination": "Goa",
    "segments": [
      {
        "mode": "Train",
        "from": "Mumbai",
        "to": "Goa",
        "duration": "12h",
        "cost": 450,
        "details": "Konkan Kanya Express"
      }
    ],
    "total_duration": "12h",
    "total_cost": 450,
    "budget_category": "economy",
    "num_transfers": 0,
    "created_at": "2025-12-20T10:00:00"
  }
}
```

### Payments

#### `POST /api/create_order`
Create Razorpay payment order for route unlock.

**Request:**
```json
{
  "route_id": "route-uuid",
  "user_name": "John Doe",
  "user_email": "john@example.com",
  "user_phone": "9876543210",
  "travel_date": "2025-12-25"
}
```

**Response:**
```json
{
  "success": true,
  "order_id": "order_123",
  "booking_id": "booking-uuid",
  "amount": 39,
  "currency": "INR",
  "key_id": "razorpay-key"
}
```

#### `POST /api/payment/webhook`
Verify Razorpay payment (webhook).

**Request:**
```json
{
  "razorpay_payment_id": "pay_123",
  "razorpay_order_id": "order_123",
  "razorpay_signature": "signature_hash",
  "booking_id": "booking-uuid"
}
```

### Admin Endpoints

#### `GET /api/admin/bookings`
Get all bookings (requires admin token).

**Headers:**
```
X-Admin-Token: your_admin_token
```

**Query Parameters:**
- `limit`: Max results (default: 100, max: 1000)
- `offset`: Results offset (default: 0)

#### `GET /api/admin/bookings/stats`
Get booking statistics.

**Response:**
```json
{
  "success": true,
  "stats": {
    "total_bookings": 150,
    "completed_bookings": 140,
    "pending_bookings": 10,
    "total_revenue": 5460
  }
}
```

#### `GET /api/admin/bookings/filter`
Filter bookings by status.

**Query Parameters:**
- `status`: pending | completed | failed
- `limit`: Max results
- `offset`: Results offset

## Performance Optimization

### Route Generation Algorithm

**Time Complexity**: O(E log V) where E = edges, V = time-expanded nodes

**Optimizations:**

1. **Time-Expanded Graph**: Pre-computed graph of stations and schedules
2. **A* Heuristic**: Uses haversine distance to prune unlikely paths
3. **Transfer Constraints**: Enforces 15-60 minute transfer windows
4. **Budget Pruning**: Discards paths exceeding budget limit
5. **Max Transfer Limit**: Prunes paths with >3 transfers

### Caching Strategy

**Search Cache (LRU):**
- Key: (source, destination, date, budget)
- Size: 1000 recent searches
- TTL: 3600 seconds (configurable)

**Graph Cache:**
- Pre-loads all stations and segments at startup
- In-memory storage for fast access

### Connection Pooling

- Pool size: 10 connections
- Max overflow: 20 connections
- Connection timeout: 30 seconds
- Pre-ping: Validates connection health

## Testing

### Run All Tests
```bash
pytest
```

### Run Specific Test File
```bash
pytest tests/test_search.py -v
```

### Run with Coverage
```bash
pytest --cov=. --cov-report=html
```

### Test Categories

**test_search.py**
- Route engine initialization
- Station lookup (case-insensitive)
- Route search and sorting
- Budget filtering

**test_route_engine.py**
- Time calculations (duration, formatting)
- Day-of-week validation
- Graph operations
- Input validation
- Distance calculations

**test_payment.py**
- Payment order creation
- Signature verification
- Razorpay integration (mocked)

## Database Schema

### Stations Table
```sql
CREATE TABLE stations (
  id UUID PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  city VARCHAR(255) NOT NULL,
  latitude FLOAT NOT NULL,
  longitude FLOAT NOT NULL,
  created_at TIMESTAMP DEFAULT NOW()
);
```

### Segments Table
```sql
CREATE TABLE segments (
  id UUID PRIMARY KEY,
  source_station_id UUID REFERENCES stations(id),
  dest_station_id UUID REFERENCES stations(id),
  transport_mode VARCHAR(50),
  departure_time VARCHAR(5),
  arrival_time VARCHAR(5),
  duration_minutes INTEGER,
  cost FLOAT,
  operator VARCHAR(255),
  operating_days VARCHAR(7),
  created_at TIMESTAMP DEFAULT NOW()
);
```

### Routes Table
```sql
CREATE TABLE routes (
  id UUID PRIMARY KEY,
  source VARCHAR(255),
  destination VARCHAR(255),
  segments JSONB,
  total_duration VARCHAR(50),
  total_cost FLOAT,
  budget_category VARCHAR(50),
  num_transfers INTEGER,
  created_at TIMESTAMP DEFAULT NOW()
);
```

### Bookings Table
```sql
CREATE TABLE bookings (
  id UUID PRIMARY KEY,
  user_name VARCHAR(255),
  user_email VARCHAR(255),
  user_phone VARCHAR(20),
  route_id UUID REFERENCES routes(id),
  travel_date VARCHAR(10),
  payment_id VARCHAR(255),
  payment_status VARCHAR(50),
  amount_paid FLOAT,
  booking_details JSONB,
  created_at TIMESTAMP DEFAULT NOW()
);
```

## Sample Data

The backend includes sample routes:

- **Mumbai ↔ Goa**: Train (12h, ₹450) or Flight (2h, ₹3500)
- **Delhi ↔ Manali**: Bus (14h, ₹800) or Flight + Taxi (9h, ₹6500)
- **Bangalore ↔ Coorg**: Bus (6h, ₹500) or Car Rental (5h, ₹2650)
- **Chennai ↔ Pondicherry**: Bus (3h, ₹300) or Car (2h, ₹1880)

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| SUPABASE_URL | - | Supabase project URL |
| SUPABASE_KEY | - | Supabase anon key |
| DATABASE_URL | - | PostgreSQL connection string |
| RAZORPAY_KEY_ID | - | Razorpay API key ID |
| RAZORPAY_KEY_SECRET | - | Razorpay API secret |
| ADMIN_API_TOKEN | - | Admin API authentication token |
| CACHE_TTL_SECONDS | 3600 | Search cache time-to-live |
| MAX_TRANSFERS | 3 | Maximum transfers allowed |
| TRANSFER_WINDOW_MIN | 15 | Min transfer time (minutes) |
| TRANSFER_WINDOW_MAX | 60 | Max transfer time (minutes) |
| MAX_SEARCH_RESULTS | 10 | Max routes per search |
| ENVIRONMENT | development | Environment (development/production) |
| LOG_LEVEL | INFO | Logging level |

## Error Handling

The API returns consistent error responses:

```json
{
  "detail": "Error message describing what went wrong"
}
```

Common HTTP Status Codes:
- `200`: Success
- `400`: Bad request (invalid input)
- `401`: Unauthorized (missing/invalid admin token)
- `404`: Resource not found
- `500`: Server error

## Performance Benchmarks

Target metrics for typical operations:

- **Route Search**: <100ms (cached), <150ms (uncached)
- **Order Creation**: <200ms
- **Payment Verification**: <50ms
- **Admin Queries**: <100ms

## Troubleshooting

### Database Connection Failed
- Verify DATABASE_URL is correct
- Check PostgreSQL is running
- Ensure database exists

### Razorpay Integration Not Working
- Verify keys are set in .env
- Check Razorpay account is in correct mode (test/live)
- Review payment webhook logs

### Slow Route Search
- Check cache statistics: GET `/health`
- Verify database indexes are created
- Review query performance in logs

## Deployment

### Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment for Production

Set in production `.env`:
```
ENVIRONMENT=production
LOG_LEVEL=WARNING
CACHE_TTL_SECONDS=7200
MAX_SEARCH_RESULTS=5
```

## Contributing

1. Create feature branch
2. Write tests for new features
3. Ensure all tests pass
4. Submit pull request

## License

Proprietary - RouteMaster Platform

## Support

For issues or questions, contact: support@routemaster.com
