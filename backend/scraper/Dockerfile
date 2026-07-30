FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the scraper code
COPY . .

# Expose port for FastAPI
EXPOSE 8001

# Run the orchestrator
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]