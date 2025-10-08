# Service Reranker - Coolify

Service de reranking pour améliorer la pertinence des résultats RAG.

## Déploiement sur Coolify

### 1. Créer le service

Dans Coolify :
- **New Resource** → **Docker Compose**
- Nom : `ragfab-reranker`
- Repository : Ton repo GitHub/GitLab
- Docker Compose Location : `coolify/5-reranker/docker-compose.yml`

### 2. Variables d'environnement

Sur Coolify, configure :

```bash
RERANKER_MODEL=BAAI/bge-reranker-v2-m3
LOG_LEVEL=INFO
```

### 3. Ressources

Recommandé :
- **CPU** : 1-2 cores
- **RAM** : 3-4GB (minimum 2GB)
- **Stockage** : 5GB (pour le cache du modèle)

### 4. Vérification

Après déploiement, vérifie les logs :
```
INFO: Chargement du modèle BAAI/bge-reranker-v2-m3...
INFO: Modèle chargé en XX.XXs
INFO: Application startup complete
```

Test healthcheck :
```bash
curl http://ragfab-reranker:8002/health
# Devrait retourner: {"status": "healthy", "model": "BAAI/bge-reranker-v2-m3"}
```

## Connexion avec le backend

Le service backend doit avoir ces variables :

```bash
RERANKER_ENABLED=false  # Activé par défaut ou non
RERANKER_API_URL=http://ragfab-reranker:8002
RERANKER_TOP_K=20
RERANKER_RETURN_K=5
```

## Notes

- Le modèle est téléchargé au premier démarrage (~500MB)
- Le cache persiste entre redémarrages grâce au volume `model_cache`
- Pas de ports publics exposés, communication interne uniquement
- Utilisateur non-root pour la sécurité
