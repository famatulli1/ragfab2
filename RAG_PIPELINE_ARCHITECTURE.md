# Architecture Pipeline RAG - RAGFab

## Vue d'ensemble

RAGFab est un système RAG (Retrieval Augmented Generation) dual-provider optimisé pour le français, avec support d'images via VLM.

---

## 🔄 Pipeline d'Ingestion

### 1. Chargement de Documents

**Formats supportés**: PDF, DOCX, MD, TXT, HTML
**Taille maximale**: 100 MB par fichier
**Stockage**: Volume partagé `/app/uploads/{job_id}/`

### 2. Parsing de Documents

**Outil**: [Docling](https://github.com/DS4SD/docling) (IBM Research)
**Avantages**:
- Respect de la structure documentaire (titres, paragraphes, tableaux)
- Extraction automatique des images
- Support multi-format avec conversion PDF

### 3. Extraction d'Images (Optionnel)

**Activation**: `VLM_ENABLED=true`
**Modèle VLM**: OpenGVLab/InternVL3_5-8B (via API https://apivlm.mynumih.fr)
**Processus**:
1. Docling détecte les images dans les pages PDF
2. Extraction + sauvegarde PNG (`/app/uploads/images/`)
3. Appel VLM API pour description + OCR
4. Stockage métadonnées dans `document_images` table
5. Liaison avec chunks via `page_number`

**Performance**: ~10-15s par image

### 4. Chunking

**Stratégie principale**: Docling HybridChunker
**Paramètres**:
- `CHUNK_SIZE=1500` tokens
- `CHUNK_OVERLAP=200` tokens

**Caractéristiques**:
- Respect des frontières naturelles du document
- Préservation du contexte sémantique
- Fallback automatique sur SimpleChunker en cas d'erreur

**Fallback**: SimpleChunker (split sur `\n\n`)

### 5. Génération d'Embeddings

**Modèle**: `intfloat/multilingual-e5-large`
**Dimension**: 1024
**Service**: FastAPI dédié (port 8001)
**Batch processing**: 20 chunks par batch
**Timeout**: 90 secondes

**Avantages du modèle**:
- Optimisé multilingue (excellent français)
- Dense retrieval performant
- Taille modérée (1.1B paramètres)

### 6. Stockage Vectoriel

**Base de données**: PostgreSQL + pgvector
**Index**: HNSW (Hierarchical Navigable Small World)
**Distance**: Cosine similarity

**Tables principales**:
- `documents`: Métadonnées des documents
- `chunks`: Texte + embeddings (vector(1024))
- `document_images`: Images + descriptions VLM

---

## 🔍 Pipeline d'Interrogation

### 1. Reformulation de Question (Chocolatine avec tools uniquement)

**Détection de références contextuelles**:
- **Références fortes**: celle, celui, celles, ceux → reformulation systématique
- **Références moyennes**: ça, cela, ce, cette → si question <8 mots
- **Pronoms en début**: il, elle, ils, elles, y, en → si premier mot
- **Patterns**: "et celle", "et celui", "et ça"

**Processus**:
1. Détection référence → Appel Chocolatine API
2. Reformulation autonome avec contexte conversationnel
3. Question reformulée envoyée au RAG agent

### 2. Recherche Vectorielle

**Sans reranking** (`RERANKER_ENABLED=false`):
1. Question → Embedding (E5-Large)
2. Recherche similarité cosinus
3. Top-5 chunks directs → Contexte LLM

**Avec reranking** (`RERANKER_ENABLED=true`):
1. Question → Embedding (E5-Large)
2. Recherche vectorielle → Top-20 candidats
3. Reranking CrossEncoder → Score précis
4. Top-5 après reranking → Contexte LLM

### 3. Reranking (Optionnel)

**Modèle**: BAAI/bge-reranker-v2-m3
**Service**: FastAPI dédié (port 8002)
**Configuration**:
- `RERANKER_TOP_K=20` (candidats avant reranking)
- `RERANKER_RETURN_K=5` (résultats finaux)

**Cas d'usage recommandés**:
- Documentation technique/médicale/juridique
- Terminologie similaire avec nuances sémantiques
- Base documentaire >1000 documents
- Besoin de précision maximale

**Performance**:
- Latence additionnelle: +100-300ms
- Ressources: ~4GB RAM
- Amélioration pertinence: +20-30%

**Fallback gracieux**: Si échec reranker → Top-5 du vector search

### 4. Génération de Réponse

#### Mode 1: LLM avec Function Calling (`LLM_USE_TOOLS=true`)

**LLM utilisé**: Chocolatine-2-14B-Instruct-v2.0.3
**API**: Compatible OpenAI (vLLM proxy)
**Processus**:
1. Agent créé avec `tools=[search_knowledge_base_tool]`
2. **Pas d'historique passé** → Force l'appel d'outil
3. LLM appelle automatiquement `search_knowledge_base_tool()`
4. Recherche vectorielle exécutée
5. Sources stockées dans variable globale `_current_request_sources`
6. LLM génère réponse avec contexte
7. Sources affichées dans frontend

**Optimisation système prompt**:
- Définitions JSON explicites des outils dans le prompt
- Exemples d'utilisation correcte
- Règles absolues pour forcer l'appel d'outil
- Approche double: `tool_choice="required"` + JSON prompt

#### Mode 2: LLM sans tools (`LLM_USE_TOOLS=false`)

**Processus**:
1. Recherche vectorielle exécutée **avant** création agent
2. Contexte injecté manuellement dans system prompt
3. Historique conversationnel peut être inclus
4. LLM génère réponse sans appel d'outil

**Avantage**: Plus simple, compatible tout LLM
**Inconvénient**: Pas de recherche adaptative

---

## 🛠️ Configuration des Modèles

### Embeddings

```bash
EMBEDDINGS_API_URL=http://embeddings:8001
EMBEDDING_DIMENSION=1024
# Modèle: intfloat/multilingual-e5-large (1.1B paramètres)
```

### Reranker (Optionnel)

```bash
RERANKER_ENABLED=false  # true pour activer
RERANKER_API_URL=http://reranker:8002
RERANKER_MODEL=BAAI/bge-reranker-v2-m3
RERANKER_TOP_K=20
RERANKER_RETURN_K=5
```

### LLM Principal

```bash
LLM_API_URL=https://apigpt.mynumih.fr
LLM_API_KEY=your_api_key
LLM_MODEL_NAME=Chocolatine-2-14B-Instruct-v2.0.3  # vLLM proxy
LLM_USE_TOOLS=true  # Function calling activé
LLM_TIMEOUT=120.0
```

**Caractéristiques Chocolatine**:
- Modèle: 14B paramètres, optimisé pour le français
- Architecture: Compatible OpenAI API via vLLM
- Function calling: Support natif des outils
- Context window: 8K tokens

### VLM (Vision Language Model)

```bash
VLM_ENABLED=false  # true pour extraction d'images
VLM_API_URL=https://apivlm.mynumih.fr
VLM_MODEL_NAME=OpenGVLab/InternVL3_5-8B
VLM_TIMEOUT=60.0
```

---

## 📊 Workflow Complet

### Ingestion (Asynchrone via Worker)

```
Upload PDF → Validation (type, taille)
  ↓
Job créé (status='pending')
  ↓
Worker claim job (polling 3s)
  ↓
Docling parsing → Extraction structure + images
  ↓
HybridChunker (1500 tokens, overlap 200)
  ↓
Batch embeddings (20 chunks, E5-Large 1024d)
  ↓
Stockage PostgreSQL (chunks + embeddings)
  ↓
Si VLM activé: Images → API VLM → Description + OCR → DB
  ↓
Job completed (status='completed')
```

### Interrogation (Temps réel)

#### Avec Function Calling (Chocolatine)

```
Question utilisateur
  ↓
Détection référence contextuelle? → OUI → Reformulation Chocolatine
  ↓
Agent créé (tools, NO history)
  ↓
LLM appelle search_knowledge_base_tool()
  ↓
Embedding question (E5-Large)
  ↓
Recherche vectorielle (cosine similarity)
  ↓
Si reranker: Top-20 → CrossEncoder → Top-5
Sinon: Top-5 direct
  ↓
Sources → Variable globale _current_request_sources
  ↓
LLM génère réponse finale avec contexte
  ↓
Réponse + Sources + Images → Frontend
```

#### Sans Function Calling

```
Question utilisateur
  ↓
Recherche vectorielle immédiate
  ↓
Contexte injecté dans system prompt
  ↓
Agent créé (avec historique possible)
  ↓
LLM génère réponse
  ↓
Réponse + Sources → Frontend
```

---

## 🎯 Points Techniques Critiques

### PydanticAI & Function Calling

- **Ne jamais passer d'historique** quand on veut forcer tool calling
- Utiliser `run()` pas `run_stream()` pour execution automatique des tools
- Variable globale `_current_request_sources` nécessaire (ContextVar perdu en async)

### Chunking

- HybridChunker respecte structure sémantique (pas de coupure arbitraire)
- Overlap de 200 tokens pour préserver contexte entre chunks
- Fallback SimpleChunker sur `\n\n` (pas sur caractères)

### UTF-8 Handling

- PDFs contiennent souvent caractères invalides
- Nettoyage systématique: `.encode('utf-8', errors='replace').decode('utf-8')`

### Base de données

- Index HNSW pour recherche vectorielle rapide
- Dimension fixe: 1024 (changement = recréation table)
- Images liées aux chunks via `page_number`

---

## 📈 Performance

| Composant | Latence | Ressources |
|-----------|---------|------------|
| Embedding (1 chunk) | ~50ms | 4-8GB RAM |
| Vector search | ~10-50ms | Index HNSW |
| Reranker (20→5) | +100-300ms | ~4GB RAM |
| VLM (1 image) | ~10-15s | API externe |
| LLM génération | 2-10s | API externe |

**Total requête RAG**:
- Sans reranking: ~2-10s
- Avec reranking: ~2.5-11s
- Avec images: Pré-calculé (pas d'impact runtime)

---

## 🔐 Sécurité & Multi-utilisateur

- JWT authentication sur toutes routes frontend
- Conversations isolées par `user_id`
- Admin panel (RBAC) pour gestion utilisateurs
- Mot de passe obligatoire au premier login
- Validation force mot de passe (8 chars, uppercase, lowercase, digit)

---

## 🚀 Déploiement

**Architecture**: Docker Compose + Coolify
**Services**:
- PostgreSQL + pgvector
- Embeddings API (E5-Large)
- Reranker API (BGE-M3) - optionnel
- Web API (FastAPI)
- Frontend (React + Vite)
- Ingestion Worker (background processing)

**Réseau**: Traefik reverse proxy avec labels pour routing automatique



Matraquer qu'il faut des moyens, pour industrialiser et répondre à la conformité et la qualité
Comment tu arrives à ca , dans d'autres usages


curl -X POST https://backend-nava.lab-numihfrance.fr/api/reports/test-email \
    -H "Content-Type: application/json" \
    -d '{"to":"famatulli@gmail.com"}'
