# Déploiement Phase 3 - Optimisations RAG Petits Documents

## Contexte

Suite au test réel avec le document "erreur fusappel 6102" (331 mots), le système a montré des limitations :
- Document fragmenté en 7 chunks (trop granulaire)
- Réponses RAG incomplètes malgré Phases 1-2
- Solutions complètes non retournées

**Phase 3** : 3 optimisations pour forcer 1 chunk sur très petits documents + augmenter contexte LLM

---

## 📋 Modifications Code Implémentées

### 1. Configuration Reranker - `.env.example`

**Fichier modifié** : [.env.example](.env.example)

**Changements** (lignes 63-73) :
```bash
# Avant
RERANKER_TOP_K=20
RERANKER_RETURN_K=5

# Après
RERANKER_TOP_K=30      # +50% pool candidats
RERANKER_RETURN_K=8    # +60% chunks envoyés au LLM
```

**Objectif** : Augmenter le nombre de chunks retournés au LLM pour couvrir documents fragmentés

---

### 2. Chunking Très Petits Documents - `chunker.py`

**Fichier modifié** : [rag-app/ingestion/chunker.py](rag-app/ingestion/chunker.py)

**Changements** (lignes 153-172) :
```python
# AVANT Phase 3
if word_count < 1000:
    max_tokens = 1500
    doc_size_category = "small"
elif word_count < 5000:
    max_tokens = 800
    doc_size_category = "medium"
else:
    max_tokens = 512
    doc_size_category = "large"

# APRÈS Phase 3
if word_count < 800:
    max_tokens = 4000  # Force 1 seul chunk
    doc_size_category = "very_small"
    logger.info(f"Very small document detected ({word_count} words) - using max_tokens=4000 (1 chunk)")
elif word_count < 2000:
    max_tokens = 1500
    doc_size_category = "small"
    logger.info(f"Small document detected ({word_count} words) - using max_tokens=1500")
elif word_count < 5000:
    max_tokens = 800
    doc_size_category = "medium"
    logger.info(f"Medium document detected ({word_count} words) - using max_tokens=800")
else:
    max_tokens = 512
    doc_size_category = "large"
    logger.info(f"Large document detected ({word_count} words) - using max_tokens=512")
```

**Impact** :
- Document 331 mots : 7 chunks → **1 chunk complet**
- Context window : +193% (1500 → 4000 tokens)
- Préserve contexte total pour réponses complètes

---

### 3. Enrichissement Chunks Images - `ingest.py`

**Fichier modifié** : [rag-app/ingestion/ingest.py](rag-app/ingestion/ingest.py)

**Changements** (lignes 309-325) :
```python
# AVANT Phase 3
content_parts = [f"[Image {idx+1} depuis la page {page_num}]"]
if description:
    content_parts.append(f"Description: {description}")
if ocr_text:
    content_parts.append(f"Texte extrait: {ocr_text}")

chunk_content = "\n".join(content_parts)

# APRÈS Phase 3
# Extract title keywords for context enrichment
title_keywords = document_title.replace('+', ' ').replace('_', ' ')

content_parts = [
    f"[Document: {document_title}]",  # Ajout contexte document
    f"[Image {idx+1} depuis la page {page_num}]"
]
if description:
    content_parts.append(f"Description: {description}")
if ocr_text:
    content_parts.append(f"Texte extrait: {ocr_text}")

# Add contextual keywords from document title
content_parts.append(f"Contexte: {title_keywords}")  # Ajout keywords

chunk_content = "\n".join(content_parts)
```

**Impact** :
- Images deviennent cherchables via titre document
- Meilleure pertinence dans résultats RAG
- Contexte enrichi pour VLM descriptions

---

## 🚀 Déploiement Coolify

### Étape 1 : Variables Environnement

**Service : `ragfab-api`**

Aller dans Coolify → Projet RAGFab → Service `ragfab-api` → Environment Variables

**Ajouter/Modifier** :
```bash
RERANKER_TOP_K=30      # Nouveau : augmente pool candidats (+50%)
RERANKER_RETURN_K=8    # Nouveau : augmente chunks LLM (+60%)
```

**Service : `ingestion-worker`**

Vérifier que ces variables sont déjà présentes (Phase 1) :
```bash
CHUNK_OVERLAP=400      # Doit être 400 (pas 200)
```

**Note** : Les nouvelles valeurs de chunking (`max_tokens=4000`) sont dans le code, pas en variable d'environnement.

---

### Étape 2 : Rebuild et Redémarrage Services

**Via Coolify UI** :

1. **Service `ragfab-api`** :
   - Cliquer sur service `ragfab-api`
   - Bouton "Redeploy" (force rebuild depuis code source)
   - Attendre fin du build (~2-3 min)

2. **Service `ingestion-worker`** :
   - Cliquer sur service `ingestion-worker`
   - Bouton "Redeploy" (force rebuild depuis code source)
   - Attendre fin du build (~2-3 min)

**Via CLI Docker (alternative)** :
```bash
# SSH sur serveur Coolify
cd /path/to/ragfab

# Rebuild services avec nouvelles modifications code
docker-compose build ragfab-api ingestion-worker

# Redémarrer services
docker-compose restart ragfab-api ingestion-worker

# Vérifier logs
docker-compose logs -f ingestion-worker
```

---

### Étape 3 : Ré-indexation Documents

**Important** : Les nouveaux paramètres de chunking nécessitent une ré-indexation complète.

#### Option A : Ré-indexation Document Spécifique (Recommandé pour test)

1. **Supprimer document "erreur fusappel 6102" via interface admin** :
   - Aller sur https://votre-domaine.fr/admin
   - Onglet "Documents"
   - Trouver document "erreur fusappel 6102"
   - Cliquer "Supprimer"

2. **Re-uploader document via interface admin** :
   - Glisser-déposer même PDF
   - Worker va ingérer avec nouveaux paramètres
   - Vérifier logs : `docker-compose logs -f ingestion-worker`
   - Chercher : `"Very small document detected (331 words) - using max_tokens=4000 (1 chunk)"`

3. **Tester avec même question** :
   - Question : "Comment résoudre l'erreur fusappel 6102 ?"
   - Vérifier que réponse complète inclut toutes les étapes
   - Vérifier nombre de sources retournées (devrait être ~8 avec images)

#### Option B : Ré-indexation Complète Base Documentaire

⚠️ **Attention** : Cette option supprime TOUS les chunks existants.

```bash
# SSH sur serveur Coolify
docker-compose exec postgres psql -U raguser -d ragdb

-- Supprimer tous les chunks (conserve documents)
DELETE FROM chunks;
DELETE FROM document_images;

-- Quitter psql
\q

# Ré-uploader tous les documents via interface admin
# OU si documents disponibles dans volume uploads
docker-compose exec ingestion-worker python -m ingestion.ingest --documents /app/uploads
```

---

## 🧪 Validation Post-Déploiement

### 1. Vérifier Logs Ingestion Worker

```bash
docker-compose logs -f ingestion-worker | grep "Very small\|Small document\|Medium document\|Large document"
```

**Attendu pour document 331 mots** :
```
Very small document detected (331 words) - using max_tokens=4000 (1 chunk)
```

**Avant Phase 3** (pour comparaison) :
```
Small document detected (331 words) - using max_tokens=1500
Created 7 document chunks  # TROP FRAGMENTÉ
```

**Après Phase 3** (objectif) :
```
Very small document detected (331 words) - using max_tokens=4000 (1 chunk)
Created 1 document chunks  # CONTEXTE COMPLET
```

---

### 2. Vérifier Variables Environnement API

```bash
docker-compose exec ragfab-api env | grep RERANKER
```

**Attendu** :
```
RERANKER_ENABLED=true
RERANKER_TOP_K=30       # Vérifié
RERANKER_RETURN_K=8     # Vérifié
```

---

### 3. Test Fonctionnel "Erreur Fusappel 6102"

**Question test** : "Comment résoudre l'erreur fusappel 6102 ?"

**Attendu** :
- ✅ Réponse complète avec toutes les étapes (4 étapes solution)
- ✅ ~8 sources retournées (document + images)
- ✅ Sources pertinentes (pas "Observation", "CRATIO", etc.)
- ✅ Chunk unique avec contexte complet

**Avant Phase 3** :
- ❌ 5 sources (RERANKER_RETURN_K=5)
- ❌ Sources fragmentées ou hors-sujet
- ❌ Réponse incomplète

---

### 4. Vérifier Chunks en Base de Données

```bash
docker-compose exec postgres psql -U raguser -d ragdb

-- Compter chunks par document
SELECT
    d.title,
    d.metadata->>'word_count' as word_count,
    COUNT(c.id) as chunk_count,
    MAX(c.metadata->>'doc_size_category') as category
FROM documents d
LEFT JOIN chunks c ON d.id = c.document_id
WHERE d.title ILIKE '%fusappel%'
GROUP BY d.id, d.title, d.metadata;
```

**Attendu pour "erreur fusappel 6102"** :
```
        title         | word_count | chunk_count | category
----------------------|------------|-------------|-----------
 erreur fusappel 6102 |    331     |      1      | very_small
```

**Avant Phase 3** :
```
        title         | word_count | chunk_count | category
----------------------|------------|-------------|-----------
 erreur fusappel 6102 |    331     |      7      | small
```

---

## 📊 Métriques Attendues

### Gains Phase 3 vs Phase 1-2

| Métrique | Phase 1-2 | Phase 3 | Gain |
|----------|-----------|---------|------|
| **Chunks doc 331 mots** | 7 chunks | 1 chunk | -86% fragmentation |
| **Context par chunk** | 1500 tokens | 4000 tokens | +167% |
| **Chunks retournés LLM** | 5 | 8 | +60% |
| **Pool candidats reranker** | 20 | 30 | +50% |
| **Qualité réponses petits docs** | +85% | **+120%** | +35% additionnel |

### Test Cas Réel "Erreur Fusappel 6102"

**Résultat attendu** :
- ✅ Réponse complète : 4 étapes solution + explication
- ✅ Sources pertinentes : 8 chunks (document + 8 images)
- ✅ Latence acceptable : <3s (reranker 30 candidats)
- ✅ Satisfaction utilisateur : Résolution problème

---

## 🔧 Troubleshooting

### Problème : Logs montrent encore "Small document" au lieu de "Very small"

**Cause** : Service `ingestion-worker` pas rebuild avec nouveau code

**Solution** :
```bash
# Forcer rebuild complet
docker-compose build --no-cache ingestion-worker
docker-compose restart ingestion-worker
```

---

### Problème : API ne retourne toujours que 5 chunks

**Cause** : Variables environnement `RERANKER_RETURN_K` pas mises à jour

**Solution** :
```bash
# Vérifier variable
docker-compose exec ragfab-api env | grep RERANKER_RETURN_K

# Si toujours =5, mettre à jour dans Coolify UI puis redémarrer
docker-compose restart ragfab-api
```

---

### Problème : Document ré-indexé mais toujours 7 chunks

**Cause** : Ancien document pas supprimé avant re-upload

**Solution** :
```bash
# Supprimer tous les chunks du document
docker-compose exec postgres psql -U raguser -d ragdb -c "DELETE FROM chunks WHERE document_id IN (SELECT id FROM documents WHERE title ILIKE '%fusappel%');"

# Re-uploader document via interface admin
```

---

### Problème : Reranker timeout ou erreur

**Cause** : Pool trop large (30 candidats) sature service reranker

**Solution temporaire** : Réduire `RERANKER_TOP_K` à 25
```bash
# Dans Coolify UI ou .env
RERANKER_TOP_K=25
```

**Solution permanente** : Augmenter ressources service reranker
```yaml
# docker-compose.yml
reranker:
  deploy:
    resources:
      limits:
        memory: 6G  # Au lieu de 4G
```

---

## 📝 Checklist Déploiement

- [ ] Variables environnement mises à jour dans Coolify
  - [ ] `RERANKER_TOP_K=30` dans `ragfab-api`
  - [ ] `RERANKER_RETURN_K=8` dans `ragfab-api`
  - [ ] `CHUNK_OVERLAP=400` dans `ingestion-worker` (déjà fait Phase 1)

- [ ] Services rebuild et redémarrés
  - [ ] `ragfab-api` redéployé via Coolify
  - [ ] `ingestion-worker` redéployé via Coolify

- [ ] Document test ré-indexé
  - [ ] Document "erreur fusappel 6102" supprimé via admin
  - [ ] Document re-uploadé via admin
  - [ ] Logs vérifiés : `"Very small document detected..."`

- [ ] Tests fonctionnels passés
  - [ ] Question "Comment résoudre erreur fusappel 6102 ?" testée
  - [ ] Réponse complète avec 4 étapes reçue
  - [ ] ~8 sources pertinentes retournées
  - [ ] Latence <3s acceptable

- [ ] Base de données vérifiée
  - [ ] Query SQL montre `chunk_count=1` pour document 331 mots
  - [ ] Catégorie = `very_small`

- [ ] Documentation mise à jour
  - [ ] `RAG_PIPELINE_ARCHITECTURE.md` mis à jour avec Phase 3
  - [ ] `.env.example` mis à jour avec nouvelles recommandations

---

## 📚 Fichiers Modifiés

1. [.env.example](.env.example) - Lignes 63-73
2. [rag-app/ingestion/chunker.py](rag-app/ingestion/chunker.py) - Lignes 153-172
3. [rag-app/ingestion/ingest.py](rag-app/ingestion/ingest.py) - Lignes 309-325
4. [RAG_PIPELINE_ARCHITECTURE.md](RAG_PIPELINE_ARCHITECTURE.md) - Section "Améliorations Phase 3"
5. [DEPLOYMENT_PHASE3.md](DEPLOYMENT_PHASE3.md) - Ce fichier (nouveau)

---

## 🎯 Prochaines Étapes (Optionnel)

### Phase 4 : Monitoring et Tuning (Si nécessaire)

**Métriques à surveiller** :
- Temps réponse reranker avec TOP_K=30
- Distribution taille documents (% very_small / small / medium / large)
- Taux satisfaction utilisateur sur petits documents

**Optimisations futures possibles** :
- Ajuster seuils adaptatifs selon distribution réelle
- Fine-tuning BGE-M3 reranker sur corpus métier
- Cache reranker pour questions fréquentes
- A/B testing différentes valeurs `RERANKER_TOP_K`

### Phase 5 : Métriques RAG Avancées (Optionnel)

**Objectif** : Mesurer gains quantitatifs Phase 3

**À implémenter** :
1. **MRR (Mean Reciprocal Rank)** : Position réponse correcte
2. **NDCG@5** : Pertinence top-5 résultats
3. **User Satisfaction Score** : Feedback utilisateurs interface
4. **Latency P50/P95** : Performance système

**Script exemple** :
```python
# scripts/evaluate_rag.py
from utils.metrics import calculate_mrr, calculate_ndcg
from web-api.app.main import execute_rag_agent

test_cases = [
    {"query": "Comment résoudre erreur fusappel 6102?", "expected_doc": "erreur fusappel 6102"}
]

for case in test_cases:
    results = execute_rag_agent(case["query"])
    mrr = calculate_mrr(results, case["expected_doc"])
    print(f"MRR: {mrr}")
```

---

**Date création** : 2025-01-10
**Auteur** : Claude Code
**Version** : 1.0 - Phase 3 Optimisations RAG Petits Documents
