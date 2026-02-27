# Minimal production Dockerfile for RouteMaster API
# - uses slim Python image
# - installs dependencies from backend/requirements.txt
# - runs the FastAPI app with uvicorn

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    POETRY_VIRTUALENVS_CREATE=false

WORKDIR /app

# Install OS-level deps required by some Python packages (kept minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
  && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt uvicorn

# Copy application code
COPY backend /app

EXPOSE 8000

# Use absolute path for uvicorn or ensure it's in PATH
CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
