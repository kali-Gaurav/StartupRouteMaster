
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (for numpy, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the shared library
COPY microservices/shared ./shared

# Copy the specific service code (passed via build arg)
ARG SERVICE_DIR
COPY microservices/${SERVICE_DIR}/ .

# Ensure shared is in PYTHONPATH
ENV PYTHONPATH=/app

# Command will be overridden in docker-compose or specific Dockerfiles
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
