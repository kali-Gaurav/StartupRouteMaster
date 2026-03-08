# RouteMaster Project Context

RouteMaster is a high-performance, resilient, and feature-rich railway routing and safety platform. It combines advanced graph-based routing algorithms (RAPTOR, Turbo) with machine learning for availability predictions and a comprehensive SOS/safety system.

## 🏗 Architecture Overview

The project is structured as a modern full-stack application with a distributed microservices-inspired backend.

- **Frontend:** A React (Vite) application using TypeScript, Tailwind CSS, and Radix UI. It integrates with Supabase for authentication and real-time features.
- **Backend:** A FastAPI-based gateway that orchestrates several internal services (Scraper, ETL, Route Service, RL Service, User Service, etc.).
- **Data Persistence:** Uses managed Supabase (PostgreSQL) for relational data and Auth, and Redis for high-speed caching and session management.
- **Messaging:** Apache Kafka is used as the backbone for event-driven processing (e.g., ETL and scraper tasks).
- **Observability:** Integrated with Prometheus, Grafana, Loki, and Promtail for monitoring and logging.

## 🚀 Key Technologies

### Frontend
- **Framework:** React 18 with Vite
- **Language:** TypeScript
- **Styling:** Tailwind CSS + Framer Motion (animations)
- **State/Data:** TanStack Query (React Query)
- **UI Components:** Radix UI primitives + Lucide icons
- **Backend-as-a-Service:** Supabase (Auth, Realtime, Database)

### Backend
- **Framework:** FastAPI
- **Language:** Python 3.11+
- **ORM:** SQLAlchemy with Alembic for migrations
- **Caching:** Redis (with multi-layer caching strategies)
- **Routing Engine:** Custom implementation featuring RAPTOR and Turbo routing algorithms.
- **ML:** Predictive availability and delay models.

### Infrastructure
- **Containerization:** Docker & Docker Compose
- **Orchestration:** Kubernetes (configs in `/k8s`)
- **CI/CD:** GitHub Actions
- **Deployment:** Railway (backend) and Vercel (frontend)

## 🛠 Commands & Development

### Backend
From the `/backend` directory:
- **Install Dependencies:** `pip install -r requirements.txt`
- **Run Migrations:** `alembic upgrade head`
- **Start Development Server:** `uvicorn app:app --reload`
- **Test:** `pytest`

### Frontend
From the `/frontend` directory:
- **Install Dependencies:** `npm install`
- **Start Development Server:** `npm run dev`
- **Build:** `npm run build`
- **Lint:** `npm run lint`

### Infrastructure (Docker)
From the root directory:
- **Start all services:** `docker-compose up -d`
- **Stop all services:** `docker-compose down`

## 📂 Directory Structure

- `/backend`: Core FastAPI application and services.
- `/frontend`: React frontend application.
- `/core`: Shared routing logic and ML models (within backend).
- `/database`: Database models and migration scripts.
- `/monitoring`: Prometheus, Grafana, and Loki configurations.
- `/k8s`: Kubernetes deployment manifests.
- `/doc`: Extensive project documentation and roadmaps.

## 📜 Development Conventions

- **Clean Code:** Adhere to PEP 8 for Python and ESLint/Prettier for TypeScript/React.
- **Migrations:** Never modify the database schema directly; always use Alembic migrations.
- **Security:** Do not commit `.env` files or secrets. Use the provided environment variable templates.
- **Safety First:** The SOS and safety features are mission-critical; ensure high test coverage for these modules.
