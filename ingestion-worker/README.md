# RAGFab Ingestion Worker

Service worker permanent qui traite l'ingestion de documents uploadés via l'interface admin.

## Architecture

```
Frontend Upload → Web API → PostgreSQL (ingestion_jobs)
                              ↓ (poll every 3s)
                    Ingestion Worker
                              ↓
                    Document Processing Pipeline
                              ↓
                    PostgreSQL (documents + chunks)
```

## Fonctionnement

### 1. Upload (Interface Admin)

L'utilisateur uploade un document via l'interface admin :

- Fichier validé (type + taille < 100MB)
- Sauvegardé dans `/app/uploads/{job_id}/filename.pdf`
- Job créé dans `ingestion_jobs` avec `status='pending'`

### 2. Worker Loop (Service Permanent)

Le worker tourne en continu et :

1. **Poll PostgreSQL** toutes les 3 secondes
2. **Détecte les jobs pending**
3. **Claim le job** (status → `processing`)
4. **Traite le document** :
   - Lecture avec Docling (PDF, DOCX, etc.)
   - Chunking avec HybridChunker
   - Génération embeddings (E5-Large)
   - Sauvegarde dans PostgreSQL
5. **Met à jour progress** (0% → 100%)
6. **Finalise le job** (status → `completed` ou `failed`)

### 3. Frontend Polling

Le frontend poll l'API toutes les 2 secondes :

```typescript
GET /api/admin/documents/jobs/{job_id}
```

Affiche une progress bar en temps réel.

## Variables d'environnement

```bash
# Database
DATABASE_URL=postgresql://user:pass@postgres:5432/ragdb

# Embeddings
EMBEDDINGS_API_URL=http://embeddings:8001
EMBEDDING_DIMENSION=1024

# Chunking
CHUNK_SIZE=1500
CHUNK_OVERLAP=200
USE_SEMANTIC_CHUNKING=true

# Worker configuration
WORKER_POLL_INTERVAL=3          # Poll interval in seconds
WORKER_TIMEOUT_MINUTES=30       # Timeout for stuck jobs
UPLOADS_DIR=/app/uploads        # Shared volume with API
```

## Volume Partagé

Le volume `api_uploads` est partagé entre :

- **ragfab-api** : Upload et stockage des fichiers
- **ingestion-worker** : Lecture et traitement des fichiers

```yaml
volumes:
  api_uploads:
    driver: local
```

## Gestion des Erreurs

### Job Timeout

Si un job reste en `processing` > 30 minutes :

- Considéré comme "stuck" (worker crash probable)
- Reset automatique à `status='pending'` au démarrage du worker
- Sera retraité automatiquement

### Échecs de Traitement

En cas d'erreur pendant le traitement :

- `status='failed'`
- `error_message` contient le détail de l'erreur
- Fichier uploadé nettoyé
- Visible dans l'interface admin

### Retry

Actuellement, pas de retry automatique. Les jobs failed restent en base pour analyse.

**Extension future** : Ajouter un compteur de retry et réessayer automatiquement les jobs failed.

## Formats Supportés

Le worker supporte tous les formats gérés par Docling :

- **Documents** : PDF, DOCX, DOC, PPTX, PPT
- **Tableurs** : XLSX, XLS
- **Web** : HTML, HTM
- **Texte** : MD, TXT

## Monitoring

### Logs Worker

```bash
docker-compose logs -f ingestion-worker
```

Messages clés :

- `🚀 Worker started (polling every 3s)`
- `📄 Processing job {job_id}: {filename}`
- `✅ Job {job_id} completed: {chunks_created} chunks created`
- `❌ Job {job_id} failed: {error_message}`

### Statut Jobs

Via l'API :

```bash
# Statut d'un job
GET /api/admin/documents/jobs/{job_id}

# Liste de tous les jobs
GET /api/admin/documents/jobs?status_filter=processing

# Réponse
{
  "id": "uuid",
  "filename": "document.pdf",
  "status": "processing",  # pending, processing, completed, failed
  "progress": 45,          # 0-100%
  "chunks_created": 0,
  "error_message": null,
  "created_at": "2025-01-10T10:00:00Z",
  "started_at": "2025-01-10T10:00:05Z",
  "completed_at": null
}
```

## Performance

### Ressources Allouées

```yaml
deploy:
  resources:
    limits:
      cpus: '2'
      memory: 4G
    reservations:
      cpus: '1'
      memory: 2G
```

### Temps de Traitement Typiques

- **PDF 10 pages** : ~30-60 secondes
- **PDF 50 pages** : ~2-3 minutes
- **DOCX 100 pages** : ~3-5 minutes

Facteurs :

- Docling parsing : ~50% du temps
- Embeddings generation : ~40% du temps
- Database save : ~10% du temps

## Développement

### Test Local

```bash
# Build et démarrage
docker-compose up -d ingestion-worker

# Logs en temps réel
docker-compose logs -f ingestion-worker

# Restart après modifications
docker-compose restart ingestion-worker
```

### Debug Mode

Activer logs détaillés :

```python
# worker.py
logging.basicConfig(level=logging.DEBUG)
```

### Test d'Upload

1. Connectez-vous à l'admin : `http://localhost:3000/admin`
2. Uploadez un document PDF
3. Surveillez les logs du worker
4. Vérifiez la progression dans l'interface

## Extensions Futures

### 1. Server-Sent Events (SSE)

Remplacer le polling par SSE pour push temps réel :

```python
@router.get("/ingestion/stream")
async def ingestion_stream():
    async def event_generator():
        while True:
            # Push events to client
            yield f"data: {json.dumps(status)}\n\n"
```

### 2. Multi-Workers

Plusieurs workers en parallèle pour haute charge :

```yaml
ingestion-worker:
  deploy:
    replicas: 3  # 3 workers simultanés
```

### 3. Job Priorité

Ajouter une colonne `priority` pour traiter les jobs urgents en premier :

```sql
ALTER TABLE ingestion_jobs ADD COLUMN priority INTEGER DEFAULT 0;
```

### 4. Upload par Batch

Gérer plusieurs fichiers en un seul job :

```typescript
// Frontend
uploadMultiple(files: File[])
```

### 5. Notification Completion

Email ou webhook à la fin du traitement :

```python
# worker.py
await send_notification(user_email, job_status)
```

## Dépannage

### Worker ne démarre pas

```bash
# Vérifier logs
docker-compose logs ingestion-worker

# Erreurs communes
# 1. Database connection failed → Vérifier DATABASE_URL
# 2. Embeddings service not ready → Attendre embeddings healthcheck
# 3. Volume not mounted → Vérifier docker-compose.yml volumes
```

### Jobs restent pending

```bash
# Vérifier que le worker tourne
docker-compose ps ingestion-worker

# Vérifier les logs pour erreurs
docker-compose logs -f ingestion-worker

# Restart worker si nécessaire
docker-compose restart ingestion-worker
```

### Fichier uploadé manquant

```bash
# Vérifier le volume
docker-compose exec ingestion-worker ls -la /app/uploads/

# Vérifier que le fichier a bien été uploadé
docker-compose exec ragfab-api ls -la /app/uploads/{job_id}/
```

## Support

Pour tout problème :

1. Vérifiez les logs : `docker-compose logs -f ingestion-worker`
2. Vérifiez les jobs en base : `SELECT * FROM ingestion_jobs ORDER BY created_at DESC;`
3. Consultez le fichier CLAUDE.md pour l'architecture complète
