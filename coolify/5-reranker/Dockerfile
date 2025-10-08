# Dockerfile pour le service de reranking
FROM python:3.11-slim

# Créer un utilisateur non-root
RUN useradd -m -u 1000 reranker

# Installer curl pour healthcheck
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Répertoire de travail
WORKDIR /app

# Copier les fichiers du reranker
COPY reranker-server/requirements.txt .
COPY reranker-server/app.py .

# Installer les dépendances
RUN pip install --no-cache-dir -r requirements.txt

# Créer le répertoire de cache
RUN mkdir -p /home/reranker/.cache && \
    chown -R reranker:reranker /home/reranker/.cache

# Changer le propriétaire du répertoire de travail
RUN chown -R reranker:reranker /app

# Basculer vers l'utilisateur non-root
USER reranker

# Exposer le port
EXPOSE 8002

# Commande de démarrage
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8002"]
