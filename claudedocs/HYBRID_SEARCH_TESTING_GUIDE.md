# Guide de Test - Hybrid Search (BM25 + Vector)

## Vue d'ensemble

Ce guide décrit les étapes pour valider l'implémentation complète de Hybrid Search dans RAGFab.

## Pré-requis

- Docker et docker-compose installés
- Projet RAGFab avec base de données PostgreSQL
- Documents ingérés dans la base (au moins 1 document pour tester)

---

## Étape 1: Appliquer la migration SQL

### 1.1 Vérifier que PostgreSQL est actif

```bash
docker-compose ps postgres
```

**Attendu**: Container `ragfab-postgres` en état `Up`

### 1.2 Appliquer la migration

```bash
docker-compose exec postgres psql -U raguser -d ragdb \
  -f /docker-entrypoint-initdb.d/10_hybrid_search.sql
```

**Attendu**: Messages sans erreur, notamment:
```
ALTER TABLE
CREATE INDEX
CREATE FUNCTION
CREATE FUNCTION
COMMENT
```

### 1.3 Vérifier la migration

```bash
docker-compose exec postgres psql -U raguser -d ragdb -c "\d chunks"
```

**Attendu**: Colonne `content_tsv` visible dans le schéma:
```
 content_tsv | tsvector |
```

```bash
docker-compose exec postgres psql -U raguser -d ragdb \
  -c "SELECT indexname FROM pg_indexes WHERE tablename = 'chunks' AND indexname = 'idx_chunks_content_tsv';"
```

**Attendu**:
```
     indexname
------------------------
 idx_chunks_content_tsv
```

```bash
docker-compose exec postgres psql -U raguser -d ragdb \
  -c "\df match_chunks_hybrid"
```

**Attendu**: Fonction listée avec signature correcte

---

## Étape 2: Vérifier les tsvectors

### 2.1 Compter les chunks avec tsvector

```bash
docker-compose exec postgres psql -U raguser -d ragdb -c \
  "SELECT COUNT(*) as total_chunks,
          COUNT(content_tsv) as chunks_with_tsvector
   FROM chunks;"
```

**Attendu**: `chunks_with_tsvector` = `total_chunks`

Si pas égal, exécuter:

```bash
docker-compose exec postgres psql -U raguser -d ragdb -c \
  "UPDATE chunks SET content_tsv = to_tsvector('french', content) WHERE content_tsv IS NULL;"
```

### 2.2 Tester la recherche keyword

```bash
docker-compose exec postgres psql -U raguser -d ragdb -c \
  "SELECT LEFT(content, 100) as preview,
          ts_rank_cd(content_tsv, to_tsquery('french', 'télétravail'), 32) AS score
   FROM chunks
   WHERE content_tsv @@ to_tsquery('french', 'télétravail')
   ORDER BY score DESC
   LIMIT 3;"
```

**Attendu**: Résultats contenant "télétravail" avec scores BM25

---

## Étape 3: Configuration backend

### 3.1 Vérifier le module hybrid_search.py

```bash
cat web-api/app/hybrid_search.py | head -n 20
```

**Attendu**: Fichier existe avec imports correctes:
```python
import re
import logging
from typing import List, Dict, Optional
from uuid import UUID

from . import database
```

### 3.2 Activer Hybrid Search dans .env

Éditer `.env`:

```bash
# Hybrid Search Configuration
HYBRID_SEARCH_ENABLED=true
```

### 3.3 Rebuild API

```bash
docker-compose build ragfab-api
docker-compose up -d ragfab-api
```

### 3.4 Vérifier les logs

```bash
docker-compose logs -f ragfab-api | grep -i hybrid
```

**Attendu** (au démarrage):
```
INFO - Module hybrid_search chargé avec succès
```

---

## Étape 4: Tests fonctionnels backend

### 4.1 Test de preprocess_query_for_tsquery

Créer un fichier de test Python temporaire:

```python
# test_preprocessing.py
import sys
sys.path.insert(0, '/app')

from app.hybrid_search import preprocess_query_for_tsquery

test_queries = [
    "Quelle est la politique de télétravail ?",
    "procédure RTT congés payés",
    "Comment fonctionne PeopleDoc ?"
]

for query in test_queries:
    processed = preprocess_query_for_tsquery(query)
    print(f"'{query}' → '{processed}'")
```

Exécuter dans le container:

```bash
docker-compose exec ragfab-api python -c "
import sys
sys.path.insert(0, '/app')
from app.hybrid_search import preprocess_query_for_tsquery

queries = [
    'Quelle est la politique de télétravail ?',
    'procédure RTT congés payés',
    'Comment fonctionne PeopleDoc ?'
]

for query in queries:
    processed = preprocess_query_for_tsquery(query)
    print(f'{query} → {processed}')
"
```

**Attendu**:
```
Quelle est la politique de télétravail ? → politique & télétravail
procédure RTT congés payés → procédure & RTT & congés & payés
Comment fonctionne PeopleDoc ? → fonctionne & PeopleDoc
```

### 4.2 Test de adaptive_alpha

```bash
docker-compose exec ragfab-api python -c "
import sys
sys.path.insert(0, '/app')
from app.hybrid_search import adaptive_alpha

queries = {
    'procédure RTT': 0.3,
    'logiciel PeopleDoc': 0.3,
    'pourquoi favoriser le télétravail ?': 0.7,
    'comment activer bluetooth': 0.7,
    'télétravail': 0.4,
    'politique de télétravail de l entreprise': 0.5
}

for query, expected in queries.items():
    calculated = adaptive_alpha(query)
    status = '✓' if calculated == expected else '✗'
    print(f'{status} {query} → alpha={calculated} (attendu={expected})')
"
```

**Attendu**: Tous les tests avec ✓

---

## Étape 5: Tests frontend

### 5.1 Rebuild frontend

```bash
docker-compose build ragfab-frontend
docker-compose up -d ragfab-frontend
```

### 5.2 Accéder à l'interface

Ouvrir http://localhost:3000

### 5.3 Vérifier le composant HybridSearchToggle

Dans l'interface de chat:

**Attendu**: Toggle "Recherche Hybride (Vector + Mots-clés)" visible dans le header

**Actions**:
1. Cliquer sur l'icône ℹ️ (HelpCircle)
   - **Attendu**: Panel d'aide s'affiche expliquant hybrid search
2. Activer le toggle (cocher la case)
   - **Attendu**: Bouton ⚙️ (Settings) apparaît
3. Cliquer sur ⚙️
   - **Attendu**: Panel avec slider alpha apparaît
4. Bouger le slider
   - **Attendu**:
     - α = 0.0-0.3 → "🔤 Privilégie mots-clés"
     - α = 0.3-0.7 → "⚖️ Équilibré"
     - α = 0.7-1.0 → "🧠 Privilégie sémantique"
5. Désactiver puis réactiver
   - **Attendu**: Settings persistent (localStorage)

---

## Étape 6: Tests de recherche end-to-end

### 6.1 Requêtes avec acronymes (alpha=0.3 attendu)

**Test**: "procédure RTT"

**Actions**:
1. Activer Hybrid Search
2. Envoyer la question
3. Observer les logs backend

```bash
docker-compose logs -f ragfab-api | grep -A 5 "Hybrid search"
```

**Attendu**:
```
🔀 Hybrid search: query='procédure RTT' → tsquery='procédure & RTT', alpha=0.30, k=5
INFO - Acronyme détecté, alpha=0.3 (keyword bias)
✅ Hybrid search: 5 résultats | Scores moyens - Vector: 0.XXX, BM25: 0.XXX, Combined: 0.XXXX
```

**Vérification**: Résultats doivent contenir explicitement "RTT"

### 6.2 Requêtes avec noms propres (alpha=0.3 attendu)

**Test**: "logiciel PeopleDoc"

**Attendu**:
```
INFO - Nom propre détecté (['PeopleDoc']), alpha=0.3 (keyword bias)
```

**Vérification**: Résultats doivent mentionner "PeopleDoc"

### 6.3 Questions conceptuelles (alpha=0.7 attendu)

**Test**: "pourquoi favoriser le télétravail ?"

**Attendu**:
```
INFO - Question conceptuelle détectée, alpha=0.7 (semantic bias)
```

**Vérification**: Résultats peuvent être plus larges sémantiquement

### 6.4 Requêtes courtes (alpha=0.4 attendu)

**Test**: "télétravail"

**Attendu**:
```
INFO - Question courte (1 mots), alpha=0.4 (léger keyword bias)
```

### 6.5 Requêtes générales (alpha=0.5 attendu)

**Test**: "politique de télétravail de l'entreprise"

**Attendu**:
```
INFO - Alpha par défaut=0.5 (équilibré)
```

---

## Étape 7: Comparaison Vector vs Hybrid

### 7.1 Test avec Hybrid OFF

1. Désactiver toggle Hybrid Search
2. Envoyer: "politique télétravail"
3. Noter les 3 premiers résultats

### 7.2 Test avec Hybrid ON

1. Activer toggle Hybrid Search
2. Envoyer la même question: "politique télétravail"
3. Noter les 3 premiers résultats

### 7.3 Analyse comparative

**Attendu**:
- Hybrid devrait retourner des résultats plus pertinents contenant explicitement les termes
- Les chunks peuvent différer (meilleur matching keyword)
- Score combined_score devrait être cohérent

---

## Étape 8: Tests de régression

### 8.1 Vérifier que la recherche vectorielle classique fonctionne

1. Désactiver Hybrid Search (toggle OFF)
2. Envoyer plusieurs questions
3. Vérifier que les réponses sont cohérentes

**Attendu**: Aucune régression, vector search fonctionne comme avant

### 8.2 Vérifier le reranking avec Hybrid

Si `RERANKER_ENABLED=true`:

1. Activer à la fois Reranking et Hybrid Search
2. Envoyer une question complexe
3. Vérifier logs

**Attendu**:
```
🔀 Hybrid search: ... → top-20 candidats
🔄 Reranking avec BGE-reranker-v2-m3 → top-5 finaux
```

---

## Étape 9: Tests de performance

### 9.1 Mesurer la latence

Avec Hybrid OFF:

```bash
curl -X POST http://localhost:8000/api/conversations/{conv_id}/messages \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"content": "politique télétravail"}' \
  -w "\nTemps total: %{time_total}s\n"
```

Avec Hybrid ON (activer dans .env):

```bash
# Même requête
```

**Attendu**:
- Latence additionnelle < 100ms
- Pas d'erreurs

### 9.2 Tester avec charge

Envoyer 10 requêtes consécutives, observer:

```bash
docker-compose logs -f ragfab-api | grep "Hybrid search"
```

**Attendu**: Pas de timeouts, pas d'erreurs de connexion DB

---

## Étape 10: Validation des résultats

### 10.1 Critères de succès

✅ Migration SQL appliquée sans erreur
✅ Tous les chunks ont un tsvector
✅ Index GIN créé
✅ Fonctions PostgreSQL existent
✅ Backend charge le module hybrid_search
✅ HYBRID_SEARCH_ENABLED=true active la fonctionnalité
✅ Frontend affiche le toggle
✅ Alpha adaptatif fonctionne correctement
✅ Recherches retournent des résultats pertinents
✅ Logs montrent les scores (vector, BM25, combined)
✅ Pas de régression sur recherche vectorielle classique

### 10.2 Métriques à surveiller

**Qualité**:
- Recall@5 amélioré de +15-25% (estimation)
- Résultats contenant explicitement les termes recherchés
- Moins de faux positifs sémantiques

**Performance**:
- Latence additionnelle < 100ms
- Pas de timeouts
- CPU/RAM stable

---

## Dépannage

### Problème: "Function match_chunks_hybrid does not exist"

**Solution**: Réappliquer migration SQL

```bash
docker-compose exec postgres psql -U raguser -d ragdb \
  -f /docker-entrypoint-initdb.d/10_hybrid_search.sql
```

### Problème: "Column content_tsv does not exist"

**Solution**: Migration non appliquée, voir Étape 1

### Problème: Aucun résultat keyword

**Vérifier**:

```bash
docker-compose exec postgres psql -U raguser -d ragdb -c \
  "SELECT COUNT(*) FROM chunks WHERE content_tsv IS NOT NULL;"
```

Si 0, exécuter:

```bash
docker-compose exec postgres psql -U raguser -d ragdb -c \
  "UPDATE chunks SET content_tsv = to_tsvector('french', content);"
```

### Problème: "Module hybrid_search not found"

**Solution**: Rebuild API

```bash
docker-compose build ragfab-api
docker-compose up -d ragfab-api
```

### Problème: Toggle non visible

**Solution**: Rebuild frontend

```bash
docker-compose build ragfab-frontend
docker-compose up -d ragfab-frontend
```

Vider cache navigateur (Ctrl+Shift+R)

---

## Commandes utiles

### Logs en temps réel

```bash
# API logs (voir hybrid search en action)
docker-compose logs -f ragfab-api | grep -i hybrid

# Frontend logs
docker-compose logs -f ragfab-frontend

# PostgreSQL logs
docker-compose logs -f postgres
```

### Statistiques DB

```bash
docker-compose exec postgres psql -U raguser -d ragdb -c "
  SELECT
    COUNT(*) as total_chunks,
    COUNT(content_tsv) as chunks_with_tsvector,
    COUNT(CASE WHEN content_tsv IS NOT NULL THEN 1 END) * 100.0 / COUNT(*) as percentage
  FROM chunks;
"
```

### Test direct de la fonction SQL

```bash
docker-compose exec postgres psql -U raguser -d ragdb -c "
  SELECT id, similarity, bm25_score, combined_score
  FROM match_chunks_hybrid(
    (SELECT embedding FROM chunks LIMIT 1),
    'télétravail politique',
    5,
    0.5,
    false
  )
  LIMIT 3;
"
```

---

## Conclusion

Une fois tous les tests passés, Hybrid Search est opérationnel. Les utilisateurs peuvent:

1. **Activer/Désactiver** le toggle selon leurs besoins
2. **Ajuster alpha** pour optimiser selon le type de question
3. **Bénéficier automatiquement** de l'alpha adaptatif sans configuration

**Impact attendu**:
- +15-25% Recall@5
- Meilleure précision sur acronymes et noms propres
- Résultats plus pertinents pour questions courtes
- Flexibilité entre recherche sémantique et mots-clés
