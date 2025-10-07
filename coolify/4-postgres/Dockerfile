# Dockerfile pour PostgreSQL avec script d'initialisation intégré
FROM pgvector/pgvector:pg16

# Copier le script d'initialisation dans l'image
COPY coolify/4-postgres/init-db.sql /docker-entrypoint-initdb.d/01-init.sql

# Donner les bonnes permissions
RUN chmod 644 /docker-entrypoint-initdb.d/01-init.sql
