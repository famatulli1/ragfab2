#!/bin/bash
set -e

# Wrapper pour l'entrypoint PostgreSQL
# Lance PostgreSQL en arrière-plan, exécute init-db.sh, puis passe en foreground

echo "🚀 Démarrage de PostgreSQL avec initialisation automatique..."

# Lancer l'entrypoint original de PostgreSQL en arrière-plan
/usr/local/bin/docker-entrypoint.sh "$@" &
POSTGRES_PID=$!

# Attendre que PostgreSQL soit prêt
echo "⏳ Attente du démarrage de PostgreSQL..."
until pg_isready -U "${POSTGRES_USER:-raguser}" -d "${POSTGRES_DB:-ragdb}" > /dev/null 2>&1; do
  sleep 1
done

echo "✅ PostgreSQL démarré, lancement de l'initialisation..."

# Copier notre pg_hba.conf personnalisé
if [ -f "/tmp/custom-pg_hba.conf" ]; then
  echo "📝 Installation de pg_hba.conf personnalisé..."
  cp /tmp/custom-pg_hba.conf /var/lib/postgresql/data/pg_hba.conf
  psql -U "${POSTGRES_USER:-raguser}" -d "${POSTGRES_DB:-ragdb}" -c "SELECT pg_reload_conf();" > /dev/null 2>&1
  echo "✅ pg_hba.conf appliqué (trust pour réseaux Docker)"
fi

# Exécuter le script d'initialisation
/usr/local/bin/init-db.sh

# Passer PostgreSQL en foreground
echo "🎉 Initialisation terminée, PostgreSQL opérationnel"
wait $POSTGRES_PID
