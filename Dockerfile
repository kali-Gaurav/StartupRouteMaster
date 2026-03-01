FROM python:3.11-slim

# Install system dependencies in one solid line
RUN apt-get update && apt-get install -y gcc python3-dev libpq-dev curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy ONLY backend requirements first for caching
COPY backend/requirements.txt .

# Install using 'python -m pip' - this is the most reliable way to avoid 'command not found'
RUN python -m pip install --no-cache-dir --upgrade pip
RUN python -m pip install --no-cache-dir -r requirements.txt

# Copy ONLY the backend folder and ML models
COPY backend/ ./backend/
COPY *.pkl ./
COPY *.json ./

# Setup environment
ENV PYTHONPATH=/app/backend
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Final check to ensure uvicorn is installed and in path
RUN python -m uvicorn --version

# Start from the backend directory
WORKDIR /app/backend
CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
