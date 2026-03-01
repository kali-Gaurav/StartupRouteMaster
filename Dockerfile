FROM python:3.11-slim

# 1. Install system dependencies (gcc is needed for some python packages)
RUN apt-get update && apt-get install -y 
    gcc 
    python3-dev 
    libpq-dev 
    curl 
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. Copy requirements and install
# We copy it from the backend folder to the root of the container
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && 
    pip install --no-cache-dir -r requirements.txt

# 3. Copy only the Backend and necessary root assets (ML Models)
COPY backend/ ./backend/
COPY *.pkl ./
COPY *.json ./

# 4. Set environment variables
ENV PYTHONPATH=/app/backend
ENV PYTHONUNBUFFERED=1

# 5. Expose the port Railway expects
EXPOSE 8000

# 6. Start the app using the verified production command
# We use shell form to ensure $PORT is evaluated
CMD cd backend && uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers
