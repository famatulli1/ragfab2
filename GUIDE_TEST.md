# 🧪 Guide de Test - RAGFab

Ce guide vous permet de tester rapidement le projet RAGFab en local.

---

## ✅ Étape 1 : Vérifier que les services sont démarrés

```bash
cd ragfab
docker-compose ps
```

**Résultat attendu** :
```
NAME                    STATUS    PORTS
ragfab-postgres        running   0.0.0.0:5432->5432/tcp
ragfab-embeddings      running   0.0.0.0:8001->8001/tcp
```

Si les services ne sont pas démarrés :
```bash
docker-compose up -d postgres embeddings
```

⏱️ **Note** : Le premier démarrage peut prendre 5-10 minutes (téléchargement du modèle d'embeddings ~2.2GB)

---

## ✅ Étape 2 : Tester le serveur d'embeddings

```bash
curl http://localhost:8001/health
```

**Résultat attendu** :
```json
{
  "status": "healthy",
  "model": "intfloat/multilingual-e5-large",
  "dimension": 1024
}
```

**Test d'embedding** :
```bash
curl -X POST http://localhost:8001/embed \
  -H "Content-Type: application/json" \
  -d "{\"text\": \"Bonjour, ceci est un test en français\"}"
```

**Résultat attendu** :
```json
{
  "embedding": [0.123, -0.456, ...],  # 1024 valeurs
  "dimension": 1024,
  "model": "intfloat/multilingual-e5-large"
}
```

---

## ✅ Étape 3 : Vérifier PostgreSQL

```bash
docker exec -it ragfab-postgres psql -U raguser -d ragdb -c "\dt"
```

**Résultat attendu** :
```
           List of relations
 Schema |   Name    | Type  |  Owner
--------+-----------+-------+---------
 public | chunks    | table | raguser
 public | documents | table | raguser
```

**Vérifier l'extension PGVector** :
```bash
docker exec -it ragfab-postgres psql -U raguser -d ragdb -c "\dx"
```

Vous devriez voir `vector` dans la liste.

---

## ✅ Étape 4 : Ingérer le document de test

Un document de test (`exemple.md`) a été créé dans `rag-app/documents/`.

**Ingestion** :
```bash
docker-compose run --rm rag-app python -m ingestion.ingest --documents /app/documents
```

**Résultat attendu** :
```
INFO - Initializing ingestion pipeline...
INFO - Ingestion pipeline initialized
INFO - Ingesting documents from /app/documents...
INFO - Processing: exemple.md
INFO - Generating embeddings for 15 chunks
INFO - Batch 1/1 processed
INFO - Successfully ingested exemple.md: 15 chunks
INFO - Ingestion complete: 1 documents, 15 chunks
```

**Vérifier que les documents sont dans la base** :
```bash
docker exec -it ragfab-postgres psql -U raguser -d ragdb -c "SELECT COUNT(*) FROM documents;"
docker exec -it ragfab-postgres psql -U raguser -d ragdb -c "SELECT COUNT(*) FROM chunks;"
```

---

## ✅ Étape 5 : Tester l'agent RAG

### Option A : Mode interactif

```bash
docker-compose --profile app up rag-app
```

**Interaction exemple** :
```
Vous: Quelles sont les caractéristiques de RAGFab ?
Assistant: [Réponse basée sur le document exemple.md avec citations]

Vous: Quel modèle LLM est utilisé ?
Assistant: [Réponse sur Chocolatine-2-14B]

Vous: quit
```

### Option B : Test rapide sans Docker

Si vous avez Python installé localement :

```bash
cd rag-app

# Installer les dépendances
pip install -r requirements.txt

# Configurer les variables d'environnement
set DATABASE_URL=postgresql://raguser:changeme_secure_password@localhost:5432/ragdb
set EMBEDDINGS_API_URL=http://localhost:8001
set CHOCOLATINE_API_URL=https://apigpt.mynumih.fr

# Lancer l'agent
python rag_agent.py
```

---

## 🔍 Dépannage

### Les containers ne démarrent pas

```bash
# Voir les logs
docker-compose logs postgres
docker-compose logs embeddings

# Redémarrer les services
docker-compose down
docker-compose up -d
```

### Le serveur d'embeddings ne répond pas

```bash
# Vérifier les logs
docker-compose logs embeddings

# Le modèle prend du temps à charger (2-3 minutes au premier démarrage)
# Attendre et retester
```

### Erreur de connexion à la base de données

```bash
# Vérifier que PostgreSQL est accessible
docker exec -it ragfab-postgres psql -U raguser -d ragdb -c "SELECT 1;"

# Vérifier les credentials dans .env
cat .env | grep DATABASE_URL
```

### Erreur lors de l'ingestion

```bash
# Vérifier que le serveur d'embeddings répond
curl http://localhost:8001/health

# Vérifier les logs de l'ingestion
docker-compose run --rm rag-app python -m ingestion.ingest --documents /app/documents
```

---

## 📊 Tests de performance

### Test de latence des embeddings

```bash
# Mesurer le temps de génération d'un embedding
time curl -X POST http://localhost:8001/embed \
  -H "Content-Type: application/json" \
  -d "{\"text\": \"Test de latence\"}"
```

**Temps attendu** : 50-200ms sur CPU

### Test de batch

```bash
curl -X POST http://localhost:8001/embed_batch \
  -H "Content-Type: application/json" \
  -d "{\"texts\": [\"Texte 1\", \"Texte 2\", \"Texte 3\", \"Texte 4\", \"Texte 5\"]}"
```

**Temps attendu** : <1 seconde pour 5 textes

---

## 🧹 Nettoyage

Pour tout arrêter et nettoyer :

```bash
# Arrêter les services
docker-compose down

# Supprimer les volumes (⚠️ supprime la base de données)
docker-compose down -v

# Supprimer les images
docker rmi ragfab-embeddings ragfab-rag-app
```

---

## ✨ Prochaines étapes

Une fois les tests réussis :

1. **Ajouter vos propres documents** dans `rag-app/documents/`
2. **Réingérer** avec `docker-compose run --rm rag-app python -m ingestion.ingest --documents /app/documents`
3. **Tester** l'agent avec vos questions
4. **Déployer sur Coolify** en utilisant `docker-compose.coolify.yml`

---

**📝 Note** : Pour des questions ou problèmes, consultez le [README.md](README.md) ou ouvrez une issue sur GitHub.
