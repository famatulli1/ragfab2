# Diagrammes d'Architecture - Pipeline RAG RAGFab

**Complément à**: `rag_pipeline_documentation.md`
**Date**: 2025-01-24

Ce document contient des diagrammes Mermaid détaillés pour visualiser l'architecture et les flux de données du système RAG.

---

## 1. Architecture globale des services

```mermaid
graph TB
    subgraph "Frontend Layer"
        UI[React Frontend<br/>Port: 5173<br/>Vite Dev Server]
    end

    subgraph "API Layer"
        API[FastAPI Web API<br/>Port: 8000<br/>Async/Await]
        WORKER[Ingestion Worker<br/>Async Background<br/>Poll: 3s]
    end

    subgraph "Intelligence Layer"
        EMB[Embeddings Service<br/>E5-Large 1024-dim<br/>Port: 8001]
        RERANK[Reranker Service<br/>BGE-M3 CrossEncoder<br/>Port: 8002]
        VLM[VLM Service<br/>InternVL3_5-8B<br/>Remote API]
    end

    subgraph "LLM Providers"
        MISTRAL[Mistral API<br/>Function Calling<br/>Streaming]
        GENERIC[Generic OpenAI<br/>Ollama/LiteLLM/etc<br/>Compatible]
    end

    subgraph "Storage Layer"
        PG[(PostgreSQL 15+<br/>PGVector Extension<br/>IVFFlat Index)]
        VOL[/Shared Volume<br/>/app/uploads/<br/>Documents + Images/]
    end

    UI -->|HTTP/REST| API
    API -->|Job Queue| PG
    API -->|Embed Query| EMB
    API -->|Rerank Results| RERANK
    API -->|Chat Completion| MISTRAL
    API -->|Chat Completion| GENERIC
    API -->|Vector Search| PG

    WORKER -->|Poll Jobs| PG
    WORKER -->|Read Files| VOL
    WORKER -->|Parse Documents| WORKER
    WORKER -->|Embed Chunks| EMB
    WORKER -->|Extract Images| VLM
    WORKER -->|Save Data| PG

    API -->|Save Files| VOL

    style UI fill:#e1f5ff
    style API fill:#fff4e1
    style WORKER fill:#fff4e1
    style EMB fill:#e8f5e9
    style RERANK fill:#e8f5e9
    style VLM fill:#e8f5e9
    style MISTRAL fill:#f3e5f5
    style GENERIC fill:#f3e5f5
    style PG fill:#fce4ec
    style VOL fill:#fce4ec
```

---

## 2. Flux d'ingestion détaillé (avec VLM)

```mermaid
sequenceDiagram
    autonumber
    participant User
    participant UI as Frontend
    participant API as Web API
    participant DB as PostgreSQL
    participant Vol as /uploads/
    participant W as Worker
    participant Doc as Docling
    participant VLM as VLM API
    participant Emb as Embeddings

    User->>UI: Upload document.pdf (100MB max)
    UI->>API: POST /api/documents/upload<br/>multipart/form-data

    rect rgb(255, 250, 240)
    Note over API,Vol: Phase 1: Reception & Storage
    API->>API: Validate file (type, size)
    API->>API: Generate job_id (UUID)
    API->>Vol: Save to /uploads/{job_id}/doc.pdf
    API->>DB: INSERT ingestion_jobs<br/>(status=pending, progress=0)
    API-->>UI: Return {job_id, status}
    end

    UI->>UI: Start polling (2s interval)
    UI->>API: GET /api/jobs/{job_id}
    API->>DB: SELECT * FROM ingestion_jobs
    API-->>UI: {status: pending, progress: 0}

    rect rgb(240, 255, 240)
    Note over W,Emb: Phase 2: Worker Processing

    loop Every 3 seconds
        W->>DB: SELECT * FROM ingestion_jobs<br/>WHERE status='pending'<br/>LIMIT 1
    end

    DB-->>W: Return pending job
    W->>DB: UPDATE status='processing'<br/>started_at=NOW()
    W->>Vol: Read /uploads/{job_id}/doc.pdf

    W->>Doc: DocumentConverter.convert(pdf_path)
    Doc->>Doc: Parse PDF structure
    Doc->>Doc: Extract text + layout
    Doc->>Doc: Detect images in pages
    Doc-->>W: DoclingDocument + markdown + image_refs

    W->>DB: UPDATE progress=30

    alt VLM_ENABLED=true
        loop For each image in document
            W->>Vol: Save image.png
            W->>VLM: POST /extract-and-describe<br/>multipart: image.png
            VLM->>VLM: InternVL analysis
            VLM-->>W: {description, ocr_text}

            alt Image too small
                W->>W: Filter out (min 200x200)
            else Image valid
                W->>W: Store ImageMetadata
            end
        end
        W->>DB: UPDATE progress=40
    end

    W->>W: HybridChunker.chunk_document()<br/>max_tokens=800
    W->>W: Create synthetic image chunks
    W->>DB: UPDATE progress=60

    W->>Emb: POST /embed_batch<br/>chunks (batch: 20)
    Emb->>Emb: E5-Large encoding
    Emb-->>W: embeddings (1024-dim vectors)
    W->>DB: UPDATE progress=80

    W->>DB: BEGIN TRANSACTION
    W->>DB: INSERT INTO documents<br/>RETURNING id

    loop For each chunk
        W->>DB: INSERT INTO chunks<br/>(embedding::vector)
    end

    loop For each image
        W->>DB: INSERT INTO document_images<br/>(chunk_id, base64, description)
    end

    W->>DB: COMMIT
    W->>DB: UPDATE progress=100<br/>status='completed'
    W->>Vol: DELETE /uploads/{job_id}/
    end

    UI->>API: GET /api/jobs/{job_id}
    API->>DB: SELECT * FROM ingestion_jobs
    API-->>UI: {status: completed, progress: 100}
    UI-->>User: ✅ Document ingested successfully
```

---

## 3. Flux de recherche vectorielle avec reranking

```mermaid
sequenceDiagram
    autonumber
    participant User
    participant API
    participant Emb as Embeddings
    participant DB as PostgreSQL
    participant Rerank as Reranker

    User->>API: Question: "Politique télétravail?"

    rect rgb(255, 245, 230)
    Note over API,Emb: Phase 1: Embedding Generation
    API->>Emb: POST /embed<br/>{text: "Politique télétravail?"}
    Emb->>Emb: E5-Large encoding
    Emb-->>API: embedding: [0.123, -0.456, ...]<br/>(1024 floats)
    end

    rect rgb(230, 245, 255)
    Note over API,DB: Phase 2: Vector Search

    alt Reranking enabled (RERANKER_ENABLED=true)
        API->>API: search_limit = RERANKER_TOP_K (20)
        API->>DB: SELECT c.*, d.*,<br/>1 - (embedding <=> $1) as similarity<br/>ORDER BY embedding <=> $1<br/>LIMIT 20

        Note over DB: IVFFlat Index<br/>Approximate search<br/>~10% of lists scanned

        DB-->>API: 20 candidate chunks

        rect rgb(245, 255, 245)
        Note over API,Rerank: Phase 3: Reranking
        API->>Rerank: POST /rerank<br/>{query, documents: [20], top_k: 5}
        Rerank->>Rerank: BGE-reranker-v2-m3<br/>CrossEncoder scoring
        Rerank->>Rerank: Sort by relevance score
        Rerank-->>API: Top 5 reranked documents
        end

    else Reranking disabled
        API->>API: search_limit = 5
        API->>DB: SELECT ... LIMIT 5
        DB-->>API: 5 most similar chunks
    end
    end

    rect rgb(255, 240, 245)
    Note over API,DB: Phase 4: Image Retrieval
    API->>DB: SELECT * FROM document_images<br/>WHERE chunk_id = ANY($1)
    DB-->>API: Associated images<br/>(base64, description, OCR)
    end

    API->>API: Format sources with images
    API->>API: Save to _current_request_sources
    API-->>User: Sources ready for LLM
```

---

## 4. Flux de génération de réponse (Function Calling)

```mermaid
sequenceDiagram
    autonumber
    participant User
    participant API
    participant Reform as Reformulation
    participant LLM
    participant Tool as search_knowledge_base_tool
    participant DB

    User->>API: "Et celle pour les managers?"

    rect rgb(255, 250, 245)
    Note over API,Reform: Contextual Reference Detection
    API->>API: Detect pronouns: "celle"
    API->>Reform: reformulate_question_with_context()
    Reform->>LLM: Mistral API with history
    LLM-->>Reform: "Quelle est la politique de<br/>télétravail pour les managers?"
    Reform-->>API: Reformulated question
    end

    rect rgb(245, 250, 255)
    Note over API,LLM: Agent Creation
    API->>API: Initialize globals:<br/>_current_request_sources = []<br/>_current_conversation_id = conv_id
    API->>API: Create PydanticAI Agent<br/>tools=[search_knowledge_base_tool]
    API->>API: system_prompt =<br/>build_tool_system_prompt_with_json()
    end

    rect rgb(250, 255, 245)
    Note over API,Tool: Agent Execution
    API->>LLM: agent.run(reformulated_question,<br/>message_history=[])

    Note over LLM: History empty →<br/>MUST call tool

    LLM->>LLM: Analyze question
    LLM->>LLM: Decide to call tool
    LLM->>Tool: search_knowledge_base_tool(<br/>query="politique télétravail managers",<br/>limit=5)

    Tool->>Tool: Generate embedding
    Tool->>Tool: Vector search + rerank
    Tool->>DB: Fetch chunks + images
    DB-->>Tool: Results
    Tool->>Tool: Save to _current_request_sources
    Tool-->>LLM: Formatted results text

    LLM->>LLM: Generate response from results
    LLM-->>API: Response content
    end

    rect rgb(255, 245, 250)
    Note over API,DB: Source Retrieval & Save
    API->>API: sources = _current_request_sources.copy()
    API->>DB: INSERT INTO messages<br/>(role='user', content)
    API->>DB: INSERT INTO messages<br/>(role='assistant', content, sources)
    end

    API-->>User: {content, sources, images}
```

---

## 5. Schéma de base de données complet

```mermaid
erDiagram
    DOCUMENTS ||--o{ CHUNKS : contains
    DOCUMENTS ||--o{ DOCUMENT_IMAGES : contains
    CHUNKS ||--o{ DOCUMENT_IMAGES : associated
    DOCUMENTS ||--o{ INGESTION_JOBS : tracked_by

    USERS ||--o{ CONVERSATIONS : creates
    CONVERSATIONS ||--o{ MESSAGES : contains
    MESSAGES ||--o{ MESSAGE_RATINGS : rated_by

    DOCUMENTS {
        uuid id PK
        text title
        text source
        text content
        jsonb metadata
        timestamp created_at
        timestamp updated_at
    }

    CHUNKS {
        uuid id PK
        uuid document_id FK
        text content
        vector_1024 embedding
        int chunk_index
        jsonb metadata
        int token_count
        timestamp created_at
    }

    DOCUMENT_IMAGES {
        uuid id PK
        uuid document_id FK
        uuid chunk_id FK
        int page_number
        jsonb position
        varchar image_path
        text image_base64
        varchar image_format
        int image_size_bytes
        text description
        text ocr_text
        float confidence_score
        jsonb metadata
        timestamp created_at
    }

    INGESTION_JOBS {
        uuid id PK
        varchar filename
        int file_size
        varchar status
        int progress
        uuid document_id FK
        int chunks_created
        text error_message
        timestamp created_at
        timestamp started_at
        timestamp completed_at
    }

    USERS {
        uuid id PK
        varchar username
        varchar email
        varchar password_hash
        varchar first_name
        varchar last_name
        boolean is_admin
        boolean must_change_password
        timestamp created_at
        timestamp updated_at
    }

    CONVERSATIONS {
        uuid id PK
        uuid user_id FK
        text title
        boolean reranking_enabled
        boolean archived
        timestamp created_at
        timestamp updated_at
    }

    MESSAGES {
        uuid id PK
        uuid conversation_id FK
        varchar role
        text content
        jsonb sources
        varchar model_name
        jsonb token_usage
        timestamp created_at
    }

    MESSAGE_RATINGS {
        uuid id PK
        uuid message_id FK
        int rating
        text comment
        timestamp created_at
    }
```

---

## 6. Flux de chunking avec HybridChunker

```mermaid
graph TB
    START[Document Content] --> DOCLING[Docling Parse]
    DOCLING --> STRUCT[DoclingDocument<br/>Structure Tree]

    STRUCT --> CHUNKER{HybridChunker}

    CHUNKER --> SECT[Section Detection]
    SECT --> HEAD[Heading Hierarchy]
    HEAD --> PARA[Paragraph Boundaries]
    PARA --> TABLE[Table Preservation]
    TABLE --> CODE[Code Block Handling]

    CODE --> TOKEN[Token-Aware Split<br/>max_tokens=800]

    TOKEN --> MERGE{Merge Peers?}
    MERGE -->|Small sections| FUSE[Fuse with neighbors]
    MERGE -->|Large sections| SPLIT[Split into chunks]

    FUSE --> CONTEXT[Add Context<br/>Heading hierarchy]
    SPLIT --> CONTEXT

    CONTEXT --> META[Add Metadata<br/>page_number, chunk_method]

    META --> CHUNKS[List of DocumentChunk]

    CHUNKS --> SYNTHETIC{Images Present?}
    SYNTHETIC -->|Yes| IMG_CHUNKS[Create Synthetic<br/>Image Chunks]
    SYNTHETIC -->|No| FINAL

    IMG_CHUNKS --> COMBINE[Combine Text + Image Chunks]
    COMBINE --> FINAL[Final Chunk List]

    FINAL --> EMBED[Batch Embedding<br/>20 chunks/batch]
    EMBED --> SAVE[Save to PostgreSQL]

    style START fill:#e1f5ff
    style CHUNKER fill:#fff4e1
    style CHUNKS fill:#e8f5e9
    style SYNTHETIC fill:#f3e5f5
    style FINAL fill:#fce4ec
```

---

## 7. Comparaison des modes d'exécution

```mermaid
graph TB
    subgraph "Mode 1: Function Calling (LLM_USE_TOOLS=true)"
        FC_START[User Question] --> FC_REFORM[Reformulate if needed]
        FC_REFORM --> FC_AGENT[Create Agent<br/>with tools]
        FC_AGENT --> FC_PROMPT[System Prompt<br/>+ JSON Tool Definition]
        FC_PROMPT --> FC_RUN[Run Agent<br/>message_history=[]]
        FC_RUN --> FC_LLM[LLM Analysis]
        FC_LLM --> FC_CALL[LLM Calls Tool]
        FC_CALL --> FC_SEARCH[search_knowledge_base_tool]
        FC_SEARCH --> FC_SAVE[Save sources to global]
        FC_SAVE --> FC_RETURN[Return results to LLM]
        FC_RETURN --> FC_GEN[LLM Generates Response]
        FC_GEN --> FC_RETRIEVE[Retrieve sources from global]
        FC_RETRIEVE --> FC_RESP[Response + Sources]
    end

    subgraph "Mode 2: Manual Injection (LLM_USE_TOOLS=false)"
        MI_START[User Question] --> MI_SEARCH[Execute search_knowledge_base_tool<br/>manually]
        MI_SEARCH --> MI_SAVE[Save sources to global]
        MI_SAVE --> MI_COPY[Copy sources locally]
        MI_COPY --> MI_INJECT[Inject results in<br/>system prompt]
        MI_INJECT --> MI_SUMMARY[Add conversation summary<br/>last 2 exchanges]
        MI_SUMMARY --> MI_AGENT[Create Agent<br/>NO tools]
        MI_AGENT --> MI_RUN[Run Agent<br/>with enhanced message]
        MI_RUN --> MI_LLM[LLM Generates Response<br/>from context]
        MI_LLM --> MI_RESP[Response + Sources]
    end

    style FC_START fill:#e3f2fd
    style FC_CALL fill:#fff9c4
    style FC_SEARCH fill:#c8e6c9
    style FC_RESP fill:#f8bbd0

    style MI_START fill:#e3f2fd
    style MI_SEARCH fill:#c8e6c9
    style MI_INJECT fill:#fff9c4
    style MI_RESP fill:#f8bbd0
```

---

## 8. Gestion des variables globales

```mermaid
sequenceDiagram
    autonumber
    participant REQ as Request Handler
    participant GLOBAL as Global Variables
    participant AGENT as PydanticAI Agent
    participant TOOL as search_knowledge_base_tool
    participant LLM

    Note over REQ,LLM: Request Start
    REQ->>GLOBAL: _current_request_sources = []
    REQ->>GLOBAL: _current_conversation_id = conv_id
    REQ->>GLOBAL: _current_reranking_enabled = preference

    REQ->>AGENT: Create agent with tools
    REQ->>AGENT: agent.run(message, [])

    AGENT->>LLM: Send message + tool definitions
    LLM->>LLM: Decide to call tool
    LLM->>TOOL: search_knowledge_base_tool(query)

    Note over TOOL: Async execution<br/>in isolated context

    TOOL->>TOOL: Perform vector search
    TOOL->>TOOL: Rerank results
    TOOL->>TOOL: Fetch images
    TOOL->>GLOBAL: _current_request_sources = sources
    TOOL-->>LLM: Return formatted text

    Note over GLOBAL: Sources persisted<br/>in global variable

    LLM->>LLM: Generate response
    LLM-->>AGENT: Response content
    AGENT-->>REQ: Result object

    REQ->>GLOBAL: sources = _current_request_sources.copy()
    REQ->>REQ: Build final response

    Note over REQ: Response Complete<br/>Globals will be reset<br/>on next request
```

**Pourquoi des globales?**
1. **PydanticAI limitation**: ContextVar perd son état en async
2. **FastAPI séquentiel**: Pas de race condition entre requêtes
3. **Simplicité**: Alternative (Redis) = overhead inutile
4. **Pattern éprouvé**: Fonctionne dans tous les cas testés

---

## 9. Pipeline VLM (Vision Language Model)

```mermaid
graph TB
    START[PDF Document] --> DOCLING[Docling Parser]
    DOCLING --> DETECT[Detect Images<br/>in Pages]

    DETECT --> EXTRACT[Extract Image Data<br/>position, size]

    EXTRACT --> FILTER{Image Filter}
    FILTER -->|Too small| SKIP[Skip image<br/>< 200x200px]
    FILTER -->|Aspect ratio wrong| SKIP
    FILTER -->|Valid| SAVE[Save to /uploads/images/]

    SAVE --> ENCODE[Encode to base64]
    ENCODE --> VLM[Call VLM API]

    VLM --> ANALYZE[InternVL3_5-8B Analysis]
    ANALYZE --> DESC[Generate Description]
    ANALYZE --> OCR[Extract Text (OCR)]

    DESC --> METADATA[Create ImageMetadata]
    OCR --> METADATA

    METADATA --> LINK{Link to Chunk}
    LINK -->|Match page_number| CHUNK[Find corresponding chunk]
    LINK -->|No match| FIRST[Link to first chunk]

    CHUNK --> DB_IMG[Save to document_images]
    FIRST --> DB_IMG

    DB_IMG --> SYNTHETIC[Create Synthetic Chunk]

    SYNTHETIC --> CONTENT[Chunk Content:<br/>- Document context<br/>- Image description<br/>- OCR text<br/>- Keywords]

    CONTENT --> EMBED[Embed Synthetic Chunk]
    EMBED --> DB_CHUNK[Save to chunks table]

    DB_CHUNK --> SEARCH[Image searchable in RAG]

    style START fill:#e1f5ff
    style FILTER fill:#fff4e1
    style VLM fill:#e8f5e9
    style SYNTHETIC fill:#f3e5f5
    style SEARCH fill:#c8e6c9
```

---

## 10. Reranking Pipeline détaillé

```mermaid
sequenceDiagram
    autonumber
    participant API
    participant VectorDB as PostgreSQL
    participant Reranker as BGE-M3 Service

    Note over API: Reranking Configuration Check
    API->>API: Check reranking preference<br/>1. Request override<br/>2. Conversation setting<br/>3. Global env var

    alt Reranking Enabled
        API->>VectorDB: Vector search<br/>LIMIT RERANKER_TOP_K (20)
        Note over VectorDB: IVFFlat Index<br/>Fast approximate search
        VectorDB-->>API: 20 candidate chunks

        rect rgb(255, 250, 240)
        Note over API,Reranker: CrossEncoder Reranking
        API->>Reranker: POST /rerank<br/>{query, documents[20], top_k=5}

        Reranker->>Reranker: For each (query, document) pair:
        Reranker->>Reranker: - Concatenate: [query] [SEP] [doc]
        Reranker->>Reranker: - Pass through BGE-M3
        Reranker->>Reranker: - Get relevance score

        Reranker->>Reranker: Sort by score (descending)
        Reranker->>Reranker: Return top 5

        Reranker-->>API: Top 5 reranked documents<br/>with scores
        end

        API->>API: Final results: Top 5

    else Reranking Disabled
        API->>VectorDB: Vector search<br/>LIMIT 5 (direct)
        VectorDB-->>API: Top 5 chunks
        API->>API: Final results: Top 5
    end

    Note over API: Performance Impact:<br/>Reranking: +100-300ms<br/>Accuracy: +20-30%
```

**Explication des étapes**:
1. **Vérification config**: Priorité request > conversation > global
2. **Candidates**: Top-20 pour avoir plus de choix pour le reranker
3. **CrossEncoder**: Analyse fine de chaque paire (query, document)
4. **Score**: Plus précis que similarité cosine seule
5. **Fallback**: Si erreur, retourne top-5 du vector search

---

## Conclusion des diagrammes

Ces diagrammes couvrent:
- ✅ Architecture globale des services
- ✅ Flux d'ingestion avec VLM
- ✅ Recherche vectorielle + reranking
- ✅ Génération de réponse (function calling)
- ✅ Schéma de base de données
- ✅ Chunking HybridChunker
- ✅ Comparaison modes d'exécution
- ✅ Gestion variables globales
- ✅ Pipeline VLM
- ✅ Reranking détaillé

**Utilisation**:
- Ces diagrammes sont en format Mermaid
- Affichables dans GitHub, GitLab, VS Code (extensions)
- Exportables en PNG/SVG via mermaid-cli

**Pour aller plus loin**:
- Consulter `rag_pipeline_documentation.md` pour détails textuels
- Explorer le code source pour implémentation exacte
- Tester les différents modes avec variables d'environnement

---

**Dernière mise à jour**: 2025-01-24
