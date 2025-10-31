FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY analytics-worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy worker code
COPY analytics-worker/worker.py .

# Run worker
CMD ["python", "-u", "worker.py"]
