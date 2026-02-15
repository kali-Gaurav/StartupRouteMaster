# Dockerfile for the Web Scraper Service

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install OS-level dependencies for Scrapy/lxml
# These might include build-essential, libxml2-dev, libxslt1-dev, zlib1g-dev, libpq-dev
# For now, let's keep it minimal and add as needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    libpq-dev \
  && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY scraper_service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY scraper_service /app

# Expose port for FastAPI (if it runs an API)
EXPOSE 8002

# Default command to run the FastAPI app (placeholder for now)
# CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
