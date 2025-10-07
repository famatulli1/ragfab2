# ==========================================
# Dockerfile pour ragfab-backend (Coolify)
# ==========================================
# Ce service expose l'API FastAPI
# Communication:
#   - Reçoit des requêtes HTTPS du frontend
#   - Envoie des requêtes HTTPS vers embeddings et postgres

FROM python:3.11-slim

# Variables d'environnement Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Installer les dépendances système
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Créer utilisateur non-root
RUN useradd -m -u 1000 apiuser && \
    mkdir -p /app /app/uploads && \
    chown -R apiuser:apiuser /app

WORKDIR /app

# Copier les requirements du backend
COPY web-api/requirements.txt ./web-api-requirements.txt

# Copier les requirements de rag-app (pour importer les modules)
COPY rag-app/requirements.txt ./rag-app-requirements.txt

# Installer les dépendances Python
RUN pip install --no-cache-dir -r web-api-requirements.txt && \
    pip install --no-cache-dir -r rag-app-requirements.txt

# Copier le code du backend
COPY --chown=apiuser:apiuser web-api/ ./web-api/

# Copier le code de rag-app (nécessaire pour les imports)
COPY --chown=apiuser:apiuser rag-app/ ./rag-app/

# Changer vers l'utilisateur non-root
USER apiuser

# Exposer le port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Commande de démarrage (sans --reload en production)
CMD ["uvicorn", "web-api.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
