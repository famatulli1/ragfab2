# Guide de test : Mise en évidence des chunks dans les PDFs

Ce guide décrit la procédure de test complète pour la fonctionnalité de mise en évidence des chunks sources dans les PDFs originaux.

## Vue d'ensemble de la fonctionnalité

**Objectif** : Permettre aux utilisateurs de voir les chunks sources surlignés dans le PDF original, facilitant la vérification de la pertinence et du contexte des sources RAG.

**Architecture** :
1. **Backend** : Extraction des bounding boxes via Docling → Stockage dans PostgreSQL → Génération PDF annoté avec PyMuPDF
2. **Frontend** : Bouton "Voir dans PDF" dans DocumentViewModal → Ouvre PDF annoté dans nouvel onglet

---

## Phase 1 : Tests Backend (Extraction et Stockage)

### 1.1 Appliquer la migration SQL

```bash
# 1. Vérifier que la migration existe
ls -la database/migrations/11_add_chunk_bbox.sql

# 2. Appliquer la migration (système automatique)
docker-compose up -d --build

# OU manuellement si le système automatique échoue
docker-compose exec postgres psql -U raguser -d ragdb \
  -f /docker-entrypoint-initdb.d/11_add_chunk_bbox.sql
```

**Validation** :
```sql
-- Vérifier que la colonne bbox existe
docker-compose exec postgres psql -U raguser -d ragdb \
  -c "\d chunks" | grep bbox

-- Vérifier les fonctions helper
docker-compose exec postgres psql -U raguser -d ragdb \
  -c "\df get_chunks_*"

-- Résultat attendu :
-- bbox | jsonb |
-- get_chunks_for_annotation
-- get_chunks_with_bbox_for_page
```

### 1.2 Rebuild des services avec nouveau code

```bash
# 1. Rebuild ingestion worker (extrait bbox)
docker-compose build ingestion-worker

# 2. Rebuild web-api (route PDF annoté)
docker-compose build ragfab-api

# 3. Rebuild frontend (bouton)
docker-compose build ragfab-frontend

# 4. Restart tous les services
docker-compose up -d
```

### 1.3 Tester l'extraction de bbox

```bash
# 1. Uploader un document PDF via l'interface admin
# http://localhost:3000/admin
# - Login : admin / admin
# - Onglet "Documents"
# - Upload un PDF de test (ex: documentation technique avec texte structuré)

# 2. Vérifier les logs du worker pour confirmer l'extraction bbox
docker-compose logs -f ingestion-worker | grep -i bbox

# Logs attendus :
# "Extracted bbox for chunk 0: page=1, bbox={'l': 72.0, 't': 800.5, 'r': 540.0, 'b': 750.2}"
# "Extracted bbox for chunk 1: page=1, bbox={'l': 72.0, 't': 740.1, 'r': 540.0, 'b': 690.3}"
```

### 1.4 Vérifier le stockage en DB

```bash
# 1. Récupérer le dernier document ingesté
docker-compose exec postgres psql -U raguser -d ragdb -c "
  SELECT id, title
  FROM documents
  ORDER BY created_at DESC
  LIMIT 1;
"

# 2. Vérifier que les chunks ont des bbox
docker-compose exec postgres psql -U raguser -d ragdb -c "
  SELECT
    id,
    chunk_index,
    bbox IS NOT NULL as has_bbox,
    metadata->>'page_number' as page,
    substring(content, 1, 50) as content_preview
  FROM chunks
  WHERE document_id = (SELECT id FROM documents ORDER BY created_at DESC LIMIT 1)
  ORDER BY chunk_index
  LIMIT 10;
"

# Résultat attendu :
# id     | chunk_index | has_bbox | page | content_preview
# -------|-------------|----------|------|------------------
# uuid1  | 0           | t        | 1    | [Document: Test PDF] Introduction to...
# uuid2  | 1           | t        | 1    | [Document: Test PDF] This document...
# uuid3  | 2           | t        | 2    | [Document: Test PDF] Chapter 1...
```

**⚠️ Points d'attention** :
- Si `has_bbox = f` (false) : Vérifier que Docling extrait bien les bbox pour ce type de PDF
- Tous les PDFs ne contiennent pas forcément de bbox (PDFs scannés par exemple)
- Les logs du chunker doivent indiquer si bbox n'est pas disponible

---

## Phase 2 : Tests API (Génération PDF Annoté)

### 2.1 Tester l'endpoint API directement

```bash
# 1. Obtenir un token JWT valide
TOKEN=$(curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin"}' | jq -r '.access_token')

# 2. Récupérer un document_id et chunk_id
DOCUMENT_ID=$(docker-compose exec postgres psql -U raguser -d ragdb -t -c "
  SELECT id FROM documents ORDER BY created_at DESC LIMIT 1;
" | xargs)

CHUNK_ID=$(docker-compose exec postgres psql -U raguser -d ragdb -t -c "
  SELECT id FROM chunks
  WHERE document_id = '$DOCUMENT_ID'
  AND bbox IS NOT NULL
  LIMIT 1;
" | xargs)

echo "Document ID: $DOCUMENT_ID"
echo "Chunk ID: $CHUNK_ID"

# 3. Tester l'endpoint /annotated-pdf
curl "http://localhost:8000/api/documents/${DOCUMENT_ID}/annotated-pdf?chunk_ids=${CHUNK_ID}" \
  -H "Authorization: Bearer $TOKEN" \
  -o test_annotated.pdf

# 4. Ouvrir le PDF généré
open test_annotated.pdf  # macOS
# xdg-open test_annotated.pdf  # Linux
# start test_annotated.pdf  # Windows
```

**Validation visuelle** :
- ✅ Le PDF s'ouvre sans erreur
- ✅ Le chunk spécifié est surligné en **jaune** à la bonne position
- ✅ Le reste du PDF est intact et lisible
- ✅ Le surlignage est semi-transparent (opacité 0.5)

### 2.2 Tester avec plusieurs chunks

```bash
# Récupérer 3 chunk IDs
CHUNK_IDS=$(docker-compose exec postgres psql -U raguser -d ragdb -t -c "
  SELECT string_agg(id::text, ',')
  FROM (
    SELECT id FROM chunks
    WHERE document_id = '$DOCUMENT_ID'
    AND bbox IS NOT NULL
    LIMIT 3
  ) sub;
" | xargs)

echo "Chunk IDs: $CHUNK_IDS"

# Générer PDF avec 3 chunks surlignés
curl "http://localhost:8000/api/documents/${DOCUMENT_ID}/annotated-pdf?chunk_ids=${CHUNK_IDS}" \
  -H "Authorization: Bearer $TOKEN" \
  -o test_annotated_multi.pdf

open test_annotated_multi.pdf
```

**Validation** :
- ✅ Les 3 chunks sont surlignés
- ✅ Pas de chevauchement visuel gênant
- ✅ Surlignages distincts et lisibles

### 2.3 Tester l'endpoint helper (chunks-bbox)

```bash
# Récupérer les métadonnées bbox sans générer le PDF
curl "http://localhost:8000/api/documents/${DOCUMENT_ID}/chunks-bbox" \
  -H "Authorization: Bearer $TOKEN" | jq

# Résultat attendu :
# {
#   "document_id": "uuid...",
#   "chunks_with_bbox": [
#     {
#       "id": "uuid...",
#       "chunk_index": 0,
#       "page_number": 1,
#       "bbox": {"l": 72.0, "t": 800.5, "r": 540.0, "b": 750.2},
#       "content_preview": "..."
#     },
#     ...
#   ]
# }
```

---

## Phase 3 : Tests Frontend (Interface Utilisateur)

### 3.1 Tester le bouton dans DocumentViewModal

**Procédure** :

1. **Ouvrir l'interface RAG** : http://localhost:3000
2. **Login** : `admin` / `admin`
3. **Créer nouvelle conversation** : Bouton "+" dans la sidebar
4. **Poser une question** liée au document uploadé :
   ```
   Question : "Qu'est-ce que [concept du document] ?"
   ```
5. **Attendre la réponse** avec sources affichées
6. **Cliquer sur un source chunk** pour ouvrir DocumentViewModal
7. **Vérifier le bouton "Voir dans PDF"** :
   - ✅ Bouton visible dans le header (bleu, avec icône FileText)
   - ✅ Texte "Voir dans PDF" visible sur desktop
   - ✅ Icône seule visible sur mobile
8. **Cliquer sur "Voir dans PDF"**
9. **Validation** :
   - ✅ Nouvel onglet s'ouvre automatiquement
   - ✅ PDF annoté s'affiche dans le navigateur
   - ✅ Chunk source est surligné en jaune
   - ✅ Position du surlignage correspond au texte du chunk

### 3.2 Tester sur mobile

**Procédure** :

1. Ouvrir DevTools (F12) → Toggle device toolbar (Ctrl+Shift+M)
2. Sélectionner "iPhone 12 Pro" ou "Pixel 5"
3. Répéter les étapes 3.1
4. **Validation** :
   - ✅ Bouton affiche seulement l'icône (texte masqué avec `hidden sm:inline`)
   - ✅ Bouton reste cliquable et fonctionnel
   - ✅ PDF s'ouvre dans nouvel onglet (pas dans modal)

### 3.3 Tester avec document sans bbox

**Scénario** : Documents anciens ou PDFs scannés sans bounding boxes

1. Uploader un PDF scanné (image) via admin
2. Ingestion complète → Chunks créés **sans bbox**
3. Poser une question → Source retournée
4. Cliquer sur source chunk → Modal s'ouvre
5. Cliquer sur "Voir dans PDF"
6. **Validation** :
   - ✅ PDF original s'ouvre **sans surlignage** (fallback gracieux)
   - ❌ Aucune erreur affichée
   - ℹ️ **Note** : Le bouton pourrait être masqué si aucun chunk n'a de bbox (amélioration future)

---

## Phase 4 : Tests de Robustesse

### 4.1 Test avec PDF multi-pages

**Scénario** : Document PDF avec chunks répartis sur plusieurs pages

```bash
# 1. Uploader un PDF de 10+ pages
# 2. Vérifier la distribution des chunks par page
docker-compose exec postgres psql -U raguser -d ragdb -c "
  SELECT
    (metadata->>'page_number')::integer as page,
    COUNT(*) as chunk_count,
    COUNT(CASE WHEN bbox IS NOT NULL THEN 1 END) as chunks_with_bbox
  FROM chunks
  WHERE document_id = '$DOCUMENT_ID'
  GROUP BY page
  ORDER BY page;
"

# 3. Générer PDF avec chunks de différentes pages
CHUNK_IDS_MULTIPAGE=$(docker-compose exec postgres psql -U raguser -d ragdb -t -c "
  SELECT string_agg(id::text, ',')
  FROM (
    SELECT DISTINCT ON ((metadata->>'page_number')::integer) id
    FROM chunks
    WHERE document_id = '$DOCUMENT_ID'
    AND bbox IS NOT NULL
    ORDER BY (metadata->>'page_number')::integer
    LIMIT 5
  ) sub;
" | xargs)

curl "http://localhost:8000/api/documents/${DOCUMENT_ID}/annotated-pdf?chunk_ids=${CHUNK_IDS_MULTIPAGE}" \
  -H "Authorization: Bearer $TOKEN" \
  -o test_multipage.pdf

open test_multipage.pdf
```

**Validation** :
- ✅ Surlignages apparaissent sur les pages correctes
- ✅ Navigation entre pages fonctionne normalement
- ✅ Aucun surlignage ne "déborde" sur une autre page

### 4.2 Test de performance

**Scénario** : PDF volumineux (100+ pages)

```bash
# 1. Uploader un gros PDF
# 2. Mesurer le temps de génération
time curl "http://localhost:8000/api/documents/${DOCUMENT_ID}/annotated-pdf" \
  -H "Authorization: Bearer $TOKEN" \
  -o test_large.pdf

# Temps acceptable : < 5 secondes pour PDF de 100 pages
```

**Optimisation si lent** :
- Ajouter un cache pour les PDFs annotés générés fréquemment
- Limiter le nombre de chunks annotables par requête (ex: max 50)

### 4.3 Test de sécurité

**Scénario** : Vérifier l'isolation des documents par utilisateur

```bash
# 1. Créer un deuxième utilisateur
docker-compose exec postgres psql -U raguser -d ragdb -c "
  INSERT INTO users (username, email, password_hash)
  VALUES ('user2', 'user2@test.com', '\$2b\$12\$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5hhbXAGZFYFiu');
"

# 2. Login avec user2
TOKEN_USER2=$(curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "user2", "password": "password"}' | jq -r '.access_token')

# 3. Tenter d'accéder au document de admin
curl "http://localhost:8000/api/documents/${DOCUMENT_ID}/annotated-pdf" \
  -H "Authorization: Bearer $TOKEN_USER2"

# Résultat attendu : 403 Forbidden (si isolation activée) OU 404 Not Found
```

---

## Troubleshooting

### Problème : Aucun bbox extrait

**Symptômes** :
- `bbox IS NULL` pour tous les chunks
- Logs : "Failed to extract bbox for chunk X"

**Diagnostic** :
```bash
# Vérifier si Docling extrait bien les bbox
docker-compose logs ingestion-worker | grep -i "bbox\|prov"

# Tester manuellement l'extraction Docling
docker-compose run --rm rag-app python -c "
from docling.document_converter import DocumentConverter
converter = DocumentConverter()
result = converter.convert('/app/uploads/test.pdf')
for i, chunk in enumerate(result.document.iterate_items()):
    if hasattr(chunk, 'prov') and chunk.prov:
        print(f'Chunk {i}: has prov = True, bbox = {hasattr(chunk.prov[0], \"bbox\")}')
"
```

**Solution** :
- Vérifier que le PDF contient du texte vectoriel (pas seulement des images scannées)
- Vérifier la version de Docling : `pip show docling`
- Mettre à jour Docling si nécessaire : `pip install --upgrade docling`

### Problème : Coordonnées bbox incorrectes

**Symptômes** :
- Surlignages apparaissent au mauvais endroit
- Surlignages hors de la page

**Diagnostic** :
```bash
# Vérifier les valeurs bbox brutes
docker-compose exec postgres psql -U raguser -d ragdb -c "
  SELECT
    chunk_index,
    bbox->>'l' as left,
    bbox->>'t' as top,
    bbox->>'r' as right,
    bbox->>'b' as bottom,
    (metadata->>'page_number')::int as page
  FROM chunks
  WHERE document_id = '$DOCUMENT_ID'
  AND bbox IS NOT NULL
  LIMIT 5;
"

# Vérifier la conversion Docling → PyMuPDF
# Docling: bottom-left origin (0,0 = bas-gauche)
# PyMuPDF: top-left origin (0,0 = haut-gauche)
# Conversion: y_pymupdf = page_height - y_docling
```

**Solution** :
- Vérifier que `routes/documents.py:144-149` applique bien la conversion de coordonnées
- Tester avec différentes tailles de page

### Problème : PDF annoté ne s'ouvre pas

**Symptômes** :
- Erreur 500 dans le navigateur
- Logs : "Failed to open PDF: ..."

**Diagnostic** :
```bash
# Vérifier les logs de l'API
docker-compose logs ragfab-api | grep -i "annotated-pdf\|error"

# Vérifier que PyMuPDF est installé
docker-compose exec ragfab-api python -c "import fitz; print(fitz.__version__)"

# Vérifier que le fichier PDF source existe
docker-compose exec ragfab-api ls -la /app/uploads/
```

**Solution** :
- Installer PyMuPDF si manquant : `pip install PyMuPDF`
- Vérifier les permissions du répertoire `/app/uploads`
- Vérifier que `document.source` contient le bon chemin relatif

---

## Checklist de validation complète

### Backend ✅
- [ ] Migration 11 appliquée avec succès
- [ ] Colonne `bbox` existe dans table `chunks`
- [ ] Fonctions `get_chunks_for_annotation` et `get_chunks_with_bbox_for_page` créées
- [ ] chunker.py extrait les bbox (logs confirment)
- [ ] ingest.py sauvegarde les bbox en DB
- [ ] Chunks ont `bbox IS NOT NULL` (au moins 80% pour PDFs vectoriels)

### API ✅
- [ ] Route `/api/documents/{id}/annotated-pdf` accessible
- [ ] Route `/api/documents/{id}/chunks-bbox` retourne JSON valide
- [ ] PDF annoté généré sans erreur (HTTP 200)
- [ ] Chunks surlignés en jaune à la bonne position
- [ ] Plusieurs chunks surlignables simultanément
- [ ] Fallback gracieux pour documents sans bbox

### Frontend ✅
- [ ] Bouton "Voir dans PDF" visible dans DocumentViewModal
- [ ] Bouton responsive (texte masqué sur mobile)
- [ ] Clic ouvre PDF annoté dans nouvel onglet
- [ ] URL correcte : `/api/documents/{id}/annotated-pdf?chunk_ids={id}`
- [ ] Aucune erreur console JavaScript

### Performance ✅
- [ ] Génération PDF < 5s pour documents < 100 pages
- [ ] Génération PDF < 10s pour documents < 500 pages
- [ ] Pas de fuite mémoire (fichiers temporaires nettoyés)

### Sécurité ✅
- [ ] Authentification JWT requise pour accès PDF
- [ ] Isolation des documents par utilisateur (si applicable)
- [ ] Validation des UUIDs chunk_ids
- [ ] Pas de traversal path dans document.source

---

## Conclusion

Une fois tous les tests passés avec succès, la fonctionnalité de mise en évidence des chunks dans les PDFs est complètement opérationnelle.

**Améliorations futures possibles** :
- Cache des PDFs annotés pour réutilisation (Redis/filesystem)
- Couleurs personnalisables pour les surlignages (query param `color`)
- Mode "prévisualisation" inline dans le modal (iframe PDF.js)
- Export PDF annoté avec métadonnées (auteur, date de génération)
- Statistiques d'utilisation de la fonctionnalité (analytics)
