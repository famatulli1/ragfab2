#!/bin/bash
# Script de test pour valider le système de reranking

set -e

echo "🧪 Test du Système de Reranking RAGFab"
echo "======================================"
echo ""

# Couleurs pour l'output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
RERANKER_URL="http://localhost:8002"
API_URL="http://localhost:8000"

echo "📋 Étape 1: Vérification des services"
echo "--------------------------------------"

# Test healthcheck reranker
echo -n "Reranker service... "
if curl -s -f "${RERANKER_URL}/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ UP${NC}"
else
    echo -e "${RED}✗ DOWN${NC}"
    echo "Démarrer avec: docker-compose up -d reranker"
    exit 1
fi

# Test healthcheck API
echo -n "API service... "
if curl -s -f "${API_URL}/api/docs" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ UP${NC}"
else
    echo -e "${RED}✗ DOWN${NC}"
    echo "Démarrer avec: docker-compose up -d ragfab-api"
    exit 1
fi

echo ""
echo "📊 Étape 2: Test du service reranker isolé"
echo "-------------------------------------------"

# Test simple de reranking
RERANK_PAYLOAD='{
  "query": "traitement de l'\''hypertension artérielle",
  "documents": [
    {
      "chunk_id": "1",
      "document_id": "doc1",
      "document_title": "Guide_Cardiologie.pdf",
      "document_source": "/docs/cardio.pdf",
      "chunk_index": 1,
      "content": "Le traitement de l'\''hypertension artérielle nécessite une approche progressive. Les médicaments de première ligne incluent les IEC, les ARA2, les diurétiques thiazidiques et les inhibiteurs calciques.",
      "similarity": 0.92
    },
    {
      "chunk_id": "2",
      "document_id": "doc1",
      "document_title": "Guide_Cardiologie.pdf",
      "document_source": "/docs/cardio.pdf",
      "chunk_index": 5,
      "content": "L'\''hypertension artérielle est définie par une pression systolique supérieure à 140 mmHg ou une pression diastolique supérieure à 90 mmHg. Elle constitue un facteur de risque majeur.",
      "similarity": 0.88
    },
    {
      "chunk_id": "3",
      "document_id": "doc2",
      "document_title": "Guide_Neurologie.pdf",
      "document_source": "/docs/neuro.pdf",
      "chunk_index": 12,
      "content": "Les accidents vasculaires cérébraux peuvent être prévenus par un bon contrôle de la pression artérielle. La prévention primaire est essentielle.",
      "similarity": 0.85
    }
  ],
  "top_k": 3
}'

echo -n "Test de reranking... "
RERANK_RESPONSE=$(curl -s -X POST "${RERANKER_URL}/rerank" \
  -H "Content-Type: application/json" \
  -d "$RERANK_PAYLOAD")

if echo "$RERANK_RESPONSE" | grep -q '"count": 3'; then
    echo -e "${GREEN}✓ OK${NC}"

    # Afficher les détails
    PROCESSING_TIME=$(echo "$RERANK_RESPONSE" | grep -o '"processing_time": [0-9.]*' | cut -d' ' -f2)
    echo "  └─ Temps de traitement: ${PROCESSING_TIME}s"

    # Vérifier que l'ordre est bon (chunk 1 devrait être premier car plus pertinent pour le traitement)
    FIRST_CHUNK=$(echo "$RERANK_RESPONSE" | grep -o '"chunk_id": "[^"]*"' | head -1 | cut -d'"' -f4)
    if [ "$FIRST_CHUNK" = "1" ]; then
        echo -e "  └─ Ordre de pertinence: ${GREEN}✓ Correct${NC}"
    else
        echo -e "  └─ Ordre de pertinence: ${YELLOW}⚠ Inattendu (chunk $FIRST_CHUNK en premier)${NC}"
    fi
else
    echo -e "${RED}✗ ÉCHEC${NC}"
    echo "Réponse: $RERANK_RESPONSE"
    exit 1
fi

echo ""
echo "🔧 Étape 3: Vérification de la configuration"
echo "---------------------------------------------"

# Vérifier les variables d'environnement
echo "Variables d'environnement dans ragfab-api:"
docker-compose exec -T ragfab-api env | grep RERANKER || echo -e "${YELLOW}⚠ Variables RERANKER non définies${NC}"

echo ""
echo "📈 Étape 4: Test d'intégration (optionnel)"
echo "-------------------------------------------"

if [ -f ".env" ] && grep -q "RERANKER_ENABLED=true" .env; then
    echo -e "RERANKER_ENABLED=true détecté dans .env: ${GREEN}✓${NC}"
    echo ""
    echo "Pour tester l'intégration complète:"
    echo "1. Ouvrir le frontend: http://localhost:3000"
    echo "2. Poser une question technique"
    echo "3. Observer les logs:"
    echo "   docker-compose logs -f ragfab-api | grep -E '(Reranking|rerank)'"
    echo ""
    echo "Logs attendus:"
    echo "  - 🔄 Reranking activé: recherche de XX candidats"
    echo "  - 🎯 Application du reranking sur XX candidats"
    echo "  - ✅ Reranking effectué en X.XXXs, X documents retournés"
else
    echo -e "RERANKER_ENABLED=false ou non défini: ${YELLOW}⚠${NC}"
    echo ""
    echo "Pour activer le reranking:"
    echo "1. Dans .env, définir: RERANKER_ENABLED=true"
    echo "2. Redémarrer: docker-compose restart ragfab-api"
    echo "3. Relancer ce script pour vérifier"
fi

echo ""
echo "✅ Tests terminés avec succès!"
echo ""
echo "📚 Ressources:"
echo "  - Guide complet: RERANKING_GUIDE.md"
echo "  - Documentation technique: reranker-server/README.md"
echo "  - Configuration: CLAUDE.md (section Reranking)"
