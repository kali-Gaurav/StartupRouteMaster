# Route Engine Evolution - API Contracts

**Version:** 2.0.0  
**Last Updated:** 2026-05-08  
**Status:** READY FOR FRONTEND INTEGRATION

---

## Table of Contents

1. [Overview](#overview)
2. [Base URL & Authentication](#base-url--authentication)
3. [Unified Route Search](#unified-route-search)
4. [SSE Progressive Delivery](#sse-progressive-delivery)
5. [Query Plan Optimizer](#query-plan-optimizer)
6. [Transfer Intelligence Score](#transfer-intelligence-score)
7. [Corridor Safety Bus](#corridor-safety-bus)
8. [Data Models](#data-models)
9. [Error Handling](#error-handling)
10. [WebSocket Events](#websocket-events)

---

## Overview

The Route Engine provides a tiered intelligence pipeline that delivers AI-enriched route recommendations:

```
Client Request → QPO (50ms) → RAPTOR (500ms) → TIS (100ms) → Safety (50ms) → SSE Stream
```

**Target Latency:** 700ms for fully enriched routes  
**First Route:** < 500ms via SSE streaming

---

## Base URL & Authentication

### Base URL
```
https://api.routemaster.in/v1
```

### Authentication
All endpoints require JWT authentication via `Authorization` header:

```http
Authorization: Bearer <jwt_token>
```

### Rate Limiting
- **Standard:** 100 requests/minute
- **SSE Stream:** 50 concurrent connections/user
- **Batch Search:** 10 batches/minute

---

## Unified Route Search

### Quick Search (GET)

**Endpoint:** `GET /api/v1/routes/quick`

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| source | string | Yes | Source station code (e.g., "NDLS") |
| destination | string | Yes | Destination station code (e.g., "BCT") |
| travel_date | string | Yes | Travel date (YYYY-MM-DD) |

**Response:**
```json
{
  "source": "NDLS",
  "destination": "BCT",
  "travel_date": "2026-05-15",
  "route_count": 5,
  "routes": [
    {
      "duration": 420,
      "departure": "06:00:00",
      "arrival": "13:00:00",
      "transfers": 0,
      "score": 92.5,
      "risk": "low"
    }
  ]
}
```

---

### Full Search (POST)

**Endpoint:** `POST /api/v1/routes/search`

**Request Body:**
```json
{
  "source": "NDLS",
  "destination": "BCT",
  "travel_date": "2026-05-15",
  "travel_time": "10:00:00",
  "preferred_train_types": ["SUPFAST", "rajdhani"],
  "max_price": 2500,
  "require_ac": true,
  "max_routes": 10,
  "user_id": "user_123"
}
```

**Response:**
```json
{
  "query_id": "qpo-1778227354.596855",
  "source": "NDLS",
  "destination": "BCT",
  "travel_date": "2026-05-15",
  "total_routes_found": 15,
  "routes": [
    {
      "journey_id": "JRN-001",
      "overall_score": 92.5,
      "risk_level": "low",
      "journey": {
        "journey_id": "JRN-001",
        "total_duration_minutes": 420,
        "total_fare": 1850.0,
        "transfers": 0,
        "departure_time": "06:00:00",
        "arrival_time": "13:00:00",
        "availability_status": "AVAILABLE",
        "safety_score": 95,
        "demand_factor": 1.2,
        "segments": [
          {
            "train_number": "12001",
            "train_name": "Bhopal Shatabdi",
            "from_station_code": "NDLS",
            "from_station_name": "New Delhi",
            "to_station_code": "BCT",
            "to_station_name": "Mumbai Central",
            "departure_time": "06:00:00",
            "arrival_time": "13:00:00",
            "duration_minutes": 420,
            "class_type": "AC Chair Car",
            "fare": 1850.0,
            "availability": "AVAILABLE"
          }
        ]
      },
      "quality_score": 90,
      "safety_score": 95,
      "transfer_score": 100,
      "safety_events": [],
      "pareto_rank": 1
    }
  ],
  "pipeline_metrics": {
    "qpo_time_ms": 45,
    "raptor_time_ms": 480,
    "tis_time_ms": 85,
    "safety_time_ms": 32,
    "total_time_ms": 642
  }
}
```

---

## SSE Progressive Delivery

### Streaming Endpoint

**Endpoint:** `GET /api/v1/routes/search/stream`

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| source | string | Yes | Source station code |
| destination | string | Yes | Destination station code |
| travel_date | string | Yes | Travel date (YYYY-MM-DD) |
| travel_time | string | No | Preferred departure time |
| max_routes | integer | No | Max routes to stream (default: 10) |

**Response Content-Type:** `text/event-stream`

### SSE Event Types

| Event Type | Description | Payload |
|------------|-------------|---------|
| `connected` | Connection established | `{ "connection_id": "conn-xxx", "timestamp": "..." }` |
| `route` | New route found | Route object (see Full Search response) |
| `progress` | Search progress update | `{ "stage": "raptor", "progress": 65 }` |
| `complete` | Search complete | `{ "total_routes": 15, "duration_ms": 642 }` |
| `heartbeat` | Keep-alive ping | `{ "timestamp": "..." }` |
| `error` | Error occurred | `{ "error": "description", "code": 500 }` |

### SSE Event Format

```javascript
event: route
data: {
  "journey_id": "JRN-001",
  "overall_score": 92.5,
  "risk_level": "low",
  ...
}

event: progress
data: {
  "stage": "tis_scoring",
  "progress": 75
}

event: complete
data: {
  "total_routes": 15,
  "duration_ms": 642
}
```

### Frontend SSE Handler Example

```javascript
const eventSource = new EventSource(
  `/api/v1/routes/search/stream?source=NDLS&destination=BCT&travel_date=2026-05-15`
);

eventSource.addEventListener('connected', (e) => {
  const data = JSON.parse(e.data);
  console.log('Connected:', data.connection_id);
  showLoadingState();
});

eventSource.addEventListener('route', (e) => {
  const route = JSON.parse(e.data);
  addRouteToList(route);
  updateProgressBar(50); // Routes are arriving
});

eventSource.addEventListener('progress', (e) => {
  const progress = JSON.parse(e.data);
  updatePipelineStage(progress.stage, progress.progress);
});

eventSource.addEventListener('complete', (e) => {
  const result = JSON.parse(e.data);
  hideLoadingState();
  showRouteCount(result.total_routes);
});

eventSource.addEventListener('error', (e) => {
  const error = JSON.parse(e.data);
  showError(error.message);
  eventSource.close();
});

// Heartbeat handler (every 30 seconds)
eventSource.addEventListener('heartbeat', (e) => {
  console.log('Connection alive');
});
```

---

## Query Plan Optimizer

### Analyze Query

**Endpoint:** `POST /api/v1/routes/qpo/analyze`

**Request Body:**
```json
{
  "source": "NDLS",
  "destination": "BCT",
  "travel_date": "2026-05-15",
  "travel_time": "10:00:00",
  "preferred_train_types": [],
  "max_price": null,
  "require_ac": false,
  "user_id": null,
  "is_peak_hour": false
}
```

**Response:**
```json
{
  "query_id": "qpo-1778227354.596855",
  "search_depth": "direct",
  "database_target": "primary",
  "hub_priorities": [
    {
      "station_code": "NDLS",
      "priority": 0.91,
      "transfer_success_rate": 0.85
    },
    {
      "station_code": "BCT",
      "priority": 0.85,
      "transfer_success_rate": 0.82
    }
  ],
  "estimated_latency_ms": 300,
  "confidence": 0.85,
  "reasoning": [
    "Search depth: direct",
    "Database target: primary",
    "Hub count: 2",
    "Estimated latency: 300ms",
    "Confidence: 85.0%"
  ]
}
```

### Estimate Latency

**Endpoint:** `GET /api/v1/routes/qpo/estimate-latency`

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| source | string | Yes | Source station code |
| destination | string | Yes | Destination station code |
| travel_date | string | Yes | Travel date |
| search_depth | string | No | one_transfer (default) |

**Response:**
```json
{
  "estimated_latency_ms": 450,
  "confidence": 0.78,
  "search_depth_recommendation": "one_transfer",
  "database_target": "read_replica"
}
```

---

## Transfer Intelligence Score

### Get Transfer Score

**Endpoint:** `GET /api/v1/routes/transfer/score`

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| transfer_station | string | Yes | Transfer station code |
| arrival_train | string | Yes | Arrival train number |
| departure_train | string | Yes | Departure train number |
| connection_time | integer | Yes | Connection time in minutes |

**Response:**
```json
{
  "transfer_station": "NDLS",
  "arrival_train": "12001",
  "departure_train": "12002",
  "connection_time_minutes": 30,
  "tis_score": 78.5,
  "risk_level": "medium",
  "historical_success_rate": 0.82,
  "buffer_factor": 0.65,
  "train_factor": 0.90,
  "time_factor": 0.75,
  "indicator": {
    "color": "yellow",
    "icon": "⚠️",
    "label": "Medium Risk"
  },
  "recommendations": [
    "Allow at least 25 minutes for this connection",
    "Consider trains with longer layover at NDLS"
  ]
}
```

### Score Journey

**Endpoint:** `POST /api/v1/routes/transfer/score-journey`

**Request Body:**
```json
{
  "journey": {
    "journey_id": "JRN-001",
    "segments": [
      {
        "train_number": "12001",
        "from_station_code": "NDLS",
        "to_station_code": "BCT"
      }
    ]
  }
}
```

**Response:**
```json
{
  "journey_id": "JRN-001",
  "overall_score": 85.0,
  "risk_level": "low",
  "transfer_details": [],
  "recommendations": [
    "This is a direct route with no transfers"
  ]
}
```

---

## Corridor Safety Bus

### Get Corridor Safety Status

**Endpoint:** `GET /api/v1/routes/safety/status`

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| source | string | Yes | Source station code |
| destination | string | Yes | Destination station code |

**Response:**
```json
{
  "corridor": "NDLS-BCT",
  "safety_score": 0.95,
  "risk_level": "low",
  "active_events": 0,
  "affected_stations": [],
  "last_updated": "2026-05-08T13:30:00Z"
}
```

### Get Active Safety Events

**Endpoint:** `GET /api/v1/routes/safety/events`

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| corridor | string | No | Filter by corridor |
| severity | string | No | Filter by severity |
| active_only | boolean | No | Only active events |

**Response:**
```json
{
  "events": [
    {
      "event_id": "evt-001",
      "event_type": "corridor_alert",
      "corridor": "NDLS-BCT",
      "stations": ["NDLS", "BCT"],
      "severity": "moderate",
      "description": "Heavy crowd expected at NDLS",
      "start_time": "2026-05-08T08:00:00Z",
      "end_time": null,
      "safety_penalty": 0.5
    }
  ],
  "total_count": 1
}
```

### Publish Safety Event

**Endpoint:** `POST /api/v1/routes/safety/events`

**Request Body:**
```json
{
  "event_type": "corridor_alert",
  "corridor": "NDLS-BCT",
  "stations": ["NDLS", "BCT"],
  "severity": "moderate",
  "description": "Heavy crowd expected",
  "start_time": "2026-05-08T08:00:00Z",
  "end_time": null
}
```

**Response:**
```json
{
  "event_id": "evt-001",
  "status": "published",
  "timestamp": "2026-05-08T13:30:00Z"
}
```

---

## Data Models

### RouteSegment
```typescript
interface RouteSegment {
  train_number: string;       // e.g., "12001"
  train_name: string;         // e.g., "Bhopal Shatabdi"
  from_station_code: string;  // e.g., "NDLS"
  from_station_name: string;  // e.g., "New Delhi"
  to_station_code: string;    // e.g., "BCT"
  to_station_name: string;    // e.g., "Mumbai Central"
  departure_time: string;     // ISO time "HH:MM:SS"
  arrival_time: string;       // ISO time "HH:MM:SS"
  duration_minutes: number;   // Total duration in minutes
  class_type: string;         // e.g., "AC Chair Car"
  fare: number;               // Fare in INR
  availability: string;       // "AVAILABLE" | "WAITLIST" | "FULL"
}
```

### Journey
```typescript
interface Journey {
  journey_id: string;
  segments: RouteSegment[];
  total_duration: number;         // Minutes
  total_fare: number;             // INR
  transfers: number;              // Number of transfers
  departure_time: string;         // ISO time
  arrival_time: string;           // ISO time
  availability_status: string;    // "AVAILABLE" | "LIMITED" | "UNAVAILABLE"
  safety_score: number;           // 0-100
  demand_factor: number;          // 0.5-2.0
}
```

### EnrichedRoute
```typescript
interface EnrichedRoute {
  journey: Journey;
  overall_score: number;          // 0-100
  quality_score: number;          // 0-100
  safety_score: number;           // 0-100
  transfer_score: number;         // 0-100
  risk_level: "low" | "medium" | "high";
  safety_events: SafetyEvent[];
  pareto_rank: number;            // Rank on Pareto frontier
}
```

### SafetyEvent
```typescript
interface SafetyEvent {
  event_id: string;
  event_type: "station_alert" | "corridor_alert" | "route_disruption" | "weather_warning";
  corridor: string;               // e.g., "NDLS-BCT"
  stations: string[];             // Affected stations
  severity: "critical" | "high" | "moderate" | "low" | "minimal";
  description: string;
  start_time: string;             // ISO datetime
  end_time: string | null;        // ISO datetime or null
  safety_penalty: number;         // 0.0-1.0
}
```

### TransferScore
```typescript
interface TransferScore {
  transfer_station: string;
  arrival_train: string;
  departure_train: string;
  connection_time_minutes: number;
  tis_score: number;              // 0-100
  risk_level: "low" | "medium" | "high" | "unknown";
  historical_success_rate: number; // 0.0-1.0
  buffer_factor: number;          // 0.0-1.0
  train_factor: number;           // 0.0-1.0
  time_factor: number;            // 0.0-1.0
  indicator: {
    color: "green" | "yellow" | "red";
    icon: string;                 // Emoji
    label: string;                // Display label
  };
  recommendations: string[];
}
```

---

## Error Handling

### Error Response Format

```json
{
  "error": {
    "code": 400,
    "message": "Invalid station code",
    "details": {
      "field": "source",
      "value": "INVALID"
    }
  },
  "timestamp": "2026-05-08T13:30:00Z"
}
```

### HTTP Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Bad Request (invalid parameters) |
| 401 | Unauthorized (missing/invalid JWT) |
| 403 | Forbidden (rate limit exceeded) |
| 404 | Not Found (station not found) |
| 422 | Validation Error |
| 500 | Internal Server Error |
| 503 | Service Unavailable |

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `INVALID_STATION_CODE` | Station code not found | Verify station code |
| `NO_ROUTES_FOUND` | No routes available | Try different date/time |
| `CONNECTION_TIMEOUT` | SSE connection timeout | Reconnect |
| `RATE_LIMIT_EXCEEDED` | Too many requests | Wait and retry |

---

## WebSocket Events

For real-time updates (alternative to SSE):

```javascript
// Connect to WebSocket
const ws = new WebSocket('wss://api.routemaster.in/v1/routes/ws');

// Send search request
ws.send(JSON.stringify({
  type: 'search',
  payload: {
    source: 'NDLS',
    destination: 'BCT',
    travel_date: '2026-05-15'
  }
}));

// Receive messages
ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  switch (message.type) {
    case 'route':
      handleRoute(message.data);
      break;
    case 'progress':
      handleProgress(message.data);
      break;
    case 'complete':
      handleComplete(message.data);
      break;
  }
};
```

---

## Frontend Integration Checklist

- [ ] Set up JWT authentication
- [ ] Implement SSE connection handling with reconnection logic
- [ ] Create route list component with progressive disclosure
- [ ] Add transfer indicator badges (green/yellow/red)
- [ ] Implement safety score display (shield icons)
- [ ] Add loading states with pipeline progress
- [ ] Handle error states and retry logic
- [ ] Implement route comparison UI
- [ ] Add analytics tracking for user behavior

---

## Support

- **API Documentation:** /docs
- **Status Page:** status.routemaster.in
- **Support Email:** api-support@routemaster.in