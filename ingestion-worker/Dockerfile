FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for Docling and ML libraries
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy worker requirements and code
COPY ingestion-worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy rag-app code (needed for ingestion imports)
COPY rag-app /app/rag-app

# Copy worker code
COPY ingestion-worker/worker.py .

# Create uploads directory
RUN mkdir -p /app/uploads

# Run worker
CMD ["python", "-u", "worker.py"]
