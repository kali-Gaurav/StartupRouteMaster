# Offline Mode API Reference

## Endpoints

### 1. Search Routes (OFFLINE)

```
POST /api/offline/search
```

**Description:** Search for routes available in offline mode

**Parameters (JSON body):**
```json
{
    "source_station_code": "string",      // e.g., "NDLS" (required)
    "destination_station_code": "string",  // e.g., "CSMT" (required)
    "travel_date": "YYYY-MM-DD",          // e.g., "2026-03-01" (required)
    "departure_time": "HH:MM",            // e.g., "10:00" (optional, default: "10:00")
    "passengers": "integer",              // e.g., 2 (optional, default: 1)
    "max_transfers": "integer"            // e.g., 2 (optional, default: 2, max: 3)
}
```

**Response:**
```json
{
    "status": "VERIFIED_OFFLINE",
    "mode": "OFFLINE",
    "database": "railway_manager.db",
    "timestamp": "2026-02-20T14:30:00Z",
    "source_station": "NDLS",
    "destination_station": "CSMT",
    "travel_date": "2026-03-01",
    "departure_time": "10:00:00",
    "routes": [
        {
            "id": "route_001",
            "from_stop_code": "NDLS",
            "to_stop_code": "CSMT",
            "from_stop_name": "New Delhi",
            "to_stop_name": "CSMT Mumbai",
            "departure_time": "10:00:00",
            "arrival_time": "10:00:00",
            "summary_text": "NDLS 10:00 → CSMT 10:00 (next day)",
            "total_duration_hours": 24.0,
            "total_duration_minutes": 1440,
            "transfers_count": 1,
            "fare_min": 1500.0,
            "fare_max": 2500.0,
            "segments_count": 2,
            "status": "LOCKED",
            "unlock_token": "abc123xyz",
            "reliability_score": 0.95
        }
    ],
    "count": 5,
    "search_time_ms": 4.2
}
```

**Status Codes:**
- `200 OK` - Successful search
- `400 Bad Request` - Invalid input
- `404 Not Found` - Station not found
- `429 Too Many Requests` - Rate limited (10/minute)
- `500 Internal Server Error` - Server error

---

### 2. Unlock Route Details

```
POST /api/offline/routes/{route_id}/unlock
```

**Description:** Unlock full journey details for a specific route

**Path Parameters:**
```
route_id: string  // Route ID from search response
```

**Query Parameters (JSON body):**
```json
{
    "unlock_token": "string"  // Token from search response (required)
}
```

**Response:**
```json
{
    "status": "VERIFIED_OFFLINE",
    "route_id": "route_001",
    "segments": [
        {
            "segment_id": "seg_001",
            "from_stop_code": "NDLS",
            "from_stop_name": "New Delhi",
            "to_stop_code": "AGC",
            "to_stop_name": "Agra City",
            "trip_id": 12345,
            "train_number": "IR101",
            "train_name": "Rajdhani Express",
            "departure_time": "10:00:00",
            "arrival_time": "13:30:00",
            "duration_minutes": 210,
            "coaches": ["A1", "A2", "B1", "B2"],
            "class_availability": {
                "AC_1": {
                    "seats": 5,
                    "fare": 2500
                },
                "AC_2": {
                    "seats": 12,
                    "fare": 1800
                },
                "AC_3": {
                    "seats": 25,
                    "fare": 1200
                }
            },
            "fare_min": 1200.0,
            "fare_max": 2500.0,
            "distance_km": 235.5
        },
        {
            "segment_id": "seg_002",
            "from_stop_code": "AGC",
            "from_stop_name": "Agra City",
            "to_stop_code": "CSMT",
            "to_stop_name": "CSMT Mumbai",
            "trip_id": 67890,
            "train_number": "IR205",
            "train_name": "Shatabdi Express",
            "departure_time": "16:00:00",
            "arrival_time": "22:00:00",
            "duration_minutes": 1080,
            "coaches": ["A1", "2", "3"],
            "class_availability": {
                "AC_1": {
                    "seats": 8,
                    "fare": 3200
                },
                "AC_2": {
                    "seats": 15,
                    "fare": 2400
                }
            },
            "fare_min": 2400.0,
            "fare_max": 3200.0,
            "distance_km": 1280.0
        }
    ],
    "transfers": [
        {
            "from_arrival_time": "13:30:00",
            "from_arrival_station": "Agra City",
            "to_departure_time": "16:00:00",
            "to_departure_station": "Agra City",
            "waiting_time_minutes": 150,
            "risk_level": "SAFE",
            "walking_time_minutes": 5,
            "transfer_distance_km": 0.5,
            "notes": "2h 30min - plenty of time for comfortable transfer"
        }
    ],
    "total_fare": 4300.0,
    "total_duration_minutes": 1440,
    "total_transfers": 1,
    "route_reliability": 0.98,
    "verified_at": "2026-02-20T14:30:00Z",
    "verification_details": {
        "all_segments_verified": true,
        "all_transfers_feasible": true,
        "seats_available": true,
        "fares_matched": true
    }
}
```

**Status Codes:**
- `200 OK` - Successful unlock
- `400 Bad Request` - Invalid token/ parameters
- `404 Not Found` - Route not found
- `429 Too Many Requests` - Rate limited (10/minute)
- `500 Internal Server Error` - Server error

---

### 3. Get System Status

```
GET /api/offline/status
```

**Description:** Get current status of offline system

**Parameters:** None

**Response:**
```json
{
    "mode": "OFFLINE",
    "status": "READY",
    "database": "railway_manager.db",
    "graph_snapshot": "loaded",
    "stations_cached": 5234,
    "trips_cached": 8932,
    "calendars_cached": 156,
    "cache_size_routes": 1250,
    "timestamp": "2026-02-20T14:30:00Z"
}
```

**Status Codes:**
- `200 OK` - Status available
- `429 Too Many Requests` - Rate limited (20/minute)
- `500 Internal Server Error` - Server error

---

### 4. Health Check

```
GET /api/offline/health
```

**Description:** Simple offline system health check

**Parameters:** None

**Response:**
```json
{
    "status": "ok",
    "message": "Offline engine ready"
}
```

Possible responses:
```json
{"status": "ok", "message": "Offline engine ready"}
{"status": "warming_up", "message": "Loading caches"}
{"status": "error", "message": "Error description"}
```

---

## Error Responses

### Common Error Format

```json
{
    "detail": "Error message describing what went wrong"
}
```

### Examples

**Invalid station:**
```json
{
    "detail": "Could not find station: 'XYZ'. Please check spelling or try nearby stations."
}
```

**Invalid date format:**
```json
{
    "detail": "travel_date must be YYYY-MM-DD format"
}
```

**Invalid time format:**
```json
{
    "detail": "departure_time must be HH:MM format"
}
```

**Rate limit exceeded:**
```json
{
    "error": "Rate limit exceeded"
}
```

---

## Rate Limiting

- Search endpoint: 10 requests/minute per IP
- Unlock endpoint: 10 requests/minute per IP
- Status endpoint: 20 requests/minute per IP
- Health endpoint: No limit

---

## Transfer Risk Levels

Transfer "risk_level" can be:

| Level | Waiting Time | Safety |
|-------|--------------|--------|
| SAFE | > 2 hours | Very safe transfer |
| LOW | 30-120 minutes | Comfortable |
| MEDIUM | 10-30 minutes | Reasonable |
| HIGH | 5-10 minutes | Risky |
| RISKY | < 5 minutes | Very risky |

---

## Class Abbreviations

Common train classes in India:

| Code | Name | Level |
|------|------|-------|
| AC_1 | AC First Class | Premium |
| AC_2 | AC 2-Tier | Upper-Mid |
| AC_3 | AC 3-Tier | Mid |
| SL | Sleeper | Budget |
| 2S | 2nd Seating | Economy |

---

## Example Workflows

### Workflow 1: Search and Display

```bash
# Step 1: Search
curl -X POST http://localhost:8000/api/offline/search \
  -H "Content-Type: application/json" \
  -d '{
    "source_station_code": "NDLS",
    "destination_station_code": "CSMT",
    "travel_date": "2026-03-01",
    "departure_time": "10:00"
  }'

# Get list of routes (LOCKED state)
# Display to user:
# 1. NDLS 10:00 → CSMT 10:00 (24h, 1 transfer) ₹1500-2500
# 2. NDLS 11:00 → CSMT 11:00 (24h, 2 transfers) ₹1200-2000
# ...
```

### Workflow 2: User Click "See Full Details"

```bash
# Step 2: Unlock selected route
curl -X POST "http://localhost:8000/api/offline/routes/route_001/unlock" \
  -H "Content-Type: application/json" \
  -d '{"unlock_token": "abc123xyz"}'

# Get full journey:
# Segment 1: IR101 NDLS 10:00 → AGC 13:30 (AC_1: ₹2500, AC_2: ₹1800)
# Transfer: 2h 30m at AGC (SAFE)
# Segment 2: IR205 AGC 16:00 → CSMT 22:00 (AC_1: ₹3200, AC_2: ₹2400)
# Total: ₹4300
```

### Workflow 3: Monitor System

```bash
# Get status
curl http://localhost:8000/api/offline/status

# Returns
{
    "mode": "OFFLINE",
    "status": "READY",
    "stations_cached": 5234,
    "trips_cached": 8932,
    ...
}
```

---

## Integration Notes

- All times are in HH:MM or HH:MM:SS format (24-hour)
- All dates are in YYYY-MM-DD format
- All fares are in local currency (₹ for India)
- All distances in kilometers
- All durations in minutes

---

## See Also

- `OFFLINE_MODE_GUIDE.md` - Complete offline system guide
- `core/README.md` - Core routing engine documentation
- `phase2-offline-route-engine.md` - Implementation plan
