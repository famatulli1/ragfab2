# Dockerfile pour l'application RAG

FROM python:3.11-slim

# Variables d'environnement
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Installer les dépendances système
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Créer un utilisateur non-root
RUN useradd -m -u 1000 ragapp && \
    mkdir -p /app && \
    chown -R ragapp:ragapp /app

WORKDIR /app

# Copier les dépendances
COPY --chown=ragapp:ragapp requirements.txt .

# Installer les dépendances Python
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code de l'application
COPY --chown=ragapp:ragapp . .

# Passer à l'utilisateur non-root
USER ragapp

# Exposer le port (optionnel si API mode)
EXPOSE 8000

# Commande par défaut (CLI interactive)
CMD ["python", "rag_agent.py"]
