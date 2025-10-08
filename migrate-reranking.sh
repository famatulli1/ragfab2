#!/bin/bash
set -e

# Script de migration manuel pour ajouter le toggle reranking
# À utiliser si tu as déjà une base de données PostgreSQL en production

echo "🚀 Migration du toggle reranking..."
echo ""
echo "Ce script va ajouter la colonne 'reranking_enabled' à la table conversations."
echo ""

# Vérifier que docker-compose est disponible
if ! command -v docker &> /dev/null; then
    echo "❌ Docker n'est pas installé ou n'est pas dans le PATH"
    exit 1
fi

# Vérifier que le conteneur PostgreSQL existe
if ! docker ps | grep -q ragfab-postgres; then
    echo "❌ Le conteneur ragfab-postgres n'est pas en cours d'exécution"
    echo "Démarrez-le avec: docker-compose up -d postgres"
    exit 1
fi

echo "✅ Conteneur PostgreSQL trouvé"
echo ""

# Exécuter la migration
echo "📝 Exécution de la migration..."
docker exec -i ragfab-postgres psql -U raguser -d ragdb <<-EOSQL
    -- Vérifier si la colonne existe déjà
    DO \$\$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name='conversations' AND column_name='reranking_enabled'
        ) THEN
            -- Ajouter la colonne
            ALTER TABLE conversations
            ADD COLUMN reranking_enabled BOOLEAN DEFAULT NULL;

            -- Ajouter un commentaire
            COMMENT ON COLUMN conversations.reranking_enabled IS
            'Contrôle le reranking pour cette conversation: NULL=global, TRUE=activé, FALSE=désactivé';

            -- Créer un index
            CREATE INDEX idx_conversations_reranking
            ON conversations(reranking_enabled)
            WHERE reranking_enabled IS NOT NULL;

            RAISE NOTICE '✅ Colonne reranking_enabled ajoutée avec succès !';
        ELSE
            RAISE NOTICE '✅ La colonne reranking_enabled existe déjà.';
        END IF;
    END
    \$\$;

    -- Afficher la structure de la table
    \d conversations
EOSQL

if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 Migration terminée avec succès !"
    echo ""
    echo "📊 Vérification de la colonne :"
    docker exec ragfab-postgres psql -U raguser -d ragdb -c \
        "SELECT column_name, data_type, is_nullable, column_default
         FROM information_schema.columns
         WHERE table_name='conversations' AND column_name='reranking_enabled';"
    echo ""
    echo "✅ Tu peux maintenant redémarrer l'API et utiliser le toggle reranking !"
else
    echo ""
    echo "❌ Erreur lors de la migration"
    exit 1
fi
