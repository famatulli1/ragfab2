FROM python:3.11-slim

# Variables d'environnement pour Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Créer un utilisateur non-root
RUN useradd -m -u 1000 reranker && \
    mkdir -p /app && \
    chown -R reranker:reranker /app

# Définir le répertoire de travail
WORKDIR /app

# Copier les requirements
COPY requirements.txt .

# Installer les dépendances
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code de l'application
COPY app.py .

# Changer l'utilisateur
USER reranker

# Exposer le port
EXPOSE 8002

# Commande de démarrage
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8002"]
