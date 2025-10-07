#!/bin/bash
set -e

echo "🗄️  Script d'initialisation PostgreSQL pour RAGFab"
echo "=================================================="
echo ""

# Trouver le container PostgreSQL
POSTGRES_CONTAINER=$(docker ps -a | grep -i postgres | grep -i pgvector | awk '{print $1}')

if [ -z "$POSTGRES_CONTAINER" ]; then
    echo "❌ Aucun container PostgreSQL trouvé"
    echo "Veuillez déployer PostgreSQL dans Coolify d'abord"
    exit 1
fi

echo "✅ Container PostgreSQL trouvé: $POSTGRES_CONTAINER"
echo ""

# Arrêter le container
echo "🛑 Arrêt du container PostgreSQL..."
docker stop $POSTGRES_CONTAINER

# Trouver et supprimer le volume
echo "🗑️  Recherche du volume de données..."
VOLUME=$(docker volume ls | grep postgres | awk '{print $2}')

if [ -n "$VOLUME" ]; then
    echo "🗑️  Suppression du volume: $VOLUME"
    docker volume rm $VOLUME
else
    echo "⚠️  Aucun volume PostgreSQL trouvé"
fi

# Supprimer le container
echo "🗑️  Suppression du container..."
docker rm $POSTGRES_CONTAINER

echo ""
echo "✅ Nettoyage terminé !"
echo ""
echo "📋 Prochaines étapes dans Coolify :"
echo "1. Va dans l'application PostgreSQL"
echo "2. Section 'Storages' → Supprime tous les anciens montages"
echo "3. Clique sur 'Redeploy'"
echo "4. PostgreSQL va redémarrer avec une base vide"
echo "5. Le script init-db.sql sera exécuté automatiquement"
echo ""
echo "⏳ Attends que PostgreSQL affiche dans les logs :"
echo "   '✅ Base de données RAGFab initialisée avec succès !'"
echo ""
echo "Ensuite, redémarre le backend pour qu'il se connecte à la nouvelle base."
