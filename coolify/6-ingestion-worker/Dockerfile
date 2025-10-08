# Dockerfile pour Ingestion Worker - Coolify
# Build depuis la racine du projet avec contexte sur ingestion-worker/

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies pour Docling et ML
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy worker code et requirements
COPY ingestion-worker/requirements.txt /app/
COPY ingestion-worker/worker.py /app/

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy rag-app pour imports des modules d'ingestion
COPY rag-app /app/rag-app

# Create uploads directory
RUN mkdir -p /app/uploads

# Run worker
CMD ["python", "-u", "worker.py"]
