# Checklist de Déploiement - Ingestion Worker

Guide pas-à-pas pour déployer le worker d'ingestion sur Coolify.

## 📋 Pré-déploiement

### ✅ Prérequis

- [ ] PostgreSQL (`ragfab-postgres`) est déployé et fonctionne
- [ ] Embeddings service (`ragfab-embeddings`) est déployé et fonctionne
- [ ] API Backend (`ragfab-api`) est déployé et fonctionne
- [ ] La table `ingestion_jobs` existe dans PostgreSQL (créée par `02_web_schema.sql`)

### ✅ Volume partagé

**CRITIQUE** : Le worker et l'API doivent partager le même volume.

- [ ] Créer le volume externe `ragfab_uploads` :
  ```bash
  docker volume create ragfab_uploads
  ```

- [ ] Vérifier que `ragfab-api` utilise ce volume :
  ```bash
  docker inspect ragfab-api | grep -A 10 Mounts
  # Doit montrer: ragfab_uploads → /app/uploads
  ```

- [ ] Si `ragfab-api` n'utilise pas encore ce volume → **Le reconfigurer d'abord**

## 🚀 Déploiement

### Étape 1 : Créer la ressource Coolify

- [ ] Aller dans le projet RAGFab sur Coolify
- [ ] Cliquer sur **"+ Add New Resource"**
- [ ] Sélectionner **"Docker Compose"**
- [ ] Nom : `ragfab-ingestion-worker`

### Étape 2 : Configuration Git

- [ ] Repository : Même repo que vos autres services
- [ ] Branch : `main` (ou votre branche de prod)
- [ ] Docker Compose Location : `coolify/6-ingestion-worker/docker-compose.yml`
- [ ] Build Pack : **Docker Compose**

### Étape 3 : Variables d'environnement

Copier-coller ces variables en adaptant les valeurs :

```bash
DATABASE_URL=postgresql://raguser:VOTRE_PASSWORD@ragfab-postgres.internal:5432/ragdb
EMBEDDINGS_API_URL=http://ragfab-embeddings.internal:8001
EMBEDDING_DIMENSION=1024
CHUNK_SIZE=1500
CHUNK_OVERLAP=200
USE_SEMANTIC_CHUNKING=true
WORKER_POLL_INTERVAL=3
WORKER_TIMEOUT_MINUTES=30
UPLOADS_DIR=/app/uploads
TRANSFORMERS_CACHE=/home/worker/.cache/huggingface
LOG_LEVEL=INFO
```

- [ ] Variable `DATABASE_URL` : Remplacer `VOTRE_PASSWORD` par le vrai mot de passe
- [ ] Variable `DATABASE_URL` : Vérifier le nom du container PostgreSQL (`.internal`)
- [ ] Variable `EMBEDDINGS_API_URL` : Vérifier le nom du container embeddings

### Étape 4 : Configuration réseau

- [ ] Network : `coolify` (réseau externe)
- [ ] Pas de port public à exposer

### Étape 5 : Volumes

**Volume 1 - Uploads partagé (OBLIGATOIRE)** :
- [ ] Type : **External Volume**
- [ ] Name : `ragfab_uploads`
- [ ] Mount path : `/app/uploads`

**Volume 2 - Cache ML (Recommandé)** :
- [ ] Type : **Persistent Volume**
- [ ] Name : `ragfab-worker-cache`
- [ ] Mount path : `/home/worker/.cache`

### Étape 6 : Limites de ressources

- [ ] CPU Limit : `2.0`
- [ ] Memory Limit : `4G`
- [ ] CPU Reservation : `1.0`
- [ ] Memory Reservation : `2G`

### Étape 7 : Déployer

- [ ] Cliquer sur **"Deploy"**
- [ ] Surveiller les logs en temps réel
- [ ] Attendre le message : `✅ Worker initialization complete`
- [ ] Attendre que le healthcheck passe (~ 60s)

## ✅ Post-déploiement

### Vérification du worker

- [ ] **Container running** :
  ```bash
  docker ps | grep ragfab-ingestion-worker
  # Status : Up (healthy)
  ```

- [ ] **Logs OK** :
  ```bash
  docker logs ragfab-ingestion-worker --tail 50
  # Messages attendus :
  # - "🚀 Worker started (polling every 3s)"
  # - "Ingestion pipeline initialized"
  # - "✅ Worker initialization complete"
  ```

- [ ] **Pas d'erreurs dans les logs** (surtout pas de Database connection failed)

### Vérification du volume partagé

- [ ] **Worker voit le volume** :
  ```bash
  docker exec ragfab-ingestion-worker ls -la /app/uploads/
  # Doit afficher le contenu (ou vide si pas encore d'upload)
  ```

- [ ] **API voit le même volume** :
  ```bash
  docker exec ragfab-api ls -la /app/uploads/
  # Doit afficher le MÊME contenu
  ```

- [ ] Si différent → **Problème de volume partagé** → Revenir à l'étape 5

### Test d'upload

- [ ] **Accéder à l'interface admin** :
  ```
  https://votre-domaine.fr/admin
  ```

- [ ] **Login** : admin / votre_mot_de_passe

- [ ] **Uploader un PDF de test** (< 10MB pour commencer)

- [ ] **Surveiller les logs du worker** :
  ```bash
  docker logs ragfab-ingestion-worker -f
  ```

  Messages attendus :
  ```
  📄 Processing job {job_id}: test.pdf
  Found file: /app/uploads/{job_id}/test.pdf
  Reading document...
  Document title: Test
  Created N chunks
  Generating embeddings...
  Saving to database...
  ✅ Job {job_id} completed: N chunks created
  ```

- [ ] **Frontend affiche "✓ Terminé - N chunks créés"**

- [ ] **Document apparaît dans la liste des documents admin**

### Vérification base de données

- [ ] **Job completed dans la DB** :
  ```bash
  docker exec ragfab-postgres psql -U raguser -d ragdb -c \
    "SELECT id, filename, status, progress, chunks_created FROM ingestion_jobs ORDER BY created_at DESC LIMIT 5;"
  ```

  Résultat attendu :
  ```
  status = completed
  progress = 100
  chunks_created > 0
  ```

- [ ] **Document créé** :
  ```bash
  docker exec ragfab-postgres psql -U raguser -d ragdb -c \
    "SELECT title, COUNT(c.id) as chunks FROM documents d LEFT JOIN chunks c ON d.id = c.document_id GROUP BY d.id, d.title ORDER BY d.created_at DESC LIMIT 5;"
  ```

  Le document test doit apparaître avec N chunks

## 🔥 Troubleshooting

### ❌ Worker ne démarre pas

**Logs à vérifier** :
```bash
docker logs ragfab-ingestion-worker --tail 100
```

**Solutions selon l'erreur** :

| Erreur | Solution |
|--------|----------|
| `Database connection failed` | Vérifier `DATABASE_URL`, tester `pg_isready` |
| `Embeddings service not ready` | Attendre 60s (start_period), vérifier embeddings running |
| `Volume not mounted` | Vérifier volume externe `ragfab_uploads` existe |
| `Module not found: ingestion` | Build problem, vérifier que `rag-app` est copié dans Dockerfile |

### ❌ Jobs restent en "pending"

- [ ] Vérifier que le worker poll :
  ```bash
  docker logs ragfab-ingestion-worker | grep "pending"
  ```

- [ ] Restart le worker :
  - Via Coolify UI : **Restart**
  - Ou CLI : `docker restart ragfab-ingestion-worker`

### ❌ Fichier uploadé manquant

- [ ] Vérifier que les deux containers voient le volume :
  ```bash
  # Uploader un fichier via l'interface
  # Puis vérifier immédiatement :

  # Depuis l'API
  docker exec ragfab-api ls -la /app/uploads/

  # Depuis le worker
  docker exec ragfab-ingestion-worker ls -la /app/uploads/

  # Les deux doivent afficher le même fichier
  ```

- [ ] Si différent → **Volume externe mal configuré** :
  - Supprimer et recréer le volume
  - Reconfigurer les deux services avec le même volume

### ❌ Performances lentes

- [ ] Augmenter CPU/RAM dans Coolify
- [ ] Vérifier latence réseau vers embeddings :
  ```bash
  docker exec ragfab-ingestion-worker curl -s http://ragfab-embeddings.internal:8001/health
  ```
- [ ] Réduire `CHUNK_SIZE` si documents très gros

## ✅ Validation finale

- [ ] **Worker tourne** : Status "Up (healthy)" dans Coolify
- [ ] **Volume partagé fonctionne** : API et worker voient les mêmes fichiers
- [ ] **Upload test réussi** : Document visible dans l'interface admin
- [ ] **Logs propres** : Pas d'erreur dans les logs worker
- [ ] **Database OK** : Jobs complétés avec chunks_created > 0

## 🎉 Déploiement terminé !

Le worker d'ingestion est maintenant opérationnel. Les documents uploadés via l'interface admin seront traités automatiquement.

**Monitoring continu** :
```bash
# Surveiller les logs
docker logs ragfab-ingestion-worker -f

# Vérifier les jobs
docker exec ragfab-postgres psql -U raguser -d ragdb -c \
  "SELECT status, COUNT(*) FROM ingestion_jobs GROUP BY status;"
```
