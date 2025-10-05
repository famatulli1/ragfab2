# Dockerfile pour le serveur d'embeddings
# Optimisé pour CPU uniquement

FROM python:3.11-slim

# Variables d'environnement
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    MODEL_NAME=intfloat/multilingual-e5-large

# Installer les dépendances système
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Créer un utilisateur non-root
RUN useradd -m -u 1000 embeddings && \
    mkdir -p /app /home/embeddings/.cache && \
    chown -R embeddings:embeddings /app /home/embeddings/.cache

WORKDIR /app

# Copier les dépendances
COPY --chown=embeddings:embeddings requirements.txt .

# Installer les dépendances Python (CPU-only torch)
RUN pip install --no-cache-dir torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# Copier le code de l'application
COPY --chown=embeddings:embeddings app.py .

# Passer à l'utilisateur non-root
USER embeddings

# Pré-télécharger le modèle au build (optionnel, commentez si vous préférez télécharger au runtime)
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${MODEL_NAME}')"

# Exposer le port
EXPOSE 8001

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Commande de démarrage
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
