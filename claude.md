# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RAGFab is a dual-provider RAG (Retrieval Augmented Generation) system optimized for French, with both a CLI application and a web interface. The system supports two LLM providers:
- **Chocolatine** (local vLLM): Manual context injection
- **Mistral** (API): Automatic function calling with tools

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      DOCKER / COOLIFY                           │
│                                                                 │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐ │
│  │ Embeddings API   │  │ Reranker API     │  │ PostgreSQL   │ │
│  │ (E5-Large)       │  │ (BGE-M3)         │  │ + PGVector   │ │
│  │ Port: 8001       │  │ Port: 8002       │  │ Port: 5432   │ │
│  └────────┬─────────┘  └────────┬─────────┘  └──────┬───────┘ │
│           │                     │                    │         │
│           └─────────────────────┼────────────────────┘         │
│                                 │                              │
│                       ┌─────────▼─────────┐                    │
│                       │ Web API (FastAPI) │                    │
│                       │ Port: 8000        │                    │
│                       └─────────┬─────────┘                    │
│                                 │                              │
│                       ┌─────────▼─────────┐                    │
│                       │ Frontend (React)  │                    │
│                       │ Port: 5173        │                    │
│                       └───────────────────┘                    │
└─────────────────────────────────────────────────────────────────┘
```

### Key Data Flow

**Question Reformulation (Mistral with tools only)**:
1. User sends question → `reformulate_question_with_context()` detects contextual references
2. If reference detected → Calls Mistral API to reformulate question autonomously
3. Reformulated question sent to RAG agent → Forces tool calling (no history passed)
4. Tool `search_knowledge_base_tool()` is called → Performs vector search (optionally with reranking)
5. Sources stored in `_current_request_sources` global variable
6. Final response generated with sources displayed in frontend

**Vector Search + Reranking Pipeline** (when `RERANKER_ENABLED=true`):
1. Question → Embedding (E5-Large) → Vector similarity search (top-20 candidates)
2. Top-20 candidates → Reranker service (BGE-reranker-v2-m3) → CrossEncoder scoring
3. Reranked results (top-5 most relevant) → LLM context
4. If reranker fails → Graceful fallback to top-5 from vector search

**Vector Search Only Pipeline** (when `RERANKER_ENABLED=false`):
1. Question → Embedding (E5-Large) → Vector similarity search (top-5 direct)
2. Top-5 results → LLM context

**Critical Pattern**: Global variable `_current_request_sources` is used instead of `ContextVar` because PydanticAI's async tool execution loses ContextVar state between calls.

## Development Commands

### Docker Setup

```bash
# Start core services (PostgreSQL + Embeddings + Reranker)
docker-compose up -d postgres embeddings reranker

# Start web stack (includes frontend + web-api)
docker-compose --profile web up -d

# Rebuild after code changes
docker-compose build web-api
docker-compose build frontend
docker-compose build reranker

# View logs
docker-compose logs -f web-api
docker-compose logs -f frontend
docker-compose logs -f reranker
```

### Testing

```bash
# Backend tests (rag-app)
cd rag-app
pytest -m unit  # Unit tests only
pytest -m "unit and not embeddings"  # Exclude embeddings tests
pytest --cov=. --cov-report=html  # With coverage

# Backend tests (web-api)
cd web-api
pytest -m unit
pytest --cov=app --cov-report=term --cov-fail-under=20

# Frontend
cd frontend
npm test  # Run tests
npm run lint  # ESLint
```

**Important**: Coverage threshold is currently set to 20% (realistic baseline). Tests requiring the embeddings service are marked with `@pytest.mark.embeddings` and excluded from CI.

### Document Ingestion

```bash
# Place PDFs in rag-app/documents/ then:
docker-compose --profile app run --rm rag-app python -m ingestion.ingest

# Verify ingestion
docker-compose exec postgres psql -U raguser -d ragdb -c "SELECT title, COUNT(c.id) as chunks FROM documents d LEFT JOIN chunks c ON d.id = c.document_id GROUP BY d.id, title;"
```

### Frontend Development

```bash
cd frontend
npm install
npm run dev  # Starts Vite dev server on port 5173
npm run build  # Production build
npm run preview  # Preview production build
```

## Critical Implementation Details

### Mistral Provider with PydanticAI

**File**: `rag-app/utils/mistral_provider.py`

Key implementation notes:
- `ArgsDict` must be imported from `pydantic_ai.messages` (NOT `pydantic_ai.models`)
- Tool arguments must be extracted with `part.args.args_dict` before JSON serialization
- `ToolReturnPart` must be processed in `ModelRequest` formatting (NOT `ModelResponse`)
- Message order is strict: system → user → assistant (with tool_calls) → tool (with results)

### Question Reformulation System

**File**: `web-api/app/main.py` (lines 847-946)

Detects contextual references and reformulates questions before RAG execution:

**Strong references** (always reformulated): celle, celui, celles, ceux
**Medium references** (only if question <8 words): ça, cela, ce, cette, ces
**Pronouns at start** (only if first word): il, elle, ils, elles, y, en
**Pattern matching**: Questions starting with "et celle", "et celui", "et ça"

Generic articles ("le", "la", "les") are NOT treated as references to avoid false positives.

### Global State Management

**Critical**: `_current_request_sources` is a global variable (List[dict]) used to pass sources between `search_knowledge_base_tool()` and the response handler.

**Why not ContextVar?**: PydanticAI's async tool execution context loses ContextVar state between the tool call and result retrieval. Global variable works because FastAPI processes requests sequentially with async.

Location: `web-api/app/main.py` line 50

### Dual Provider System

**Environment variable**: `RAG_PROVIDER` (values: "mistral" or "chocolatine")

**Mistral mode** (`provider="mistral"` and `use_tools=True`):
- Question reformulated if contextual references detected
- Agent created with `tools=[search_knowledge_base_tool]`
- NO history passed to agent (forces tool calling every time)
- Sources retrieved from global variable after execution

**Chocolatine/Mistral without tools**:
- Manual search executed BEFORE agent creation
- Context injected into system prompt
- History summary can be included (doesn't interfere with tool calling)

### Database Schema

**Important dimensions**:
- Embedding dimension: **1024** (multilingual-e5-large)
- Vector type in schema: `vector(1024)`

Changing embedding models requires:
1. Update `EMBEDDING_DIMENSION` in `.env`
2. Modify `database/schema.sql` vector dimensions
3. Drop and recreate `chunks` table

Schema files:
- `database/schema.sql`: Core RAG tables (documents, chunks)
- `database/02_web_schema.sql`: Web interface tables (conversations, messages, ratings)

### Chunking Strategy

**Docling HybridChunker** (preferred):
- Respects document structure (headings, paragraphs, tables)
- Falls back to SimpleChunker on error
- Configuration: `CHUNK_SIZE=1500`, `CHUNK_OVERLAP=200`

**SimpleChunker** (fallback):
- Splits on paragraph breaks (`\n\n`), NOT character count
- Test expectations must use multi-paragraph content

**Batch embedding**: 20 chunks per batch (timeout: 90s) to avoid API timeouts

### UTF-8 Handling

PDF documents often contain invalid UTF-8 surrogate characters. All chunk content must be cleaned:

```python
clean_content = content.encode('utf-8', errors='replace').decode('utf-8')
```

Location: Applied in both `rag_agent.py` and `web-api/app/main.py`

## Environment Configuration

### Critical Variables

```bash
# Provider selection
RAG_PROVIDER=mistral  # or "chocolatine"

# Database (update for Coolify with .internal suffix)
DATABASE_URL=postgresql://raguser:pass@postgres:5432/ragdb
POSTGRES_HOST=postgres  # Change to postgres.internal on Coolify

# Embeddings
EMBEDDINGS_API_URL=http://embeddings:8001
EMBEDDING_DIMENSION=1024

# Reranking (NEW - Activable à la demande)
RERANKER_ENABLED=false  # true pour activer le reranking (recommandé pour doc médicale/technique)
RERANKER_API_URL=http://reranker:8002
RERANKER_MODEL=BAAI/bge-reranker-v2-m3  # Modèle multilingue excellent pour le français
RERANKER_TOP_K=20  # Nombre de candidats avant reranking
RERANKER_RETURN_K=5  # Nombre de résultats finaux après reranking

# Mistral API
MISTRAL_API_KEY=your_key_here
MISTRAL_MODEL_NAME=mistral-small-latest  # Better function calling than open-mistral-7b
MISTRAL_TIMEOUT=120.0

# Chocolatine API (if using chocolatine provider)
CHOCOLATINE_API_URL=https://apigpt.mynumih.fr
CHOCOLATINE_API_KEY=  # Optional
```

### Coolify Deployment Notes

When deploying on Coolify:
1. Container names must have unique prefixes (e.g., `ragfab-postgres`, `ragfab-embeddings`, `ragfab-reranker`)
2. Use `postgres.internal` instead of `postgres` for DATABASE_URL
3. Use `reranker.internal` instead of `reranker` for RERANKER_API_URL
4. Update Traefik router names to match new container names
5. Set environment variables via Coolify interface

Recent fix: All containers renamed with `ragfab-` prefix to avoid conflicts.

### Reranking System (NEW)

**When to use reranking** (`RERANKER_ENABLED=true`):
- Documentation technique avec terminologie similaire (médical, juridique, scientifique)
- Beaucoup de concepts qui se chevauchent sémantiquement
- Base documentaire >1000 documents
- Besoin de précision maximale sur les résultats

**Performance impact**:
- Latence additionnelle: +100-300ms par requête
- Ressources: ~4GB RAM pour le service reranker
- Avantage: Meilleure pertinence des résultats (jusqu'à 20-30% d'amélioration)

**How it works**:
1. Vector search récupère top-20 candidats (au lieu de 5)
2. CrossEncoder (BGE-reranker-v2-m3) analyse finement chaque paire (question, document)
3. Top-5 documents vraiment pertinents sont retournés au LLM
4. Fallback gracieux si le service reranker échoue (utilise top-5 du vector search)

**Configuration**:
```bash
RERANKER_ENABLED=true  # Activer le reranking
RERANKER_TOP_K=20      # Augmenter si base très large (max 50)
RERANKER_RETURN_K=5    # Nombre final de chunks pour le LLM
```

## Common Pitfalls

### PydanticAI Tools
- ❌ Don't use `run_stream()` with tools - it detects but doesn't execute them automatically
- ✅ Use `run()` for automatic tool execution workflow
- ❌ Don't pass history when you need tool calling - model will skip tool and answer from context
- ✅ Pass empty `message_history=[]` to force tool calls

### Test Failures
- Pydantic v2 strictly validates types and **rejects MagicMock** objects
- Don't mock tokenizers in tests - use real tokenizers (~200ms load time acceptable)
- `DocumentChunk` requires: content, index, start_char, end_char, metadata, token_count (NOT id, source, title)

### Glob Patterns
- Pattern `**/*.pdf` does NOT find files at root directory
- Always use two globs: one for root, one for subdirectories

### Container Naming
- Coolify environments may have multiple projects
- Always use unique prefixes (e.g., `ragfab-postgres` instead of just `postgres`)
- Update DATABASE_URL and service references when renaming containers

## Frontend Architecture

**Stack**: React 18 + TypeScript + Vite + TailwindCSS
**Key libraries**: react-router-dom, axios, react-markdown, lucide-react

**State management**: No global state library - uses React hooks and local component state

**API integration**: Axios client in `frontend/src/lib/api.ts`

**Document viewing**: Supports source document viewing with chunk highlighting

**Markdown rendering**: Uses react-markdown with syntax highlighting (react-syntax-highlighter)

## Testing Philosophy

- Unit tests focus on business logic, not implementation details
- Integration tests require actual services (marked with `@pytest.mark.embeddings`)
- Coverage threshold: 20% (realistic baseline, not aspirational 70%)
- Tests should use real dependencies when possible (e.g., real tokenizers, not mocks)

## Git Workflow

All commits should include:
- Clear description of problem solved
- Technical solution explanation
- List of changes with file references
- Standardized footer:

```
🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

## Common Development Scenarios

### Adding a New LLM Provider

1. Create provider file in `rag-app/utils/` or `web-api/app/utils/`
2. Implement `Model` or `AgentModel` interface from PydanticAI
3. Add factory function (e.g., `get_provider_model()`)
4. Update `execute_rag_agent()` in `web-api/app/main.py` with new provider logic
5. Add environment variables to `.env.example` and `docker-compose.yml`
6. Update documentation

### Modifying Chunking Strategy

1. Edit `rag-app/ingestion/chunker.py`
2. Update `ChunkingConfig` dataclass if adding parameters
3. Modify environment variables in `.env`
4. Re-ingest all documents to apply new strategy
5. Update tests in `rag-app/tests/unit/test_chunker.py`

### Adding New Database Tables

1. Add schema to `database/02_web_schema.sql` (or create new file `03_*.sql`)
2. Ensure files are mounted in `docker-compose.yml` under postgres volumes
3. Files execute in alphabetical order - use numeric prefixes
4. Recreate database or run migration manually for existing deployments

### Debugging Sources Not Appearing

Check in order:
1. `_current_request_sources` is properly initialized at request start
2. Tool execution saves sources to global variable
3. Sources retrieved from global variable after agent execution
4. Frontend correctly displays sources array from API response
5. Check logs for "📚 Sources récupérées" messages

### Performance Tuning

**Embeddings service**:
- Adjust batch size in `rag-app/ingestion/embedder.py` (currently 20)
- Increase timeout if needed (currently 90s)
- Monitor memory usage - model requires ~4-8GB RAM

**PostgreSQL**:
- Index on `embedding` column uses HNSW (configured in schema)
- Adjust `match_count` parameter for search results (default 5)
- Monitor query performance with `EXPLAIN ANALYZE`

**Vector Search**:
- Similarity threshold: 0.0 (no filtering by default)
- Uses cosine distance: `embedding <=> query_embedding`
- Results ordered by similarity (closest first)
