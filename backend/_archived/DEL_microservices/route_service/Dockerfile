
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y build-essential libpq-dev && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Route Service needs core logic from backend
COPY core ./core
COPY database ./database
COPY utils ./utils
COPY services ./services

COPY microservices/shared ./shared
COPY microservices/route_service/ .
ENV PYTHONPATH=/app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
