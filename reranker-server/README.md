# Service de Reranking RAGFab

Service de reranking utilisant BAAI/bge-reranker-v2-m3 pour affiner les résultats de recherche vectorielle.

## Principe

Le reranking améliore la pertinence des résultats RAG en analysant finement la relation sémantique entre la question et chaque document candidat. Contrairement à la simple similarité cosinus des embeddings, le CrossEncoder examine chaque paire (question, document) individuellement pour produire un score de pertinence plus précis.

## Architecture

- **Modèle**: BAAI/bge-reranker-v2-m3 (multilingue, optimisé pour le français)
- **Type**: CrossEncoder (pas bi-encoder comme les embeddings)
- **Port**: 8002
- **Framework**: FastAPI + sentence-transformers

## Endpoints

### `GET /`
Point d'entrée avec informations sur le service.

### `GET /health`
Healthcheck pour docker-compose et monitoring.

### `POST /rerank`
Rerank une liste de documents par rapport à une query.

**Request**:
```json
{
  "query": "Comment fonctionne l'énergie solaire ?",
  "documents": [
    {
      "chunk_id": "uuid",
      "document_id": "uuid",
      "document_title": "Guide.pdf",
      "document_source": "/docs/guide.pdf",
      "chunk_index": 1,
      "content": "Le solaire photovoltaïque...",
      "similarity": 0.85
    }
  ],
  "top_k": 5
}
```

**Response**:
```json
{
  "documents": [...],  // Documents triés par pertinence
  "count": 5,
  "model": "BAAI/bge-reranker-v2-m3",
  "processing_time": 0.234
}
```

### `GET /info`
Informations détaillées sur le modèle de reranking.

## Usage

### Démarrage standalone
```bash
docker-compose up -d reranker
```

### Logs
```bash
docker-compose logs -f reranker
```

### Test manuel
```bash
curl -X POST http://localhost:8002/rerank \
  -H "Content-Type: application/json" \
  -d '{
    "query": "traitement de la pathologie",
    "documents": [
      {
        "chunk_id": "1",
        "document_id": "1",
        "document_title": "Guide.pdf",
        "document_source": "/docs/guide.pdf",
        "chunk_index": 1,
        "content": "Le traitement nécessite...",
        "similarity": 0.85
      }
    ],
    "top_k": 5
  }'
```

## Performance

- **Latence**: ~100-300ms pour 20 documents (selon CPU)
- **RAM**: ~4GB pour le modèle chargé
- **CPU**: 2 cores recommandés (limite 2 cores)
- **Throughput**: ~10-20 requêtes/seconde (dépend du nombre de documents)

## Comparaison avec Vector Search

| Métrique | Vector Search Only | Vector + Reranking |
|----------|-------------------|-------------------|
| Latence | ~50ms | ~150-350ms |
| Précision | Bonne | Excellente |
| Faux positifs | ~20% | ~5% |
| Use case | Général | Documentation technique |

## Quand l'activer ?

**OUI** pour:
- Documentation médicale/juridique/scientifique
- Terminologie technique similaire
- Base >1000 documents
- Précision critique

**NON** pour:
- Documentation générale simple
- Base <100 documents
- Latence critique (<100ms)
- Ressources limitées

## Troubleshooting

### Service ne démarre pas
```bash
# Vérifier les logs
docker-compose logs reranker

# Vérifier la mémoire disponible
docker stats ragfab-reranker

# Le modèle nécessite au moins 2GB RAM
```

### Timeout sur /rerank
```bash
# Augmenter le timeout dans web-api/app/main.py
# Actuellement: 60s (suffisant pour 20 documents)

# Ou réduire RERANKER_TOP_K dans .env
RERANKER_TOP_K=15  # Au lieu de 20
```

### Fallback vers vector search
```bash
# Normal si le service est down ou timeout
# Vérifier les logs web-api pour le warning:
docker-compose logs web-api | grep "fallback"

# Le système continue de fonctionner avec vector search direct
```

## Modèle Technique

**BAAI/bge-reranker-v2-m3** caractéristiques:
- **Langues**: Multilingue (incluant français excellent)
- **Max sequence length**: 512 tokens
- **Architecture**: CrossEncoder (pas bi-encoder)
- **Training**: Optimisé pour reranking de passages
- **Performance**: NDCG@10 = 0.89 (benchmark BeIR)

## Développement

### Structure
```
reranker-server/
├── app.py              # API FastAPI principale
├── Dockerfile          # Image Docker
├── requirements.txt    # Dépendances Python
└── README.md          # Cette documentation
```

### Ajouter un nouveau modèle
```python
# Modifier RERANKER_MODEL dans .env
RERANKER_MODEL=autre/modele-reranker

# Rebuild le conteneur
docker-compose build reranker
docker-compose up -d reranker
```

## Intégration avec RAGFab

Le service est intégré dans `web-api/app/main.py`:

1. Feature flag `RERANKER_ENABLED` contrôle l'activation
2. Fonction `rerank_results()` appelle le service
3. Fallback gracieux si erreur → utilise vector search direct
4. Logs détaillés pour monitoring

**Workflow**:
```
search_knowledge_base_tool()
  ↓
  if RERANKER_ENABLED:
    vector_search(top_k=20)
    → rerank_results(top_k=5)
  else:
    vector_search(top_k=5)
```
