FROM pgvector/pgvector:pg16

# Copier le schéma SQL dans le dossier d'init
COPY schema.sql /docker-entrypoint-initdb.d/

# Le script sera exécuté automatiquement au premier démarrage
