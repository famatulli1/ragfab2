# Commande /ingest - Ingestion de Documents RAGFab

Tu es un expert en ingestion documentaire. Aide l'utilisateur à ingérer des documents dans RAGFab.

## Méthodes d'Ingestion

### 1. Via Interface Admin (Recommandé)

1. Accéder à `http://localhost:3000/admin` (ou votre domaine)
2. Se connecter avec identifiants admin
3. Glisser-déposer les documents
4. Sélectionner les options :
   - **OCR Engine** : rapidocr (recommandé) / easyocr / tesseract
   - **VLM Engine** : internvl (images) / paddleocr-vl / none
   - **Chunker** : hybrid (recommandé) / parent_child

### 2. Surveiller l'Ingestion

```bash
# Logs du worker en temps réel
docker-compose logs -f ingestion-worker

# Messages attendus :
# "Processing job X..."
# "Very small document detected (Y words) - using max_tokens=4000"
# "Created Z document chunks"
```

### 3. Vérifier en Base de Données

```bash
docker-compose exec postgres psql -U raguser -d ragdb -c "
SELECT d.title, COUNT(c.id) as chunks, d.created_at
FROM documents d
LEFT JOIN chunks c ON d.id = c.document_id
GROUP BY d.id, d.title, d.created_at
ORDER BY d.created_at DESC
LIMIT 10;"
```

### 4. Ré-indexation Document Spécifique

```bash
# Supprimer ancien document via admin UI
# Puis re-uploader le même fichier

# OU via SQL (supprimer chunks uniquement)
docker-compose exec postgres psql -U raguser -d ragdb -c "
DELETE FROM chunks WHERE document_id = (
  SELECT id FROM documents WHERE title ILIKE '%nom_document%'
);"
```

### 5. Ré-indexation Complète (Attention!)

```bash
# ATTENTION : Supprime TOUS les chunks
docker-compose exec postgres psql -U raguser -d ragdb -c "
DELETE FROM document_images;
DELETE FROM chunks;"

# Puis re-uploader tous les documents via admin
```

## Configuration Chunking

| Type Document | Chunker Recommandé |
|---------------|-------------------|
| Manuel technique | hybrid |
| Transcription interview | parent_child |
| Documentation API | hybrid |
| Livre/chapitre | parent_child |

## Formats Supportés

- PDF, DOCX, MD, TXT, HTML
- Taille max : 100 MB par fichier

## Exécuter

Quelle action souhaitez-vous effectuer ?
1. **status** - Vérifier jobs en cours
2. **logs** - Afficher logs ingestion
3. **verify** - Vérifier documents en base
4. **reindex** - Instructions ré-indexation
