FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for Docling and ML libraries
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy worker requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy worker code
COPY worker.py .

# Create uploads directory
RUN mkdir -p /app/uploads

# The rag-app directory will be mounted as a volume
# so we can import ingestion modules
VOLUME ["/app/rag-app"]

# Run worker
CMD ["python", "-u", "worker.py"]
