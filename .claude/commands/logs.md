# Commande /logs - Consultation des Logs RAGFab

Tu es un expert en debugging. Aide l'utilisateur à consulter et analyser les logs.

## Logs par Service

### 1. Tous les Services

```bash
docker-compose logs -f --tail 100
```

### 2. Service Spécifique

```bash
# API Backend
docker-compose logs -f ragfab-api

# Worker Ingestion
docker-compose logs -f ingestion-worker

# Frontend
docker-compose logs -f ragfab-frontend

# Base de données
docker-compose logs -f postgres

# Embeddings
docker-compose logs -f embeddings

# Reranker
docker-compose logs -f reranker
```

### 3. Filtrer les Erreurs

```bash
# Erreurs dans tous services
docker-compose logs 2>&1 | grep -i error

# Erreurs API uniquement
docker-compose logs ragfab-api 2>&1 | grep -i error

# Warnings
docker-compose logs ragfab-api 2>&1 | grep -i warning
```

## Messages Clés à Surveiller

### Ingestion Worker

```bash
# Succès
"Processing job..."
"Very small document detected..."
"Created X document chunks"

# Erreurs
"Error processing job..."
"Failed to embed chunks..."
```

### API RAG

```bash
# Recherche réussie
"Query enrichie: 'X' → 'Y'"
"5 sources sauvegardées"

# Reranking
"Reranking activé: recherche de 20 candidats"
"Mode recherche: Directe (sans reranking)"
```

### Healthchecks

```bash
# Vérifier santé
docker-compose logs | grep -i "health\|ready\|startup complete"
```

## Commandes Avancées

### Logs avec Timestamp

```bash
docker-compose logs -f --timestamps ragfab-api
```

### Dernières N Lignes

```bash
docker-compose logs --tail 50 ragfab-api
```

### Logs depuis une Date

```bash
docker-compose logs --since "2h" ragfab-api  # Dernières 2 heures
docker-compose logs --since "2024-01-01" ragfab-api
```

### Stats Ressources

```bash
docker stats --format "table {{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}"
```

## Exécuter

Quel service voulez-vous inspecter ?
1. **all** - Tous les services
2. **api** - API Backend
3. **worker** - Ingestion Worker
4. **errors** - Filtrer erreurs uniquement
5. **stats** - Utilisation ressources
