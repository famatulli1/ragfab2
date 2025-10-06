FROM pgvector/pgvector:pg16

# Copier les schémas SQL dans le dossier d'init
# Les scripts sont exécutés par ordre alphabétique au premier démarrage
COPY schema.sql /docker-entrypoint-initdb.d/01_schema.sql
COPY 02_web_schema.sql /docker-entrypoint-initdb.d/02_web_schema.sql
