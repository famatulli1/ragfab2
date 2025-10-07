# ==========================================
# Dockerfile pour ragfab-postgres (Coolify)
# ==========================================
# Ce service expose PostgreSQL avec extension pgvector
# Communication: Reçoit des connexions du backend

FROM pgvector/pgvector:pg16

# Copier les schémas SQL d'initialisation
COPY database/schema.sql /docker-entrypoint-initdb.d/01_schema.sql
COPY database/02_web_schema.sql /docker-entrypoint-initdb.d/02_web_schema.sql

# Configuration PostgreSQL optimisée pour production
RUN echo "max_connections = 100" >> /usr/share/postgresql/postgresql.conf.sample && \
    echo "shared_buffers = 256MB" >> /usr/share/postgresql/postgresql.conf.sample && \
    echo "effective_cache_size = 1GB" >> /usr/share/postgresql/postgresql.conf.sample && \
    echo "maintenance_work_mem = 64MB" >> /usr/share/postgresql/postgresql.conf.sample && \
    echo "checkpoint_completion_target = 0.9" >> /usr/share/postgresql/postgresql.conf.sample && \
    echo "wal_buffers = 16MB" >> /usr/share/postgresql/postgresql.conf.sample && \
    echo "default_statistics_target = 100" >> /usr/share/postgresql/postgresql.conf.sample && \
    echo "random_page_cost = 1.1" >> /usr/share/postgresql/postgresql.conf.sample && \
    echo "effective_io_concurrency = 200" >> /usr/share/postgresql/postgresql.conf.sample && \
    echo "work_mem = 2621kB" >> /usr/share/postgresql/postgresql.conf.sample && \
    echo "min_wal_size = 1GB" >> /usr/share/postgresql/postgresql.conf.sample && \
    echo "max_wal_size = 4GB" >> /usr/share/postgresql/postgresql.conf.sample

# Exposer le port PostgreSQL
EXPOSE 5432

# Health check
HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
    CMD pg_isready -U ${POSTGRES_USER:-raguser} -d ${POSTGRES_DB:-ragdb} || exit 1

# Utiliser l'entrypoint par défaut de l'image pgvector
CMD ["postgres"]
