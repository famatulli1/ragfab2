# ==========================================
# Dockerfile pour ragfab-embeddings (Coolify)
# ==========================================
# Ce service expose l'API d'embeddings
# Communication: Reçoit des requêtes HTTPS du backend

FROM python:3.11-slim

# Variables d'environnement
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    MODEL_NAME=intfloat/multilingual-e5-large \
    TRANSFORMERS_CACHE=/home/embeddings/.cache/huggingface

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
COPY embeddings-server/requirements.txt .

# Installer les dépendances Python (CPU-only torch pour réduire la taille)
RUN pip install --no-cache-dir torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# Copier le code de l'application
COPY --chown=embeddings:embeddings embeddings-server/app.py .

# Passer à l'utilisateur non-root
USER embeddings

# Pré-télécharger le modèle au build (optionnel mais recommandé)
# Commentez cette ligne si vous préférez télécharger au runtime
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-large')"

# Exposer le port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Commande de démarrage
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
