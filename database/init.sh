#!/bin/bash
# Script d'initialisation de la base de données PostgreSQL avec PGVector

set -e

echo "🗄️  Initialisation de la base de données PostgreSQL..."

# Attendre que PostgreSQL soit prêt
until PGPASSWORD=$POSTGRES_PASSWORD psql -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c '\q'; do
  echo "⏳ En attente de PostgreSQL..."
  sleep 2
done

echo "✅ PostgreSQL est prêt"

# Exécuter le schéma SQL
echo "📋 Création des tables et fonctions..."
PGPASSWORD=$POSTGRES_PASSWORD psql -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /docker-entrypoint-initdb.d/schema.sql

echo "✅ Base de données initialisée avec succès"
echo "📊 Tables créées : documents, chunks"
echo "🔍 Fonction de recherche : match_chunks()"
