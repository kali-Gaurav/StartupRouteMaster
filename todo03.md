Perfect 👍 — now we are designing the core production backbone of your system.

Below is a complete engineering blueprint covering:

1️⃣ Booking Queue Database Schema
2️⃣ IRCTC Automation Architecture
3️⃣ Admin / Developer Dashboard Design
4️⃣ Complete Test Pipeline Scripts (Backend + Frontend + E2E + Load)

This is written at startup / enterprise deployment level so you can directly implement.

🚆 1. Booking Queue Database Schema

Your booking system is not direct booking.

It is a request-based execution pipeline.

Flow:

User confirms booking
        ↓
Booking Request Created
        ↓
Payment Verified (₹39 unlock)
        ↓
Queue Entry Created
        ↓
Admin / Automation executes
        ↓
Success / Failure
        ↓
Refund if failure
Core Tables Overview
users
booking_requests
booking_queue
passengers
payment_transactions
booking_results
refunds
execution_logs
✅ booking_requests Table

Stores user intent.

CREATE TABLE booking_requests (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),

    source_station VARCHAR(20),
    destination_station VARCHAR(20),
    journey_date DATE,

    train_number VARCHAR(20),
    train_name VARCHAR(100),

    class_type VARCHAR(10),
    quota VARCHAR(10),

    status VARCHAR(20) DEFAULT 'PENDING',

    verification_status VARCHAR(20) DEFAULT 'NOT_VERIFIED',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

Status values:

PENDING
VERIFIED
QUEUED
PROCESSING
SUCCESS
FAILED
CANCELLED
REFUNDED
✅ passengers Table

Passenger details per request.

CREATE TABLE passengers (
    id UUID PRIMARY KEY,
    booking_request_id UUID REFERENCES booking_requests(id),

    name VARCHAR(100),
    age INT,
    gender VARCHAR(10),

    berth_preference VARCHAR(20),

    id_proof_type VARCHAR(20),
    id_proof_number VARCHAR(50)
);
✅ payment_transactions Table

₹39 unlock payment.

CREATE TABLE payment_transactions (
    id UUID PRIMARY KEY,
    booking_request_id UUID REFERENCES booking_requests(id),

    amount DECIMAL(10,2),
    currency VARCHAR(10) DEFAULT 'INR',

    payment_gateway VARCHAR(50),
    transaction_id VARCHAR(100),

    status VARCHAR(20),

    created_at TIMESTAMP
);

Status:

INITIATED
SUCCESS
FAILED
REFUNDED
✅ booking_queue Table

Queue for execution.

CREATE TABLE booking_queue (
    id UUID PRIMARY KEY,
    booking_request_id UUID REFERENCES booking_requests(id),

    priority INT DEFAULT 5,
    execution_mode VARCHAR(20), -- AUTO / MANUAL

    status VARCHAR(20) DEFAULT 'WAITING',

    scheduled_time TIMESTAMP,

    created_at TIMESTAMP
);

Status:

WAITING
RUNNING
DONE
FAILED
CANCELLED
✅ booking_results Table

Ticket outcome.

CREATE TABLE booking_results (
    id UUID PRIMARY KEY,
    booking_request_id UUID REFERENCES booking_requests(id),

    pnr_number VARCHAR(20),
    ticket_status VARCHAR(50),

    coach_details TEXT,
    seat_details TEXT,

    irctc_transaction_id VARCHAR(100),

    created_at TIMESTAMP
);
✅ refunds Table

Refund management.

CREATE TABLE refunds (
    id UUID PRIMARY KEY,
    booking_request_id UUID REFERENCES booking_requests(id),

    amount DECIMAL(10,2),
    reason TEXT,

    status VARCHAR(20),

    created_at TIMESTAMP
);
✅ execution_logs Table

Critical for debugging.

CREATE TABLE execution_logs (
    id UUID PRIMARY KEY,

    booking_request_id UUID REFERENCES booking_requests(id),

    step VARCHAR(100),
    message TEXT,

    status VARCHAR(20),

    created_at TIMESTAMP
);
🤖 2. IRCTC Automation Architecture

Important:

You are NOT replacing IRCTC.

You are automating interaction.

Architecture:

RouteMaster Backend
        ↓
Automation Engine
        ↓
IRCTC Website / API
Automation Modes
Mode 1 — Manual Execution

Admin performs booking.

Safe for MVP.

Mode 2 — Semi-Automatic

System fills forms → Admin confirms.

Mode 3 — Fully Automatic Bot

Future stage.

Automation Engine Components
automation/
    irctc_client.py
    session_manager.py
    captcha_solver.py
    booking_executor.py
    result_parser.py
Execution Pipeline
1. Login IRCTC
2. Search train
3. Select passengers
4. Fill details
5. Payment redirect
6. Confirmation capture
7. Store PNR
Technologies

Recommended:

Playwright (best)

Selenium (fallback)

Playwright advantages:

Fast

Headless

Reliable

CAPTCHA support plugins

Risk Areas

You must handle:

CAPTCHA

Session expiry

Payment redirect failures

IRCTC downtime

Bot detection

🖥 3. Admin / Developer Dashboard Design

This is the control center of your system.

Dashboard Modules
1. Booking Queue Panel

Shows:

Pending requests

Priority

Execution mode

User info

Train info

Actions:

Execute

Cancel

Mark failed

2. Booking Execution Panel

Real-time automation view.

Logs like:

Login success
Train selected
Passenger submitted
Payment done
PNR generated
3. Payment Monitor

Shows:

₹39 payments

Failed payments

Refund status

4. System Health

API status:

RapidAPI

IRCTC

Database

WebSocket

5. User Management

Admin can:

View users

Block users

Refund manually

6. Analytics

Metrics:

Total bookings

Success rate

Failure rate

Revenue

API usage

Recommended Tech

Frontend:

React Admin Panel

Chart.js / Recharts

Backend:

Admin APIs with RBAC

🧪 4. Complete Test Pipeline Scripts

You need 4 layers.

✅ Layer 1 — Backend Unit Tests (pytest)

Example:

def test_create_booking_request(client):
    response = client.post("/booking/create", json={
        "train_number": "12627",
        "date": "2026-03-01"
    })
    assert response.status_code == 200

Run:

pytest
✅ Layer 2 — Integration Tests

Test:

RapidAPI call

DB write

Queue creation

Example:

def test_queue_pipeline():
    req = create_booking()
    verify_payment(req)
    queue = add_to_queue(req)

    assert queue.status == "WAITING"
✅ Layer 3 — End-to-End Tests (Playwright)

Simulate real user.

npx playwright test

Example flow:

Login
Search route
Unlock
Payment
Booking request
Dashboard view
✅ Layer 4 — Load Testing (Locust)

Simulate 100 users.

locust -f locustfile.py

Test:

Search load

WebSocket load

Queue load

🔧 CI/CD Pipeline Example (GitHub Actions)
name: Deploy

on: [push]

jobs:

  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - run: pip install -r requirements.txt
      - run: pytest

  frontend:
    runs-on: ubuntu-latest
    steps:
      - run: npm ci
      - run: npm run build

  docker:
    runs-on: ubuntu-latest
    steps:
      - run: docker build .
🔥 5. Recommended System Architecture (Final)
Frontend (React)
        ↓
Backend API (FastAPI)
        ↓
Service Layer
        ↓
Queue Manager
        ↓
Automation Engine
        ↓
IRCTC

Supporting:

PostgreSQL

Redis

WebSocket server

RapidAPI providers

⭐ 6. Deployment Phases Strategy
Phase 1 — MVP

Manual booking execution

Queue works

Payment works

Phase 2 — Semi Automation

Autofill IRCTC

Admin confirm

Phase 3 — Full Automation

Bot booking

✅ 7. Most Important Advice

Your biggest success factor:

Reliable queue + execution logs

Not UI.

Not AI.

Not chatbot.