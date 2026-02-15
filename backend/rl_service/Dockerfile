FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --retries 10 --timeout 300 -r requirements.txt

COPY . .

EXPOSE 8003

CMD ["python", "app.py"]