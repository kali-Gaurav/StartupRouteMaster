# Guardian AI - Frontend Integration Guide

The Guardian AI is an autonomous, persistent background safety agent that protects users during their journey. It constantly evaluates user location, chat behavior, and trip data to calculate real-time risk scores and automatically escalate issues (e.g., calling emergency contacts or authorities).

## API Endpoints (`/api/v3/guardian`)

### 1. Initialize a Safety Mission
**POST** `/api/v3/guardian/mission`

Initializes a new Guardian AI mission for a user. This should be called when a user starts a journey or opts into the safety tracking feature.

**Request Body:**
```json
{
  "user_id": "string",
  "journey_details": {
    "train_number": "string",
    "pnr": "string (optional)",
    "source_station": "string",
    "destination_station": "string"
  }
}
```

**Response:**
```json
{
  "status": "success",
  "mission_id": "msn_xxxxxxxxxxxx",
  "message": "Guardian AI Mission started."
}
```

---

### 2. Update Passenger Location
**POST** `/api/v3/guardian/mission/{mission_id}/location`

Pings the Guardian AI with the user's latest GPS coordinates. The frontend should send this every few minutes while the mission is active.

**Request Body:**
```json
{
  "latitude": 28.6139,
  "longitude": 77.2090,
  "station": "NDLS (optional)"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Location updated."
}
```

---

### 3. Send Message for Behavioral Analysis
**POST** `/api/v3/guardian/mission/{mission_id}/message`

Sends user chat messages to the Guardian AI. The AI analyzes text locally (without latency) for distress keywords (e.g., "scared", "harass", "police"). If an anomaly is detected, the risk score is automatically adjusted, and actions may be triggered.

**Request Body:**
```json
{
  "text": "The train is very dark and I feel scared."
}
```

**Response:**
```json
{
  "status": "success",
  "mission_status": "ACTIVE",
  "risk_level": "HIGH",
  "directives": ["INITIATE_VOICE_CALL", "ALERT_EMERGENCY_CONTACTS"]
}
```
*Note: If directives are returned, the Guardian AI will execute them autonomously on the backend. The frontend can optionally display an alert to the user (e.g., "Guardian is alerting your contacts").*

---

### 4. Check Mission Status
**GET** `/api/v3/guardian/mission/{mission_id}`

Retrieves the current state, risk level, and log of the active mission.

**Response:**
```json
{
  "mission_id": "msn_xxxxxxxx",
  "user_id": "string",
  "status": "ACTIVE",
  "risk_score": 60.0,
  "risk_level": "HIGH",
  "last_ping": "2024-05-20T10:00:00Z",
  "events": [
    {
      "timestamp": "2024-05-20T10:05:00Z",
      "type": "BEHAVIORAL_ANOMALY",
      "description": "Distress keyword detected.",
      "severity": "High Threat"
    }
  ]
}
```

---

## Autonomous Monitoring
Guardian AI ticks every 30 seconds independently of the frontend. If the user stops sending location updates or messages, the `monitoring_loop` will detect inactivity and autonomously escalate the risk. 

**Frontend Responsibilities:**
1. Call `/location` periodically while the app is in the foreground/background.
2. Ensure any user messages in the chat interface are forwarded to `/message`.
3. Optionally poll the mission status or listen to Realtime/WebSockets (if implemented) to reflect the `risk_level` in the UI (e.g., changing the shield icon color from green to red).
