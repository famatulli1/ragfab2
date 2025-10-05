FROM python:3.11-slim

# Installer les dépendances système
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Créer utilisateur non-root
RUN useradd -m -u 1000 apiuser && \
    mkdir -p /app && \
    chown -R apiuser:apiuser /app

WORKDIR /app

# Copier les requirements
COPY --chown=apiuser:apiuser requirements.txt .

# Installer les dépendances Python
RUN pip install --no-cache-dir -r requirements.txt

# Copier l'application
COPY --chown=apiuser:apiuser . .

# Changer vers l'utilisateur non-root
USER apiuser

# Exposer le port
EXPOSE 8000

# Commande de démarrage
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
