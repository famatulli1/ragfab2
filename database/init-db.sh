#!/bin/bash
set -e

# Script d'initialisation de la base de données PostgreSQL
# Vérifie et crée les tables manquantes automatiquement
# Compatible avec les déploiements Coolify (base existante)

echo "🔍 Vérification de l'état de la base de données..."

# Variables
POSTGRES_USER="${POSTGRES_USER:-raguser}"
POSTGRES_DB="${POSTGRES_DB:-ragdb}"

# Attendre que PostgreSQL soit prêt
until pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" > /dev/null 2>&1; do
  echo "⏳ En attente de PostgreSQL..."
  sleep 2
done

echo "✅ PostgreSQL est prêt"

# Fonction pour vérifier si une table existe
table_exists() {
  local table_name=$1
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc \
    "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name='$table_name');" | grep -q 't'
}

# Fonction pour vérifier si une vue existe
view_exists() {
  local view_name=$1
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc \
    "SELECT EXISTS (SELECT FROM information_schema.views WHERE table_name='$view_name');" | grep -q 't'
}

# Vérifier les tables principales (schema RAG)
echo ""
echo "📊 Vérification du schéma RAG..."

RAG_TABLES=("documents" "chunks")
RAG_MISSING=0

for table in "${RAG_TABLES[@]}"; do
  if table_exists "$table"; then
    echo "  ✅ Table '$table' existe"
  else
    echo "  ❌ Table '$table' manquante"
    RAG_MISSING=1
  fi
done

if [ $RAG_MISSING -eq 1 ]; then
  echo ""
  echo "🔧 Création du schéma RAG..."
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /docker-entrypoint-initdb.d/01_schema.sql
  echo "✅ Schéma RAG créé"
fi

# Vérifier les tables web
echo ""
echo "🌐 Vérification du schéma Web..."

WEB_TABLES=("users" "conversations" "messages" "message_ratings" "ingestion_jobs")
WEB_MISSING=0

for table in "${WEB_TABLES[@]}"; do
  if table_exists "$table"; then
    echo "  ✅ Table '$table' existe"
  else
    echo "  ❌ Table '$table' manquante"
    WEB_MISSING=1
  fi
done

# Vérifier les vues
WEB_VIEWS=("conversation_stats" "document_stats")
for view in "${WEB_VIEWS[@]}"; do
  if view_exists "$view"; then
    echo "  ✅ Vue '$view' existe"
  else
    echo "  ❌ Vue '$view' manquante"
    WEB_MISSING=1
  fi
done

if [ $WEB_MISSING -eq 1 ]; then
  echo ""
  echo "🔧 Création du schéma Web..."
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /docker-entrypoint-initdb.d/02_web_schema.sql
  echo "✅ Schéma Web créé"
fi

# Récapitulatif
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Base de données initialisée avec succès !"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📊 Tables disponibles :"
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\dt" | grep -E '(documents|chunks|users|conversations|messages|message_ratings|ingestion_jobs)' || echo "  (Aucune table trouvée)"
echo ""
echo "📈 Vues disponibles :"
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\dv" | grep -E '(conversation_stats|document_stats)' || echo "  (Aucune vue trouvée)"
echo ""
echo "🎉 Initialisation terminée"
