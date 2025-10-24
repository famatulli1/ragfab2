# Documentation Technique de la Pipeline RAG - RAGFab

**Version**: 1.0
**Date**: 2025-01-24
**Auteur**: Documentation générée par analyse du codebase

---

## Table des Matières

1. [Vue d'ensemble](#1-vue-densemble)
2. [Architecture générale](#2-architecture-générale)
3. [Pipeline d'ingestion de documents](#3-pipeline-dingestion-de-documents)
4. [Pipeline de recherche vectorielle](#4-pipeline-de-recherche-vectorielle)
5. [Pipeline de génération de réponse](#5-pipeline-de-génération-de-réponse)
6. [Flux de données complet](#6-flux-de-données-complet)
7. [Configuration et optimisation](#7-configuration-et-optimisation)
8. [Points critiques et pièges](#8-points-critiques-et-pièges)

---

## 1. Vue d'ensemble

RAGFab est un système RAG (Retrieval Augmented Generation) dual-provider optimisé pour le français, avec support de:
- **Providers LLM**: Mistral API (function calling), Chocolatine (vLLM local), tout provider compatible OpenAI
- **Embeddings**: E5-Large multilingue (1024 dimensions)
- **Reranking optionnel**: BGE-reranker-v2-m3 (CrossEncoder)
- **Base vectorielle**: PostgreSQL + PGVector
- **Interface**: Web (React) et CLI

### Caractéristiques clés

- ✅ **Multi-format**: PDF, DOCX, PPTX, XLSX, HTML, MD, TXT, Audio (MP3, WAV, etc.)
- ✅ **Extraction d'images**: Vision Language Model (VLM) pour OCR et description
- ✅ **Chunking intelligent**: Docling HybridChunker (respect de la structure documentaire)
- ✅ **Reranking optionnel**: Amélioration de +20-30% de la pertinence
- ✅ **Jobs asynchrones**: Worker dédié pour l'ingestion sans bloquer l'API
- ✅ **Dual-mode**: Function calling automatique OU injection manuelle de contexte

---

## 2. Architecture générale

### Diagramme de composants

```mermaid
graph TB
    subgraph "Frontend (React)"
        UI[Interface Web]
    end

    subgraph "Backend Services"
        API[FastAPI Web API<br/>Port: 8000]
        WORKER[Ingestion Worker<br/>Async Processing]
    end

    subgraph "Intelligence Services"
        EMB[Embeddings API<br/>E5-Large - Port: 8001]
        RERANK[Reranker API<br/>BGE-M3 - Port: 8002]
        VLM[VLM API<br/>Image Analysis]
    end

    subgraph "LLM Providers"
        MISTRAL[Mistral API<br/>Function Calling]
        CHOCO[Chocolatine vLLM<br/>Manual Injection]
        GENERIC[Generic OpenAI-compatible<br/>Ollama, LiteLLM, etc.]
    end

    subgraph "Storage"
        PG[(PostgreSQL<br/>+ PGVector)]
        VOL[/Shared Volume<br/>/app/uploads/]
    end

    UI -->|Upload Document| API
    UI -->|Ask Question| API
    API -->|Create Job| PG
    WORKER -->|Poll Jobs| PG
    WORKER -->|Process| VOL
    WORKER -->|Generate Embeddings| EMB
    WORKER -->|Extract Images| VLM
    WORKER -->|Save Chunks| PG
    API -->|Search Query| EMB
    API -->|Vector Search| PG
    API -->|Rerank| RERANK
    API -->|Generate Answer| MISTRAL
    API -->|Generate Answer| CHOCO
    API -->|Generate Answer| GENERIC
```

### Stack technique

**Backend**:
- FastAPI (Python 3.11+)
- PydanticAI (agent framework)
- asyncpg (PostgreSQL async)
- Docling (document parsing + chunking)

**Base de données**:
- PostgreSQL 15+
- Extension PGVector (similarité vectorielle)
- IVFFlat index (optimisation recherche)

**Services IA**:
- Embeddings: `intfloat/multilingual-e5-large` (1024 dim)
- Reranker: `BAAI/bge-reranker-v2-m3` (CrossEncoder)
- VLM: `OpenGVLab/InternVL3_5-8B` (vision)

---

## 3. Pipeline d'ingestion de documents

### 3.1 Vue d'ensemble du flux

```mermaid
sequenceDiagram
    participant User
    participant WebUI
    participant API
    participant DB
    participant Worker
    participant Docling
    participant VLM
    participant Embeddings

    User->>WebUI: Upload document
    WebUI->>API: POST /api/documents/upload
    API->>DB: Create ingestion_job (status=pending)
    API->>WebUI: Return job_id
    WebUI->>WebUI: Poll job status (every 2s)

    Worker->>DB: Poll pending jobs (every 3s)
    Worker->>DB: Claim job (status=processing)
    Worker->>Docling: Parse document
    Docling-->>Worker: DoclingDocument + images

    alt VLM enabled
        Worker->>VLM: Extract & describe images
        VLM-->>Worker: Image descriptions + OCR
    end

    Worker->>Worker: Chunk document (HybridChunker)
    Worker->>Worker: Create synthetic image chunks
    Worker->>Embeddings: Batch embed chunks (20/batch)
    Embeddings-->>Worker: Embeddings (1024-dim vectors)
    Worker->>DB: Save document + chunks + images
    Worker->>DB: Update job (status=completed)
    WebUI->>API: Poll job status
    API-->>WebUI: Job completed (100%)
```

### 3.2 Classe DocumentIngestionPipeline

**Fichier**: `rag-app/ingestion/ingest.py`

**Responsabilités**:
1. Lecture multi-format (PDF, DOCX, PPTX, XLSX, HTML, MD, TXT, Audio)
2. Parsing avec Docling
3. Extraction d'images (optionnel)
4. Chunking intelligent
5. Génération d'embeddings
6. Sauvegarde PostgreSQL

**Configuration**:
```python
@dataclass
class IngestionConfig:
    chunk_size: int = 1500          # Taille cible des chunks
    chunk_overlap: int = 200        # Chevauchement entre chunks
    max_chunk_size: int = 2000      # Taille maximale
    use_semantic_chunking: bool = True  # HybridChunker activé
```

**Méthodes clés**:

#### `_read_document(file_path: str) -> tuple[str, DoclingDocument, List[ImageMetadata]]`

Lit un document et extrait le contenu + images.

**Formats supportés**:
- **Audio** (MP3, WAV, M4A, FLAC): Transcription Whisper ASR
- **Docling** (PDF, DOCX, PPTX, XLSX, HTML): Conversion en Markdown
- **Texte** (MD, TXT): Lecture directe

**Extraction d'images** (si `VLM_ENABLED=true`):
1. Docling détecte les images dans le PDF
2. Chaque image est sauvegardée dans `/app/uploads/images/{job_id}/{image_id}.png`
3. VLM API analyse l'image → Description + OCR
4. Métadonnées stockées (page, position, base64)

**Filtrage d'images** (anti-pollution):
```python
# Images filtrées selon critères
IMAGE_MIN_WIDTH = 200           # Largeur minimale
IMAGE_MIN_HEIGHT = 200          # Hauteur minimale
IMAGE_MIN_AREA = 40000          # Surface minimale (200x200)
IMAGE_ASPECT_RATIO_MAX = 10.0   # Ratio max (évite bannières)
```

**Retour**:
```python
(markdown_content, docling_doc, images)
# markdown_content: Contenu en Markdown (avec placeholders <!-- image -->)
# docling_doc: DoclingDocument (pour HybridChunker)
# images: List[ImageMetadata] (métadonnées + descriptions VLM)
```

#### `chunk_document(content, docling_doc)` (via Chunker)

**HybridChunker** (recommandé):
- Token-aware (800 tokens max par chunk, +56% vs défaut)
- Respect de la structure (sections, paragraphs, tableaux)
- Contexte préservé (hiérarchie de headings)
- Fallback: SimpleChunker si erreur

**SimpleChunker** (fallback):
- Split sur paragraphes (`\n\n`)
- Pas de limite stricte en caractères

**Output**: `List[DocumentChunk]`
```python
DocumentChunk(
    content: str,           # Texte du chunk
    index: int,             # Position dans le document
    start_char: int,        # Offset début
    end_char: int,          # Offset fin
    metadata: dict,         # {title, source, page_number, chunk_method}
    token_count: int,       # Nombre de tokens
    embedding: List[float]  # Ajouté après embed_chunks()
)
```

#### `_create_image_chunks(images)` → Chunks synthétiques

Transforme les images en chunks textuels cherchables dans le RAG.

**Structure du chunk synthétique**:
```markdown
[Document: {document_title}]
[Image {idx+1} depuis la page {page_num}]
Description: {vlm_description}
Texte extrait: {ocr_text}
Contexte: {title_keywords}
```

**Avantages**:
- Images indexées et cherchables via embeddings
- Descriptions VLM augmentent la sémantique
- OCR capture le texte présent dans les images
- Contexte documentaire enrichit la pertinence

**Index**: 1000+ (pour apparaître après les chunks textuels)

#### `embed_chunks(chunks)` → Embeddings batch

**Fichier**: `rag-app/ingestion/embedder.py`

**Processus**:
1. Batch de 20 chunks maximum
2. Appel API embeddings: `POST http://embeddings:8001/embed_batch`
3. Timeout: 90 secondes
4. Retry automatique en cas d'échec

**Nettoyage UTF-8**:
```python
# Critique: PDF contiennent souvent des surrogates UTF-8 invalides
clean_content = content.encode('utf-8', errors='replace').decode('utf-8')
```

**Output**: Chunks enrichis avec `embedding: List[float]` (1024 dimensions)

#### `_save_to_postgres(document, chunks, images)`

Sauvegarde transactionnelle dans PostgreSQL.

**Ordre d'insertion**:
1. **Document** → `documents` table (retourne `document_id`)
2. **Chunks** → `chunks` table (avec embeddings vectoriels)
3. **Images** → `document_images` table (liées aux chunks via `page_number`)

**Format vectoriel PostgreSQL**:
```python
# Conversion embedding pour PGVector
embedding_str = '[' + ','.join(map(str, embedding)) + ']'
# Example: '[0.123,-0.456,0.789,...]' (sans espaces)
```

**Linking chunk-image**:
```python
def _find_chunk_for_image(image, chunks):
    # Heuristique: correspondance par page_number
    for chunk in chunks:
        if chunk.metadata["page_number"] == image.page_number:
            return chunk_id
    # Fallback: premier chunk du document
```

### 3.3 Ingestion Worker

**Fichier**: `ingestion-worker/worker.py`

**Architecture asynchrone**:
- Worker tourne en boucle infinie (poll interval: 3s)
- Polling PostgreSQL pour jobs `status='pending'`
- Claim atomique du job (`UPDATE WHERE status='pending'`)
- Traitement avec mise à jour de progression (0→100%)

**Classe IngestionWorker**:

```python
class IngestionWorker:
    poll_interval: int = 3          # Intervalle de polling
    timeout_minutes: int = 30       # Timeout avant reset
    uploads_dir: Path = "/app/uploads"

    async def run(self):
        """Boucle principale du worker"""
        while self.running:
            job = await self.get_next_pending_job()
            if job:
                await self.process_job(job)
            else:
                await asyncio.sleep(self.poll_interval)
```

**Méthode process_job(job)**:

**Étapes avec progression**:
```python
0%  → Job créé
10% → Fichier localisé dans /app/uploads/{job_id}/
30% → Document lu et parsé
40% → Métadonnées extraites
60% → Chunking terminé
80% → Embeddings générés
85% → Images traitées (VLM)
90% → Sauvegarde PostgreSQL
100% → Job complété
```

**Gestion d'erreurs**:
- Capture toutes exceptions → `status='failed'`, `error_message`
- Cleanup fichier uploadé (même en cas d'erreur)
- Reset jobs bloqués au démarrage (`reset_stuck_jobs()`)

**Shared volume**:
- API sauvegarde: `/app/uploads/{job_id}/{filename}`
- Worker lit depuis le même volume partagé
- Cleanup après traitement réussi

### 3.4 Schéma de base de données (Ingestion)

**Fichier**: `database/schema.sql`

```sql
-- Documents sources
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    source TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Chunks avec embeddings (dimension 1024)
CREATE TABLE chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    embedding vector(1024),  -- E5-Large embeddings
    chunk_index INTEGER NOT NULL,
    metadata JSONB DEFAULT '{}',
    token_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index vectoriel IVFFlat (optimisé pour cosine similarity)
CREATE INDEX idx_chunks_embedding
    ON chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Images extraites des documents (VLM)
CREATE TABLE document_images (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    chunk_id UUID REFERENCES chunks(id),
    page_number INTEGER,
    position JSONB,  -- {x, y, width, height}
    image_path VARCHAR(500),
    image_base64 TEXT,  -- Pour affichage inline
    image_format VARCHAR(10),
    image_size_bytes INTEGER,
    description TEXT,  -- VLM description
    ocr_text TEXT,     -- VLM OCR
    confidence_score FLOAT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Jobs d'ingestion asynchrones
CREATE TABLE ingestion_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    filename VARCHAR(255) NOT NULL,
    file_size INTEGER,
    status VARCHAR(20) DEFAULT 'pending',  -- pending, processing, completed, failed
    progress INTEGER DEFAULT 0,
    document_id UUID REFERENCES documents(id),
    chunks_created INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);
```

**Fonction de recherche vectorielle**:
```sql
CREATE FUNCTION match_chunks(
    query_embedding vector(1024),
    match_count INT DEFAULT 10,
    similarity_threshold FLOAT DEFAULT 0.0
)
RETURNS TABLE (
    id UUID,
    document_id UUID,
    content TEXT,
    similarity FLOAT,  -- 1 - (embedding <=> query_embedding)
    metadata JSONB,
    document_title TEXT,
    document_source TEXT
)
```

**Opérateur de distance**:
- `<=>` : Cosine distance (0 = identique, 2 = opposé)
- Similarité = `1 - distance` (0-1, 1 = parfait match)

---

## 4. Pipeline de recherche vectorielle

### 4.1 Vue d'ensemble du flux

```mermaid
sequenceDiagram
    participant User
    participant API
    participant Embeddings
    participant PGVector
    participant Reranker

    User->>API: Send question
    API->>Embeddings: Embed question
    Embeddings-->>API: Query vector (1024-dim)

    alt Reranking enabled
        API->>PGVector: Vector search (top-20)
        PGVector-->>API: 20 candidate chunks
        API->>Reranker: Rerank(query, candidates)
        Reranker-->>API: Top-5 reranked chunks
    else Reranking disabled
        API->>PGVector: Vector search (top-5)
        PGVector-->>API: 5 most similar chunks
    end

    API->>PGVector: Fetch images for chunks
    PGVector-->>API: Associated images
    API-->>User: Sources + Images
```

### 4.2 Fonction search_knowledge_base_tool

**Fichier**: `web-api/app/main.py` (lignes 1008-1201)

**Signature**:
```python
async def search_knowledge_base_tool(query: str, limit: int = 5) -> str
```

**Étapes détaillées**:

#### Étape 1: Détermination du mode reranking

**Priorité de configuration** (ordre décroissant):
1. **Requête explicite**: `_current_reranking_enabled` (variable globale)
2. **Préférence conversation**: `conversations.reranking_enabled`
3. **Configuration globale**: `RERANKER_ENABLED` (env var)

```python
# Lecture de la préférence de conversation
async with database.db_pool.acquire() as conn:
    conv = await conn.fetchrow(
        "SELECT reranking_enabled FROM conversations WHERE id = $1",
        _current_conversation_id
    )
    if conv['reranking_enabled'] is not None:
        reranker_enabled = conv['reranking_enabled']
```

**Ajustement de la limite de recherche**:
```python
if reranker_enabled:
    search_limit = int(os.getenv("RERANKER_TOP_K", "20"))  # 20 candidats
else:
    search_limit = limit  # 5 directs
```

#### Étape 2: Génération de l'embedding de la question

**API Embeddings**:
```python
embeddings_url = os.getenv("EMBEDDINGS_API_URL", "http://ragfab-embeddings:8001")
async with httpx.AsyncClient() as client:
    response = await client.post(
        f"{embeddings_url}/embed",
        json={"text": query},
        timeout=30.0
    )
    query_embedding = response.json()["embedding"]  # List[float] (1024-dim)
```

**Conversion pour PostgreSQL**:
```python
embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"
# Example: "[0.123,-0.456,0.789,...]"
```

#### Étape 3: Recherche vectorielle dans PostgreSQL

**Requête SQL**:
```sql
SELECT
    c.id as chunk_id,
    c.content,
    c.chunk_index,
    c.metadata,
    d.id as document_id,
    d.title as document_title,
    d.source as document_source,
    1 - (c.embedding <=> $1::vector) as similarity  -- Cosine similarity
FROM chunks c
JOIN documents d ON c.document_id = d.id
ORDER BY c.embedding <=> $1::vector  -- Ordre croissant de distance
LIMIT $2
```

**Opérateur `<=>`**:
- Distance cosine entre deux vecteurs
- 0.0 = vecteurs identiques
- 2.0 = vecteurs opposés
- `1 - distance` = score de similarité (0-1)

**Index IVFFlat**:
- Partitionnement en 100 listes (clusters)
- Approximate Nearest Neighbor (ANN)
- Compromis vitesse/précision

#### Étape 4: Récupération des images associées

```python
chunk_ids = [str(row["chunk_id"]) for row in results]
async with database.db_pool.acquire() as conn:
    image_rows = await conn.fetch(
        """
        SELECT chunk_id, id, page_number, position,
               description, ocr_text, image_base64
        FROM document_images
        WHERE chunk_id = ANY($1::uuid[])
        ORDER BY page_number, (position->>'y')::float
        """,
        chunk_ids
    )
```

**Mapping chunk → images**:
```python
chunk_images_map = {}  # {chunk_id: [image1, image2, ...]}
for img_row in image_rows:
    chunk_id = str(img_row["chunk_id"])
    chunk_images_map.setdefault(chunk_id, []).append({
        "id": str(img_row["image_id"]),
        "description": img_row["description"],
        "ocr_text": img_row["ocr_text"],
        "image_base64": img_row["image_base64"]
    })
```

#### Étape 5: Reranking (optionnel)

**Fonction rerank_results(query, results)**:

**API Reranker**:
```python
reranker_url = os.getenv("RERANKER_API_URL", "http://reranker:8002")
return_k = int(os.getenv("RERANKER_RETURN_K", "5"))

async with httpx.AsyncClient() as client:
    response = await client.post(
        f"{reranker_url}/rerank",
        json={
            "query": query,
            "documents": documents,  # 20 candidats
            "top_k": return_k        # 5 finaux
        },
        timeout=60.0
    )
    reranked_data = response.json()
```

**Modèle BGE-reranker-v2-m3**:
- CrossEncoder (analyse paire question-document)
- Score de pertinence plus fin que similarité vectorielle
- +20-30% d'amélioration de la pertinence

**Fallback gracieux**:
```python
except Exception as e:
    logger.warning(f"⚠️ Reranking failed (fallback to vector search): {e}")
    # Retourne top-5 des résultats vectoriels
    return results[:return_k]
```

#### Étape 6: Formatage de la réponse

**Structure des sources**:
```python
sources = []
for doc in reranked_docs:
    sources.append({
        "chunk_id": doc["chunk_id"],
        "document_id": doc["document_id"],
        "document_title": doc["document_title"],
        "document_source": doc["document_source"],
        "chunk_index": doc["chunk_index"],
        "content": doc["content"][:200] + "...",
        "similarity": doc["similarity"],
        "images": chunk_images_map.get(doc["chunk_id"], []),
        "is_image_chunk": doc.get("metadata", {}).get("is_image_chunk", False)
    })
```

**Sauvegarde globale**:
```python
_current_request_sources = sources.copy()
logger.info(f"✅ {len(sources)} sources sauvegardées")
```

**Texte retourné au LLM**:
```python
response_parts = []
for doc in sources:
    part = f"[Source: {doc['document_title']}]\n{doc['content']}\n"
    if doc["images"]:
        part += f"\n📷 Images associées ({len(doc['images'])}):\n"
        for img in doc["images"]:
            if img.get("description"):
                part += f"  - {img['description']}\n"
            if img.get("ocr_text"):
                part += f"    Texte: {img['ocr_text'][:100]}...\n"
    response_parts.append(part)

return "Résultats trouvés:\n\n" + "\n---\n".join(response_parts)
```

### 4.3 Variables globales de contexte

**Fichier**: `web-api/app/main.py` (ligne 50)

```python
_current_request_sources: List[dict] = []  # Sources de la requête en cours
_current_conversation_id: Optional[UUID] = None  # ID conversation active
_current_reranking_enabled: Optional[bool] = None  # Préférence reranking
```

**Pourquoi des globales et pas ContextVar?**
- PydanticAI exécute les tools en contexte async isolé
- ContextVar perd son état entre l'appel du tool et la récupération du résultat
- FastAPI traite les requêtes séquentiellement → pas de race condition
- Alternative envisageable: Redis ou base de données (overhead inutile)

**Pattern d'utilisation**:
```python
# 1. Initialisation au début de la requête
_current_request_sources = []
_current_conversation_id = conversation_id
_current_reranking_enabled = reranking_enabled

# 2. Tool sauvegarde les sources
async def search_knowledge_base_tool(query):
    # ... recherche ...
    _current_request_sources = sources.copy()

# 3. Récupération après exécution de l'agent
result = await agent.run(message)
sources = _current_request_sources.copy()
```

---

## 5. Pipeline de génération de réponse

### 5.1 Vue d'ensemble du système dual-provider

```mermaid
graph TB
    START[User Question] --> DETECT{Detect<br/>Contextual<br/>Reference?}

    DETECT -->|Yes| REFORM[Reformulate Question<br/>with Mistral API]
    DETECT -->|No| MODE{use_tools?}
    REFORM --> MODE

    MODE -->|True: Function Calling| AGENT_TOOLS[Create Agent<br/>with Tools]
    MODE -->|False: Manual Injection| SEARCH_MANUAL[Execute Search<br/>Manually]

    AGENT_TOOLS --> RUN_AGENT[Run Agent<br/>Empty History]
    SEARCH_MANUAL --> INJECT[Inject Context<br/>in System Prompt]

    RUN_AGENT --> TOOL_CALL[LLM Calls<br/>search_knowledge_base_tool]
    TOOL_CALL --> RETRIEVE_SOURCES[Retrieve Sources<br/>from Global Variable]

    INJECT --> CREATE_AGENT[Create Agent<br/>No Tools]
    CREATE_AGENT --> RUN_NO_TOOLS[Run Agent<br/>with Context Summary]

    RETRIEVE_SOURCES --> RESPONSE[Generate Response]
    RUN_NO_TOOLS --> RETRIEVE_MANUAL[Sources Already<br/>Retrieved]
    RETRIEVE_MANUAL --> RESPONSE

    RESPONSE --> RETURN[Return to User]
```

### 5.2 Reformulation de question

**Fonction**: `reformulate_question_with_context(message, history)`
**Fichier**: `web-api/app/main.py` (lignes 847-946)

**Objectif**: Résoudre les références contextuelles dans les questions de suivi.

**Exemples de références détectées**:

**Références fortes** (toujours reformulées):
- `celle`, `celui`, `celles`, `ceux`
- Example: "Et celle-ci?" → "Quelle est la politique de télétravail pour les managers?"

**Références moyennes** (si question courte <8 mots):
- `ça`, `cela`, `ce`, `cette`, `ces`
- Example: "Et ça?" → "Quels sont les avantages de la mutuelle santé?"

**Pronoms en début** (si premier mot):
- `il`, `elle`, `ils`, `elles`, `y`, `en`
- Example: "Y a-t-il des exceptions?" → "Y a-t-il des exceptions à la politique de congés?"

**Patterns spéciaux**:
- Questions commençant par "et celle", "et celui", "et ça"

**Exclusions**:
- Articles génériques: `le`, `la`, `les` (trop de faux positifs)

**Appel Mistral API**:
```python
async with httpx.AsyncClient() as client:
    response = await client.post(
        f"{mistral_api_url}/v1/chat/completions",
        json={
            "model": mistral_model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                *history[-4:],  # 2 derniers échanges
                {"role": "user", "content": message}
            ],
            "temperature": 0.3  # Peu de créativité
        },
        headers={"Authorization": f"Bearer {mistral_api_key}"},
        timeout=30.0
    )
    reformulated = response.json()["choices"][0]["message"]["content"]
```

**System prompt**:
```text
Tu reformules les questions vagues en questions autonomes et précises.

RÈGLES:
- Si la question est déjà claire et autonome, renvoie-la telle quelle
- Si elle contient une référence contextuelle (celle, celui, ça, ce, etc.),
  reformule en intégrant le contexte de la conversation
- Garde la question courte et directe
- Renvoie UNIQUEMENT la question reformulée, sans explication

EXEMPLES:
Question: "Et celle pour les managers ?"
Contexte: [politique de télétravail]
→ "Quelle est la politique de télétravail pour les managers ?"

Question: "Quels sont les avantages ?"
→ "Quels sont les avantages ?" (déjà autonome)
```

### 5.3 Fonction execute_rag_agent

**Fichier**: `web-api/app/main.py` (lignes 1402-1514)

**Signature**:
```python
async def execute_rag_agent(
    message: str,
    history: List[dict],
    provider: str,
    use_tools: bool,
    conversation_id: Optional[UUID] = None,
    reranking_enabled: Optional[bool] = None
) -> dict
```

**Retour**:
```python
{
    "content": str,           # Réponse générée
    "sources": List[dict],    # Sources utilisées
    "model_name": str,        # Nom du modèle LLM
    "token_usage": Optional[dict]  # Statistiques (si disponibles)
}
```

#### Mode 1: Function Calling (use_tools=True)

**Configuration**:
```python
llm_use_tools = os.getenv("LLM_USE_TOOLS", "").lower() == "true"
mistral_use_tools = os.getenv("RAG_PROVIDER", "mistral") == "mistral" and use_tools
use_function_calling = llm_use_tools or mistral_use_tools
```

**Création de l'agent**:
```python
from .utils.generic_llm_provider import get_generic_llm_model

model = get_generic_llm_model()  # Mistral, Ollama, LiteLLM, etc.
system_prompt = build_tool_system_prompt_with_json()

agent = Agent(
    model,
    system_prompt=system_prompt,
    tools=[search_knowledge_base_tool]
)
```

**System prompt enrichi avec JSON**:
```python
def build_tool_system_prompt_with_json() -> str:
    return f"""
Tu es un assistant RAG intelligent.

OUTIL DISPONIBLE - DÉFINITION COMPLÈTE :
[
  {{
    "type": "function",
    "function": {{
      "name": "search_knowledge_base_tool",
      "description": "Recherche dans la base de connaissances",
      "parameters": {{
        "type": "object",
        "properties": {{
          "query": {{
            "type": "string",
            "description": "Question de recherche"
          }},
          "limit": {{
            "type": "integer",
            "default": 5
          }}
        }},
        "required": ["query"]
      }}
    }}
  }}
]

EXEMPLE D'UTILISATION CORRECTE :
Question: "Quelle est la politique de télétravail ?"
→ ÉTAPE 1 - APPEL OBLIGATOIRE: search_knowledge_base_tool(query="...")
→ ÉTAPE 2 - RÉCEPTION: [Résultats]
→ ÉTAPE 3 - RÉPONSE: [Synthèse basée sur les résultats]

RÈGLES ABSOLUES :
1. Tu DOIS appeler l'outil AVANT de répondre
2. JAMAIS de réponse sans appel préalable de l'outil
3. Si l'outil ne trouve rien, dis-le clairement
4. Utilise UNIQUEMENT les informations retournées par l'outil
"""
```

**Pourquoi JSON explicite dans le prompt?**
- Renforce le comportement de function calling
- Certains providers (Ollama, LiteLLM) ont besoin du contexte explicite
- Dual approach: API `tool_choice` + JSON in prompt = meilleure fiabilité

**Exécution**:
```python
# Reformuler la question si références contextuelles
reformulated_message = await reformulate_question_with_context(message, history)

# Exécuter SANS historique pour forcer l'appel du tool
result = await agent.run(reformulated_message, message_history=[])

# Récupérer les sources depuis la variable globale
sources = _current_request_sources.copy()
```

**Pourquoi historique vide?**
- Si historique passé, le LLM peut répondre depuis le contexte conversationnel
- Historique vide → LLM n'a pas le contexte → DOIT appeler le tool
- Garantit que chaque réponse est basée sur une recherche fraîche

#### Mode 2: Injection manuelle (use_tools=False)

**Recherche préalable**:
```python
search_results = await search_knowledge_base_tool(message, limit=5)
sources = _current_request_sources.copy()
```

**Injection dans le system prompt**:
```python
system_prompt = f"""Tu es un assistant intelligent.

CONTEXTE DE LA BASE DE CONNAISSANCES:
{search_results}

INSTRUCTIONS:
- Utilise UNIQUEMENT les informations du contexte ci-dessus
- Si l'information n'est pas dans le contexte, dis-le clairement
- Réponds en français de manière concise et précise
"""
```

**Résumé conversationnel**:
```python
if history and len(history) > 0:
    recent_history = history[-4:]  # 2 derniers échanges
    context_summary = "\n".join([
        f"{'Utilisateur' if msg['role'] == 'user' else 'Assistant'}: {msg['content'][:200]}"
        for msg in recent_history
    ])
    enhanced_message = f"Contexte récent:\n{context_summary}\n\nNouvelle question: {message}"
else:
    enhanced_message = message
```

**Exécution**:
```python
model = get_generic_llm_model()
agent = Agent(model, system_prompt=system_prompt)  # Pas de tools
result = await agent.run(enhanced_message, message_history=[])
```

**Avantage du résumé conversationnel**:
- Injection manuelle → pas de conflit avec function calling
- LLM peut comprendre le contexte de la conversation
- Limité à 2 derniers échanges (évite surcharge de tokens)

### 5.4 Provider générique (Generic LLM)

**Fichier**: `web-api/app/utils/generic_llm_provider.py`

**Configuration**:
```python
LLM_API_URL = os.getenv("LLM_API_URL", "https://api.mistral.ai")
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "mistral-small-latest")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "120.0"))
LLM_USE_TOOLS = os.getenv("LLM_USE_TOOLS", "").lower() == "true"
```

**Providers supportés**:
- Mistral AI: `https://api.mistral.ai`
- Chocolatine: `https://apigpt.mynumih.fr`
- Ollama: `http://localhost:11434`
- LiteLLM: `http://localhost:4000`
- OpenAI: `https://api.openai.com`
- Tout provider compatible OpenAI Chat Completions API

**Format API requis**:
```python
# Endpoint: POST {LLM_API_URL}/v1/chat/completions
{
  "model": "model-name",
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."}
  ],
  "tools": [...],  # Optionnel (si LLM_USE_TOOLS=true)
  "tool_choice": "auto",
  "temperature": 0.7
}
```

**Rétrocompatibilité**:
```python
# Variables legacy supportées (DEPRECATED)
MISTRAL_API_KEY → LLM_API_KEY
MISTRAL_API_URL → LLM_API_URL
MISTRAL_MODEL_NAME → LLM_MODEL_NAME
MISTRAL_TIMEOUT → LLM_TIMEOUT
RAG_PROVIDER="mistral" → LLM_USE_TOOLS=true
```

### 5.5 Gestion des tools dans PydanticAI

**Points critiques**:

1. **Import correct de ArgsDict**:
```python
# ✅ CORRECT
from pydantic_ai.messages import ArgsDict

# ❌ INCORRECT (erreur import)
from pydantic_ai.models import ArgsDict
```

2. **Extraction des arguments du tool**:
```python
# ✅ CORRECT
part.args.args_dict  # Dict[str, Any]

# ❌ INCORRECT
part.args  # ArgsDict object (not serializable)
```

3. **Format de message pour tool results**:
```python
# ToolReturnPart doit être dans ModelRequest (input)
# PAS dans ModelResponse (output)

# ✅ CORRECT
new_messages.append(ModelRequest(parts=[
    ToolReturnPart(
        tool_name="search_knowledge_base_tool",
        content="...",
        tool_call_id=part.tool_call_id
    )
]))

# ❌ INCORRECT
new_messages.append(ModelResponse(parts=[...]))  # Wrong direction
```

4. **Ordre strict des messages**:
```python
# system → user → assistant (avec tool_calls) → tool (avec results)
[
    SystemPromptPart(content="..."),
    UserPromptPart(content="..."),
    ToolCallPart(tool_name="...", args=ArgsDict(...)),
    ToolReturnPart(tool_name="...", content="...")
]
```

5. **Utilisation de run() au lieu de run_stream()**:
```python
# ✅ CORRECT (exécution automatique des tools)
result = await agent.run(message)

# ❌ INCORRECT (détecte mais n'exécute pas les tools)
async for chunk in agent.run_stream(message):
    ...
```

---

## 6. Flux de données complet

### 6.1 Scénario: Upload et question

```mermaid
sequenceDiagram
    participant U as User
    participant UI as Frontend
    participant API as Web API
    participant DB as PostgreSQL
    participant W as Worker
    participant E as Embeddings
    participant V as VLM
    participant L as LLM
    participant R as Reranker

    rect rgb(230, 240, 250)
    Note over U,V: PHASE 1: INGESTION
    U->>UI: Upload document.pdf
    UI->>API: POST /api/documents/upload
    API->>DB: INSERT ingestion_jobs (status=pending)
    API-->>UI: job_id
    UI->>UI: Poll job status (2s interval)

    W->>DB: Poll jobs (3s interval)
    W->>DB: Claim job (status=processing)
    W->>W: Parse PDF with Docling
    W->>V: Extract & describe images
    V-->>W: Descriptions + OCR
    W->>W: Chunk document (HybridChunker)
    W->>W: Create synthetic image chunks
    W->>E: Embed chunks (batch 20)
    E-->>W: Embeddings (1024-dim)
    W->>DB: Save document + chunks + images
    W->>DB: Update job (status=completed)
    UI->>API: GET /api/jobs/{job_id}
    API-->>UI: Job 100% completed
    end

    rect rgb(240, 250, 230)
    Note over U,R: PHASE 2: QUESTION
    U->>UI: "Quelle est la politique de télétravail?"
    UI->>API: POST /api/conversations/{id}/messages

    alt Contextual reference detected
        API->>L: Reformulate question
        L-->>API: "Quelle est la politique..."
    end

    API->>API: Initialize global context
    Note over API: _current_request_sources = []<br/>_current_conversation_id = conv_id<br/>_current_reranking_enabled = preference

    alt Function Calling Mode
        API->>API: Create agent with tools
        API->>L: Run agent (empty history)
        L->>API: Call search_knowledge_base_tool
        API->>E: Embed question
        E-->>API: Query embedding

        alt Reranking enabled
            API->>DB: Vector search (top-20)
            DB-->>API: 20 candidates
            API->>R: Rerank candidates
            R-->>API: Top-5 reranked
        else Reranking disabled
            API->>DB: Vector search (top-5)
            DB-->>API: 5 chunks
        end

        API->>DB: Fetch images for chunks
        DB-->>API: Associated images
        API->>API: Save sources to global variable
        API-->>L: Search results + images
        L->>L: Generate response
        L-->>API: Response content
        API->>API: Retrieve sources from global
    else Manual Injection Mode
        API->>API: Execute search manually
        API->>E: Embed question
        API->>DB: Vector search
        API->>R: Rerank (if enabled)
        API->>DB: Fetch images
        API->>API: Save sources
        API->>API: Inject context in system prompt
        API->>L: Run agent with context
        L-->>API: Response content
    end

    API->>DB: Save message (user + assistant)
    API-->>UI: Response + sources + images
    UI-->>U: Display answer with sources and images
    end
```

### 6.2 Flux de données détaillé

**Input**: Question utilisateur
**Output**: Réponse avec sources et images

**Étapes numérotées**:

1. **Réception de la question** (`POST /api/conversations/{id}/messages`)
   - Headers: `Authorization: Bearer {jwt_token}`
   - Body: `{"content": "question", "reranking_enabled": true}`

2. **Détection de références contextuelles** (`reformulate_question_with_context`)
   - Analyse de la question (pronoms, références)
   - Appel Mistral API si nécessaire
   - Retour: question reformulée ou originale

3. **Initialisation du contexte global**
   ```python
   _current_request_sources = []
   _current_conversation_id = conversation_id
   _current_reranking_enabled = reranking_enabled
   ```

4. **Choix du mode d'exécution**
   - `LLM_USE_TOOLS=true` → Function calling
   - `LLM_USE_TOOLS=false` → Injection manuelle

5. **Mode Function Calling**:
   - 5a. Création agent avec `tools=[search_knowledge_base_tool]`
   - 5b. Exécution `agent.run(message, message_history=[])`
   - 5c. LLM appelle `search_knowledge_base_tool(query="...")`
   - 5d. Tool exécute recherche vectorielle + reranking
   - 5e. Tool sauvegarde sources dans `_current_request_sources`
   - 5f. Tool retourne texte formaté au LLM
   - 5g. LLM génère réponse basée sur les résultats
   - 5h. Récupération sources depuis variable globale

6. **Mode Injection Manuelle**:
   - 6a. Exécution `search_knowledge_base_tool` manuellement
   - 6b. Récupération sources depuis `_current_request_sources`
   - 6c. Construction system prompt avec contexte injecté
   - 6d. Résumé conversationnel (2 derniers échanges)
   - 6e. Création agent sans tools
   - 6f. Exécution `agent.run(enhanced_message)`
   - 6g. LLM génère réponse depuis le contexte

7. **Recherche vectorielle** (`search_knowledge_base_tool`):
   - 7a. Génération embedding question (E5-Large)
   - 7b. Query PostgreSQL avec opérateur `<=>`
   - 7c. Reranking optionnel (BGE-reranker)
   - 7d. Récupération images associées
   - 7e. Formatage sources avec métadonnées
   - 7f. Sauvegarde dans variable globale

8. **Sauvegarde en base de données**
   ```sql
   INSERT INTO messages (conversation_id, role, content, sources)
   VALUES ($1, 'user', $2, '[]');

   INSERT INTO messages (conversation_id, role, content, sources, model_name)
   VALUES ($1, 'assistant', $2, $3, $4);
   ```

9. **Retour à l'utilisateur**
   ```json
   {
     "id": "message_id",
     "content": "Réponse générée...",
     "sources": [
       {
         "chunk_id": "...",
         "document_title": "...",
         "content": "...",
         "similarity": 0.85,
         "images": [
           {
             "id": "...",
             "description": "...",
             "ocr_text": "...",
             "image_base64": "..."
           }
         ]
       }
     ],
     "model_name": "mistral-small-latest",
     "created_at": "2025-01-24T..."
   }
   ```

---

## 7. Configuration et optimisation

### 7.1 Variables d'environnement critiques

**Base de données**:
```bash
DATABASE_URL=postgresql://raguser:pass@postgres:5432/ragdb
# ⚠️ Coolify: utiliser postgres.internal au lieu de postgres
```

**LLM Provider (Generic)**:
```bash
LLM_API_URL=https://api.mistral.ai  # Ou Ollama, LiteLLM, etc.
LLM_API_KEY=your_api_key_here
LLM_MODEL_NAME=mistral-small-latest
LLM_USE_TOOLS=true  # Function calling activé
LLM_TIMEOUT=120.0
```

**Embeddings**:
```bash
EMBEDDINGS_API_URL=http://embeddings:8001
EMBEDDING_DIMENSION=1024  # E5-Large
```

**Reranking** (optionnel):
```bash
RERANKER_ENABLED=false  # true pour activer
RERANKER_API_URL=http://reranker:8002
RERANKER_MODEL=BAAI/bge-reranker-v2-m3
RERANKER_TOP_K=20  # Candidats avant reranking
RERANKER_RETURN_K=5  # Résultats finaux
```

**VLM Image Extraction** (optionnel):
```bash
VLM_ENABLED=false  # true pour activer
VLM_API_URL=https://apivlm.mynumih.fr
VLM_API_KEY=  # Optionnel
VLM_MODEL_NAME=OpenGVLab/InternVL3_5-8B
VLM_TIMEOUT=60.0

# Filtrage d'images (anti-pollution)
IMAGE_MIN_WIDTH=200
IMAGE_MIN_HEIGHT=200
IMAGE_MIN_AREA=40000  # 200x200 pixels
IMAGE_ASPECT_RATIO_MAX=10.0
```

**Chunking**:
```bash
CHUNK_SIZE=1500  # Taille cible en caractères
CHUNK_OVERLAP=200  # Chevauchement
USE_SEMANTIC_CHUNKING=true  # HybridChunker
```

**Ingestion Worker**:
```bash
WORKER_POLL_INTERVAL=3  # Secondes entre polls
WORKER_TIMEOUT_MINUTES=30  # Timeout avant reset
```

### 7.2 Optimisations de performance

**Batch embedding**:
```python
# rag-app/ingestion/embedder.py
BATCH_SIZE = 20  # Chunks par batch
TIMEOUT = 90.0   # Secondes
```

**Rationale**:
- API embeddings: ~100ms par chunk
- Batch 20 chunks: ~2s total vs 2s x 20 = 40s séquentiel
- Timeout 90s laisse marge pour retry

**Index PostgreSQL**:
```sql
-- IVFFlat pour ANN (Approximate Nearest Neighbor)
CREATE INDEX idx_chunks_embedding
    ON chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
```

**Rationale**:
- 100 listes = partitionnement en clusters
- Recherche dans ~10 clusters (10% du total)
- Compromis: 95% précision, 10x plus rapide qu'exact

**Reranking sélectif**:
```python
# Activer uniquement si:
# - Documentation technique avec terminologie similaire
# - Base >1000 documents
# - Besoin de précision maximale

# Coût: +100-300ms par requête
# Gain: +20-30% pertinence
```

**Chunking HybridChunker**:
```python
# rag-app/ingestion/chunker.py
HybridChunker(
    tokenizer=tokenizer,
    max_tokens=800,  # +56% contexte vs 512 (défaut)
    merge_peers=True  # Fusionne sections courtes
)
```

**Rationale**:
- 800 tokens = 600-800 mots
- E5-Large supporte 512 tokens (testé jusqu'à 1024)
- Plus de contexte = meilleure compréhension sémantique

### 7.3 Monitoring et debugging

**Logs structurés**:
```python
logger.info(f"🔍 Tool search_knowledge_base_tool appelé avec query: {query}")
logger.info(f"🎚️ Préférence requête: reranking={reranker_enabled}")
logger.info(f"🔄 Reranking activé: recherche de {search_limit} candidats")
logger.info(f"✅ {len(sources)} sources sauvegardées dans _current_request_sources")
```

**Métriques importantes**:
- Temps de génération d'embeddings
- Latence recherche vectorielle
- Temps de reranking (si activé)
- Temps total de réponse LLM

**Requêtes SQL de monitoring**:
```sql
-- Nombre de documents et chunks
SELECT COUNT(*) as doc_count FROM documents;
SELECT COUNT(*) as chunk_count FROM chunks;

-- Taille moyenne des chunks
SELECT AVG(token_count) as avg_tokens FROM chunks;

-- Distribution par document
SELECT d.title, COUNT(c.id) as chunks
FROM documents d
LEFT JOIN chunks c ON d.id = c.document_id
GROUP BY d.id, d.title;

-- Jobs en cours
SELECT status, COUNT(*)
FROM ingestion_jobs
GROUP BY status;

-- Jobs échoués récents
SELECT filename, error_message, created_at
FROM ingestion_jobs
WHERE status = 'failed'
ORDER BY created_at DESC
LIMIT 10;
```

---

## 8. Points critiques et pièges

### 8.1 Pièges courants

**1. Encodage UTF-8 des chunks**

**Problème**: PDFs contiennent souvent des surrogates UTF-8 invalides
**Symptôme**: `UnicodeEncodeError` lors de la sauvegarde PostgreSQL
**Solution**:
```python
clean_content = content.encode('utf-8', errors='replace').decode('utf-8')
```

**Fichiers concernés**:
- `rag-app/ingestion/ingest.py`
- `web-api/app/main.py`

---

**2. Format vectoriel PostgreSQL**

**Problème**: PGVector attend format sans espaces après virgules
**Symptôme**: `ERROR: invalid input syntax for type vector`
**Solution**:
```python
# ✅ CORRECT
embedding_str = '[' + ','.join(map(str, embedding)) + ']'

# ❌ INCORRECT
embedding_str = str(embedding)  # Contient espaces
```

---

**3. Dimension d'embeddings**

**Problème**: Mismatch entre modèle d'embeddings et schéma DB
**Symptôme**: `ERROR: expected 1024 dimensions, got 1536`
**Solution**:
```sql
-- Vérifier dimension dans schema.sql
CREATE TABLE chunks (
    embedding vector(1024),  -- DOIT correspondre au modèle
    ...
);

-- Recréer table si changement de modèle
DROP TABLE chunks CASCADE;
CREATE TABLE chunks (...);
```

---

**4. Historique vide avec function calling**

**Problème**: Si historique passé, LLM répond sans appeler le tool
**Symptôme**: Réponse générique sans sources
**Solution**:
```python
# ✅ CORRECT (mode function calling)
result = await agent.run(message, message_history=[])

# ❌ INCORRECT
result = await agent.run(message, message_history=history)
```

---

**5. Variable globale _current_request_sources**

**Problème**: Sources non initialisées ou écrasées
**Symptôme**: Sources vides ou sources d'une requête précédente
**Solution**:
```python
# TOUJOURS initialiser au début de la requête
_current_request_sources = []
_current_conversation_id = conversation_id

# TOUJOURS copier lors de la récupération
sources = _current_request_sources.copy()  # Pas de référence directe
```

---

**6. Timeout embeddings batch**

**Problème**: Batch trop grand → timeout API
**Symptôme**: `TimeoutError` lors de l'ingestion
**Solution**:
```python
# Limiter batch size
BATCH_SIZE = 20  # Max 20 chunks

# Augmenter timeout si nécessaire
TIMEOUT = 90.0  # Secondes
```

---

**7. Jobs bloqués (worker crash)**

**Problème**: Worker crash → jobs restent en `status=processing`
**Symptôme**: Documents ne s'ingèrent pas
**Solution**:
```python
# Worker reset automatique au démarrage
async def reset_stuck_jobs(self):
    timeout_threshold = datetime.now() - timedelta(minutes=30)
    await conn.execute("""
        UPDATE ingestion_jobs
        SET status = 'pending', started_at = NULL
        WHERE status = 'processing' AND started_at < $1
    """, timeout_threshold)
```

**Manuel**:
```sql
-- Réinitialiser jobs bloqués
UPDATE ingestion_jobs
SET status = 'pending', started_at = NULL
WHERE status = 'processing';
```

---

**8. Reranking fallback silencieux**

**Problème**: Service reranker down → fallback discret
**Symptôme**: Pertinence réduite sans erreur visible
**Solution**:
```python
# Toujours logger le fallback
except Exception as e:
    logger.warning(f"⚠️ Erreur reranking (fallback): {e}")
    return results[:return_k]  # Fallback vers vector search
```

**Monitoring**:
```bash
# Vérifier logs reranker
docker-compose logs -f reranker

# Tester endpoint
curl -X POST http://reranker:8002/rerank \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "documents": [...], "top_k": 5}'
```

---

**9. Images filtrées par erreur**

**Problème**: Filtrage trop strict → images pertinentes ignorées
**Symptôme**: Aucune image indexée malgré présence dans PDF
**Solution**:
```bash
# Réduire seuils de filtrage
IMAGE_MIN_WIDTH=150
IMAGE_MIN_HEIGHT=150
IMAGE_MIN_AREA=22500  # 150x150

# Ou désactiver complètement
IMAGE_MIN_WIDTH=0
IMAGE_MIN_HEIGHT=0
IMAGE_MIN_AREA=0
IMAGE_ASPECT_RATIO_MAX=1000.0
```

**Debug**:
```bash
# Activer logs détaillés
LOG_LEVEL=DEBUG

# Vérifier logs d'extraction
docker-compose logs -f ingestion-worker | grep "image"
```

---

**10. Container naming sur Coolify**

**Problème**: Conflits de noms entre projets
**Symptôme**: `ERROR: connection refused to postgres:5432`
**Solution**:
```bash
# Utiliser préfixes uniques
ragfab-postgres (au lieu de postgres)
ragfab-embeddings (au lieu de embeddings)
ragfab-reranker (au lieu de reranker)

# Mettre à jour DATABASE_URL
DATABASE_URL=postgresql://user:pass@ragfab-postgres:5432/db
# Ou avec .internal sur Coolify
DATABASE_URL=postgresql://user:pass@postgres.internal:5432/db
```

---

### 8.2 Checklist de debugging

**Problème d'ingestion**:
- [ ] Worker tourne? `docker-compose ps ingestion-worker`
- [ ] Jobs en pending? `SELECT * FROM ingestion_jobs WHERE status='pending';`
- [ ] Embeddings API accessible? `curl http://embeddings:8001/health`
- [ ] VLM API accessible (si activé)? `curl {VLM_API_URL}/health`
- [ ] Volume partagé monté? `ls /app/uploads/`
- [ ] Logs worker? `docker-compose logs -f ingestion-worker`

**Problème de recherche**:
- [ ] Chunks en base? `SELECT COUNT(*) FROM chunks;`
- [ ] Embeddings non NULL? `SELECT COUNT(*) FROM chunks WHERE embedding IS NULL;`
- [ ] Index vectoriel créé? `\d chunks` (vérifier idx_chunks_embedding)
- [ ] Dimension correcte? `SELECT vector_dims(embedding) FROM chunks LIMIT 1;`
- [ ] Reranker actif? `curl http://reranker:8002/health`

**Problème de réponse**:
- [ ] LLM API accessible? `curl {LLM_API_URL}/health`
- [ ] Sources récupérées? Vérifier logs "Sources sauvegardées"
- [ ] Tool appelé? Logs "Tool search_knowledge_base_tool appelé"
- [ ] Mode function calling configuré? `echo $LLM_USE_TOOLS`
- [ ] Historique vide passé? Vérifier code `message_history=[]`

---

### 8.3 Limites connues

**Scalabilité**:
- Worker séquentiel: 1 job à la fois
- Solution: Déployer plusieurs workers (job claiming atomique)

**Latence**:
- VLM extraction: +6-60s par image (selon modèle)
- Reranking: +100-300ms par requête
- Solution: Désactiver VLM ou reranking si contraintes temps réel

**Mémoire**:
- E5-Large embeddings: ~4-8GB RAM
- BGE-reranker: ~4GB RAM
- InternVL VLM: ~16GB VRAM (GPU)
- Solution: Adapter ressources Docker ou utiliser APIs distantes

**Stockage**:
- Base64 images: ~50-500KB par image
- Embeddings: 1024 floats x 4 bytes = 4KB par chunk
- Solution: Cleanup périodique des anciens documents

---

## Conclusion

Cette documentation couvre l'intégralité de la pipeline RAG de RAGFab, de l'upload d'un document à la génération d'une réponse enrichie avec sources et images.

**Points clés à retenir**:
1. **Pipeline d'ingestion asynchrone** avec jobs et worker dédié
2. **Chunking intelligent** via Docling HybridChunker (structure documentaire)
3. **Recherche vectorielle optimisée** avec IVFFlat et reranking optionnel
4. **Dual-mode LLM**: Function calling (automatique) ou injection manuelle
5. **Images enrichies** via VLM pour OCR et description
6. **Variables globales** pour gestion des sources (limitation PydanticAI)

**Pour aller plus loin**:
- Consulter `CLAUDE.md` pour détails d'implémentation
- Explorer `rag-app/` et `web-api/` pour le code source
- Tester avec `RERANKER_ENABLED=true` pour améliorer pertinence
- Activer `VLM_ENABLED=true` pour documents avec images techniques

---

**Dernière mise à jour**: 2025-01-24
**Auteur**: Documentation technique générée par analyse du codebase RAGFab
