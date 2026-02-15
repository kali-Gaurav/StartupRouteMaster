FROM python:3.11-slim

WORKDIR /app

# system deps for playwright
RUN apt-get update && apt-get install -y wget ca-certificates libnss3 libatk1.0-0 libatk-bridge2.0-0 libx11-6 libxss1 libasound2 libxcomposite1 libxrandr2 libgbm1 libgtk-3-0 libdrm2 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# copy app
COPY . .

# install playwright browsers
RUN playwright install chromium || true

EXPOSE 8008
CMD ["uvicorn", "routemaster_agent.main:app", "--host", "0.0.0.0", "--port", "8008"]