#!/bin/bash
set -e

# Script de migration automatique pour le reranking
# Ce script vérifie si la colonne existe déjà avant de l'ajouter

echo "🔍 Vérification de la migration reranking..."

# Vérifier si la colonne reranking_enabled existe
COLUMN_EXISTS=$(psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc \
  "SELECT COUNT(*) FROM information_schema.columns
   WHERE table_name='conversations' AND column_name='reranking_enabled';")

if [ "$COLUMN_EXISTS" -eq "0" ]; then
  echo "📝 Migration reranking : ajout de la colonne reranking_enabled..."

  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<-EOSQL
    -- Ajouter la colonne reranking_enabled
    ALTER TABLE conversations
    ADD COLUMN IF NOT EXISTS reranking_enabled BOOLEAN DEFAULT NULL;

    -- Ajouter un commentaire explicatif
    COMMENT ON COLUMN conversations.reranking_enabled IS
    'Contrôle le reranking pour cette conversation: NULL=global, TRUE=activé, FALSE=désactivé';

    -- Créer un index pour optimiser les requêtes
    CREATE INDEX IF NOT EXISTS idx_conversations_reranking
    ON conversations(reranking_enabled)
    WHERE reranking_enabled IS NOT NULL;
EOSQL

  echo "✅ Migration reranking terminée avec succès !"
else
  echo "✅ La colonne reranking_enabled existe déjà, aucune migration nécessaire."
fi

echo "🎉 Base de données prête pour le toggle reranking !"
