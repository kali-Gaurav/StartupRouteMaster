# RouteMaster Backend - Quick Start Guide

## 5-Minute Setup

### 1. Install Dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.example .env
```

Edit `.env` with your Supabase credentials:
```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_anon_key
DATABASE_URL=postgresql://user:pass@localhost/routemaster
```

### 3. Start the Server
```bash
python app.py
```

Server runs at: `http://localhost:8000`

## Testing the API

### Via cURL

**1. Health Check**
```bash
curl http://localhost:8000/api/health
```

**2. Search Routes**
```bash
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{
    "source": "Mumbai",
    "destination": "Goa",
    "date": "2025-12-25",
    "budget": "economy"
  }'
```

**3. Get Route Details**
```bash
curl http://localhost:8000/api/route/{route_id}
```

**4. Create Payment Order**
```bash
curl -X POST http://localhost:8000/api/create_order \
  -H "Content-Type: application/json" \
  -d '{
    "route_id": "route-uuid",
    "user_name": "John Doe",
    "user_email": "john@example.com",
    "user_phone": "9876543210",
    "travel_date": "2025-12-25"
  }'
```

**5. Admin Bookings (with token)**
```bash
curl http://localhost:8000/api/admin/bookings \
  -H "X-Admin-Token: your_admin_token"
```

### Via Interactive Docs
Open browser to: `http://localhost:8000/docs`

## Running Tests

```bash
# All tests
pytest

# Specific file
pytest tests/test_search.py -v

# With coverage
pytest --cov=.
```

## Common Issues & Solutions

### Issue: Database Connection Error
**Solution:**
```bash
# Check DATABASE_URL in .env
# Verify PostgreSQL is running
# Create database if missing:
createdb routemaster
```

### Issue: Import Errors
**Solution:**
```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### Issue: Port Already in Use
**Solution:**
```bash
# Use different port
python -c "import uvicorn; uvicorn.run('app:app', host='0.0.0.0', port=8001)"
```

### Issue: Razorpay Errors
**Solution:**
```bash
# Razorpay integration is optional
# API returns helpful error message if not configured
# Add your keys to .env to enable payments:
RAZORPAY_KEY_ID=your_key_id
RAZORPAY_KEY_SECRET=your_secret
```

## Performance Testing

### Test Route Search Speed
```python
import time
import requests

url = "http://localhost:8000/api/search"
payload = {
    "source": "Mumbai",
    "destination": "Goa",
    "date": "2025-12-25",
    "budget": "all"
}

# First request (uncached)
start = time.time()
resp1 = requests.post(url, json=payload)
uncached_time = time.time() - start

# Second request (cached)
start = time.time()
resp2 = requests.post(url, json=payload)
cached_time = time.time() - start

print(f"Uncached: {uncached_time*1000:.0f}ms")
print(f"Cached: {cached_time*1000:.0f}ms")
print(f"Response: {resp1.json()['duration_ms']}ms (per API)")
```

Expected results:
- First request: 50-150ms
- Cached request: 10-30ms

## Database Seeding

The application automatically seeds sample data on first initialization.

Available sample routes:
- Mumbai ↔ Goa (train, flight)
- Delhi ↔ Manali (bus, flight+taxi)
- Bangalore ↔ Coorg (bus, car)
- Chennai ↔ Pondicherry (bus, car)

## Project Structure Reference

```
backend/
├── app.py              # Main FastAPI app
├── config.py           # Configuration
├── models.py           # Database models
├── schemas.py          # Request/response schemas
├── database.py         # DB connection
│
├── services/
│   ├── route_engine.py      # Route optimization
│   ├── cache_service.py     # LRU cache
│   ├── payment_service.py   # Razorpay
│   └── booking_service.py   # Bookings
│
├── api/
│   ├── search.py       # Search endpoints
│   ├── routes.py       # Route detail endpoints
│   ├── payments.py     # Payment endpoints
│   └── admin.py        # Admin endpoints
│
├── utils/
│   ├── time_utils.py      # Time calculations
│   ├── validators.py      # Input validation
│   └── graph_utils.py     # Graph algorithms
│
├── tests/              # Test files
├── requirements.txt    # Dependencies
├── README.md          # Full documentation
├── ARCHITECTURE.md    # Technical details
└── QUICKSTART.md      # This file
```

## API Endpoints Quick Reference

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/` | Root / Status |
| GET | `/api/health` | Health check |
| POST | `/api/search` | Search routes |
| GET | `/api/route/{id}` | Route details |
| GET | `/api/routes/available-locations` | City list |
| POST | `/api/create_order` | Create payment order |
| POST | `/api/payment/webhook` | Payment webhook |
| GET | `/api/admin/bookings` | All bookings (admin) |
| GET | `/api/admin/bookings/stats` | Booking stats (admin) |
| GET | `/api/admin/bookings/filter` | Filter bookings (admin) |

## Next Steps

1. **Frontend Integration**: Connect React app to these endpoints
2. **Production Deployment**: Docker or cloud hosting
3. **Monitoring**: Set up logging and error tracking
4. **Performance Tuning**: Monitor and optimize based on real usage
5. **Feature Expansion**: Add seat availability, customer reviews, etc.

## Documentation

- **Full API Docs**: http://localhost:8000/docs
- **README**: See `README.md`
- **Architecture**: See `ARCHITECTURE.md`

## Getting Help

1. Check API documentation at `/docs`
2. Review logs in console output
3. Consult `README.md` for detailed info
4. Check `ARCHITECTURE.md` for technical details
5. Review test files for usage examples

Happy routing! 🚀
