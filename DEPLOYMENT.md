# 🚀 RouteMaster Full Deployment Guide

This guide covers the end-to-end production deployment of RouteMaster using **Railway**, **Supabase**, and **Upstash Redis**.

## 🏗️ Production Stack
- **Frontend**: Vercel (React/Vite)
- **Backend**: Railway (FastAPI)
- **Database**: Supabase (PostgreSQL)
- **Cache**: Upstash (Redis)

---

## 🛰️ Step 1: Database & Cache Setup

### 1. Supabase (Database & Auth)
1. Create a new project at [supabase.com](https://supabase.com).
2. Go to **Project Settings > API** to get your `SUPABASE_URL` and `SUPABASE_ANON_KEY`.
3. Go to **Project Settings > Database** to get your Connection String (`DATABASE_URL`).
4. (Optional) Run the SQL migrations found in `backend/alembic/` or use the provided `.sql` files to setup the schema if not using automatic initialization.

### 2. Upstash (Redis)
1. Create a Redis database at [upstash.com](https://upstash.com).
2. Copy the **Redis URL** (should start with `rediss://...`).

---

## 🛠️ Step 2: Deploy Backend to Railway

### 1. Preparation
Ensure your `backend/` directory contains all necessary files including the `Dockerfile`.

### 2. Deployment
1. Log in to [Railway.app](https://railway.app).
2. Click **New Project > Deploy from GitHub repo**.
3. Select your repository.
4. Railway will detect the `backend/Dockerfile` automatically. Set the **Root Directory** to `backend` in the service settings.

### 3. Environment Variables
Add the following variables in the Railway dashboard:
- `ENVIRONMENT`: `production`
- `DATABASE_URL`: Your Supabase Postgres URL (Connection String)
- `SUPABASE_URL`: Your Supabase Project URL
- `SUPABASE_KEY`: Your Supabase **Anon Key**
- `SUPABASE_SERVICE_KEY`: Your Supabase **Service Role Key** (for backend admin tasks)
- `REDIS_URL`: Your Upstash Redis URL
- `PORT`: `8000` (Railway provides this automatically)
- `LOG_LEVEL`: `INFO`
- `JWT_SECRET_KEY`: A long random string for auth security

### 4. 🧠 Memory Requirement (CRITICAL)
The routing engine loads a graph snapshot into RAM.
- **Go to Settings > Plan > Resource Limits**.
- **Requirement**: Minimum **2 GB RAM**. 
- *Note*: If memory is < 2GB, the process may be killed during graph initialization.

---

## 🎨 Step 3: Deploy Frontend to Vercel

1. Log in to [Vercel.com](https://vercel.com).
2. Click **Add New > Project** and select your repo.
3. **Framework Preset**: Vite.
4. **Environment Variables**:
   - `RAILWAY_BACKEND_URL`: Your Railway backend URL (e.g., `https://backend-production.up.railway.app`)
5. Click **Deploy**.

---

## 🏆 Final Production Flow
```
User → React (Vercel) → FastAPI (Railway)
                          ↓
                    Redis Cache (Upstash)
                          ↓
                    Memory Graph (RAM)
                          ↓
                    RAPTOR Engine (Algorithm)
                          ↓
                    JSON Response
```

### Latency Targets
- **Cache Hit**: 10–30 ms
- **Cache Miss (RAPTOR)**: 50–150 ms
- **UI Interaction**: Fluid < 200 ms

---

## ⭐ Bonus: Post-Deployment Improvements

### 1. Monitoring
The backend is already equipped with **Prometheus** instrumentation.
- Access `/metrics` on your backend URL to see raw data.
- Connect a Grafana dashboard to Railway for professional monitoring.

### 2. Request Coalescing
Already implemented in `SearchService`. This prevents "Search Storms" where multiple users querying the same route simultaneously would trigger redundant RAPTOR runs.

### 3. Graph Warmup
The `route_engine.initialize()` method runs on startup to pre-calculate hub tables and load segments, ensuring the first user query is just as fast as the 1000th.

---
**RouteMaster** — *Safety & Intelligence in Every Journey.*
