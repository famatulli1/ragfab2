FROM pgvector/pgvector:pg16

# Copier la configuration pg_hba.conf personnalisée avec trust pour Docker networks
COPY custom-pg_hba.conf /tmp/custom-pg_hba.conf

# Copier les schémas SQL
COPY schema.sql /docker-entrypoint-initdb.d/01_schema.sql
COPY 02_web_schema.sql /docker-entrypoint-initdb.d/02_web_schema.sql

# Copier le script d'initialisation intelligent
COPY init-db.sh /usr/local/bin/init-db.sh
RUN chmod +x /usr/local/bin/init-db.sh

# Créer un wrapper pour l'entrypoint qui exécute notre script après le démarrage de PostgreSQL
COPY docker-entrypoint-wrapper.sh /usr/local/bin/docker-entrypoint-wrapper.sh
RUN chmod +x /usr/local/bin/docker-entrypoint-wrapper.sh

# Utiliser notre wrapper comme entrypoint
ENTRYPOINT ["/usr/local/bin/docker-entrypoint-wrapper.sh"]
CMD ["postgres"]
