# RAGFab Ingestion Worker - Déploiement Coolify

Service worker permanent qui traite l'ingestion de documents uploadés via l'interface admin.

## Prérequis

✅ Services déjà déployés sur Coolify :
- **ragfab-postgres** : Base de données PostgreSQL
- **ragfab-embeddings** : Service d'embeddings (E5-Large)
- **ragfab-api** : API backend FastAPI

⚠️ **Important** : Le volume `ragfab_uploads` doit être créé et partagé avec `ragfab-api`.

## Création du volume partagé

Le worker et l'API backend doivent partager le même volume pour les fichiers uploadés.

### Option 1 : Via Coolify UI (Recommandé)

1. Aller dans **Settings** → **Volumes**
2. Créer un nouveau volume nommé : `ragfab_uploads`
3. Type : **Persistent Volume**
4. Attacher ce volume à :
   - `ragfab-api` : mount path `/app/uploads`
   - `ragfab-ingestion-worker` : mount path `/app/uploads`

### Option 2 : Via Docker CLI

```bash
# Se connecter au serveur Coolify
ssh user@your-server

# Créer le volume partagé
docker volume create ragfab_uploads

# Vérifier
docker volume ls | grep ragfab_uploads
```

## Déploiement sur Coolify

### Étape 1 : Créer une nouvelle ressource

1. Aller dans votre projet RAGFab sur Coolify
2. Cliquer sur **"+ Add New Resource"**
3. Sélectionner **"Docker Compose"**
4. Nom de la ressource : `ragfab-ingestion-worker`

### Étape 2 : Configuration Git

- **Repository** : Même que vos autres services RAGFab
- **Branch** : `main` (ou votre branche de production)
- **Docker Compose Location** : `coolify/6-ingestion-worker/docker-compose.yml`
- **Build Pack** : Docker Compose

### Étape 3 : Variables d'environnement

Copier les variables depuis `.env.example` et les adapter :

```bash
# Database
DATABASE_URL=postgresql://raguser:VOTRE_MOT_DE_PASSE@ragfab-postgres.internal:5432/ragdb

# Embeddings
EMBEDDINGS_API_URL=http://ragfab-embeddings.internal:8001
EMBEDDING_DIMENSION=1024

# Chunking
CHUNK_SIZE=1500
CHUNK_OVERLAP=200
USE_SEMANTIC_CHUNKING=true

# Worker
WORKER_POLL_INTERVAL=3
WORKER_TIMEOUT_MINUTES=30
UPLOADS_DIR=/app/uploads

# Cache
TRANSFORMERS_CACHE=/home/worker/.cache/huggingface
LOG_LEVEL=INFO
```

⚠️ **Remplacer** :
- `VOTRE_MOT_DE_PASSE` : Le mot de passe PostgreSQL (même que ragfab-api)
- Vérifier que les URLs `.internal` correspondent à vos noms de containers

### Étape 4 : Configuration réseau

- **Network** : Utiliser le réseau `coolify` (externe)
- **No public port** : Le worker n'expose aucun port (interne uniquement)

### Étape 5 : Volumes

Configurer les volumes dans Coolify :

1. **Volume partagé uploads** (CRITIQUE) :
   - Name : `ragfab_uploads` (volume externe créé précédemment)
   - Mount path : `/app/uploads`
   - Type : External Volume

2. **Cache ML** (optionnel mais recommandé) :
   - Name : `ragfab-worker-cache`
   - Mount path : `/home/worker/.cache`
   - Type : Persistent Volume

### Étape 6 : Limites de ressources

Dans **Advanced** → **Resource Limits** :

```yaml
CPU Limit: 2.0
Memory Limit: 4G
CPU Reservation: 1.0
Memory Reservation: 2G
```

### Étape 7 : Déployer

1. Cliquer sur **"Deploy"**
2. Surveiller les logs en temps réel
3. Attendre que le healthcheck soit OK (~ 60s)

## Vérification du déploiement

### 1. Vérifier que le worker tourne

```bash
# Via Coolify UI: aller dans Logs

# Via CLI (si accès SSH au serveur)
docker ps | grep ragfab-ingestion-worker
docker logs ragfab-ingestion-worker --tail 50
```

Messages attendus :
```
🚀 Worker started (polling every 3s)
Ingestion pipeline initialized
✅ Worker initialization complete
```

### 2. Tester l'upload via l'interface admin

1. Aller sur `https://votre-domaine.fr/admin`
2. Login : admin / votre_mot_de_passe
3. Uploader un document PDF de test
4. Surveiller les logs du worker :

```bash
docker logs ragfab-ingestion-worker -f
```

Messages attendus :
```
📄 Processing job {job_id}: test.pdf
Found file: /app/uploads/{job_id}/test.pdf
Reading document...
Document title: Test Document
Created 15 chunks
Generating embeddings...
Saving to database...
✅ Job {job_id} completed: 15 chunks created
```

### 3. Vérifier dans PostgreSQL

```bash
docker exec ragfab-postgres psql -U raguser -d ragdb -c "SELECT id, filename, status, progress, chunks_created FROM ingestion_jobs ORDER BY created_at DESC LIMIT 5;"
```

Résultat attendu :
```
                  id                  |   filename   |  status   | progress | chunks_created
--------------------------------------+--------------+-----------+----------+----------------
 uuid-ici                             | test.pdf     | completed |      100 |             15
```

## Troubleshooting

### Le worker ne démarre pas

**Vérifier les logs** :
```bash
docker logs ragfab-ingestion-worker --tail 100
```

**Erreurs communes** :

1. **Database connection failed**
   - Vérifier `DATABASE_URL` : doit être `ragfab-postgres.internal` (pas `postgres`)
   - Vérifier que PostgreSQL est accessible : `docker exec ragfab-postgres pg_isready`

2. **Embeddings service not ready**
   - Vérifier que `ragfab-embeddings` tourne : `docker ps | grep embeddings`
   - Attendre le healthcheck (60s de start_period)

3. **Volume not mounted**
   - Vérifier que le volume `ragfab_uploads` existe : `docker volume ls | grep ragfab_uploads`
   - Vérifier que le volume est bien attaché : `docker inspect ragfab-ingestion-worker | grep -A 10 Mounts`

### Jobs restent en "pending"

**Diagnostic** :
```bash
# Vérifier que le worker poll
docker logs ragfab-ingestion-worker | grep "poll"

# Vérifier les jobs pending dans la DB
docker exec ragfab-postgres psql -U raguser -d ragdb -c "SELECT id, filename, status, created_at FROM ingestion_jobs WHERE status='pending';"
```

**Solutions** :
- Restart le worker : Dans Coolify UI → **Restart**
- Vérifier que le worker a accès à la base : tester `DATABASE_URL`

### Fichier uploadé manquant

**Vérifier le volume** :
```bash
# Vérifier que le volume est monté
docker exec ragfab-ingestion-worker ls -la /app/uploads/

# Vérifier depuis l'API
docker exec ragfab-api ls -la /app/uploads/
```

**Solution** :
- Les deux containers doivent voir le même contenu
- Si pas le cas → volume partagé mal configuré → Recréer le volume externe

### Performances lentes

**Optimiser** :
1. Augmenter les ressources CPU/RAM dans Coolify
2. Réduire `CHUNK_SIZE` si documents très gros
3. Vérifier la latence réseau vers `ragfab-embeddings`

**Monitoring** :
```bash
# Temps de traitement moyen
docker exec ragfab-postgres psql -U raguser -d ragdb -c "SELECT filename, EXTRACT(EPOCH FROM (completed_at - started_at)) as duration_seconds FROM ingestion_jobs WHERE status='completed' ORDER BY completed_at DESC LIMIT 10;"
```

## Maintenance

### Restart le worker

```bash
# Via Coolify UI
# Aller dans le service → Restart

# Via CLI
docker restart ragfab-ingestion-worker
```

### Vider le cache ML

```bash
# Supprimer le volume cache (force re-téléchargement des modèles)
docker volume rm ragfab-worker-cache

# Restart le worker
docker restart ragfab-ingestion-worker
```

### Nettoyer les jobs terminés

```bash
docker exec ragfab-postgres psql -U raguser -d ragdb -c "DELETE FROM ingestion_jobs WHERE status='completed' AND completed_at < NOW() - INTERVAL '30 days';"
```

## Monitoring Production

### Logs en temps réel

```bash
docker logs ragfab-ingestion-worker -f
```

### Métriques

```bash
# Nombre de jobs par statut
docker exec ragfab-postgres psql -U raguser -d ragdb -c "SELECT status, COUNT(*) FROM ingestion_jobs GROUP BY status;"

# Jobs échoués récents
docker exec ragfab-postgres psql -U raguser -d ragdb -c "SELECT id, filename, error_message, completed_at FROM ingestion_jobs WHERE status='failed' ORDER BY completed_at DESC LIMIT 10;"

# Statistiques de performance
docker exec ragfab-postgres psql -U raguser -d ragdb -c "SELECT AVG(chunks_created) as avg_chunks, AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) as avg_duration_sec FROM ingestion_jobs WHERE status='completed';"
```

## Mise à jour

Lorsque vous poussez une nouvelle version du code :

1. Coolify détecte automatiquement le nouveau commit (si auto-deploy activé)
2. Ou manuellement : **Redeploy** dans Coolify UI
3. Le worker redémarre automatiquement
4. Les jobs en cours de traitement sont reset à `pending` et retraités

## Support

Pour tout problème :
1. Consulter les logs : `docker logs ragfab-ingestion-worker`
2. Vérifier la base de données : `SELECT * FROM ingestion_jobs ORDER BY created_at DESC;`
3. Consulter le fichier `CLAUDE.md` pour l'architecture complète
4. Voir `CHECKLIST_COOLIFY.md` pour le guide pas-à-pas
