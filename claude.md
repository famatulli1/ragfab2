# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RAGFab is a dual-provider RAG (Retrieval Augmented Generation) system optimized for French, with both a CLI application and a web interface. The system supports any OpenAI-compatible LLM API through a generic provider system.

**Key Features**:
- Generic LLM provider (Mistral, Ollama, OpenAI, etc.)
- Hybrid Search (semantic + keyword with RRF fusion)
- Multi-user with role-based access
- Product Universes for document segmentation
- VLM image extraction (PaddleOCR-VL / InternVL)
- Automatic database migrations

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                         DOCKER / COOLIFY                             │
│                                                                      │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────────────┐ │
│  │ Embeddings API │  │ Reranker API   │  │ PostgreSQL + PGVector  │ │
│  │ (E5-Large)     │  │ (BGE-M3)       │  │ (documents + chunks)   │ │
│  │ Port: 8001     │  │ Port: 8002     │  │ Port: 5432             │ │
│  └────────────────┘  └────────────────┘  └────────────────────────┘ │
│                                                                      │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────────────┐ │
│  │ Web API        │  │ Ingestion      │  │ Frontend (React)       │ │
│  │ (FastAPI)      │  │ Worker         │  │ Port: 5173             │ │
│  │ Port: 8000     │  │                │  │                        │ │
│  └────────────────┘  └────────────────┘  └────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

**Key Data Flow**:
1. User sends question → Question reformulation (if contextual references)
2. Reformulated question → RAG agent with tool calling
3. `search_knowledge_base_tool()` → Vector search (+ optional reranking/hybrid)
4. Sources stored in `_current_request_sources` global variable
5. Final response generated with sources

> **Implementation Details**: See `claudedocs/history/` for detailed implementation documentation.

## Development Commands

### Docker Setup

```bash
# Start full stack
docker-compose up -d

# Rebuild after code changes
docker-compose build ragfab-api ragfab-frontend ingestion-worker

# View logs
docker-compose logs -f ragfab-api
docker-compose logs -f ingestion-worker
```

### Testing

```bash
# Backend tests (rag-app)
cd rag-app && pytest -m unit

# Backend tests (web-api)
cd web-api && pytest -m unit

# Frontend
cd frontend && npm test && npm run lint
```

### Document Ingestion (via Admin Interface)

```bash
# 1. Access admin interface
open http://localhost:3000/admin  # Login: admin / admin

# 2. Upload documents via drag & drop
# - Supported: PDF, DOCX, MD, TXT, HTML
# - Select OCR engine (RapidOCR, EasyOCR, Tesseract)
# - Select VLM engine (PaddleOCR-VL, InternVL, None)
# - Select Chunker type (Hybrid, Parent-Child)

# 3. Monitor ingestion
docker-compose logs -f ingestion-worker
```

## Critical Implementation Details

### Global State Management

**Critical**: `_current_request_sources` (List[dict]) passes sources between `search_knowledge_base_tool()` and response handler.

**Why not ContextVar?**: PydanticAI's async tool execution loses ContextVar state. Global variable works with FastAPI's async processing.

Location: `web-api/app/main.py` line 50

### PydanticAI Tools

- ❌ Don't use `run_stream()` with tools
- ✅ Use `run()` for automatic tool execution
- ❌ Don't pass history when you need tool calling
- ✅ Pass empty `message_history=[]` to force tool calls

### Database Schema

- Embedding dimension: **1024** (multilingual-e5-large)
- Vector type: `vector(1024)`
- Schema files: `database/schema.sql`, `database/02_web_schema.sql`

### Chunking Strategy

| Chunker | Best For | Details |
|---------|----------|---------|
| **Hybrid** (default) | Structured docs | Respects headings, tables, lists |
| **Parent-Child** | Long narratives | Parent (2000t) → Children (~600t) |

## Environment Configuration

### Essential Variables

```bash
# Generic LLM Configuration
LLM_API_URL=https://api.mistral.ai
LLM_API_KEY=your_api_key_here
LLM_MODEL_NAME=mistral-small-latest
LLM_USE_TOOLS=true  # true = function calling, false = manual injection

# Database
DATABASE_URL=postgresql://raguser:pass@postgres:5432/ragdb

# Embeddings
EMBEDDINGS_API_URL=http://embeddings:8001
EMBEDDING_DIMENSION=1024

# Search Features (optional)
HYBRID_SEARCH_ENABLED=false
RERANKER_ENABLED=false
USE_ADJACENT_CHUNKS=true
USE_PARENT_CHILD_CHUNKS=false

# VLM Image Extraction (optional)
VLM_ENABLED=false
IMAGE_PROCESSOR_ENGINE=internvl  # or paddleocr-vl, none
DOCLING_OCR_ENGINE=rapidocr      # or easyocr, tesseract
```

### Coolify Deployment

- Use `ragfab-` prefix for containers
- Use `.internal` suffix for internal services (e.g., `postgres.internal`)
- Set environment variables via Coolify interface

## Common Pitfalls

| Issue | Cause | Fix |
|-------|-------|-----|
| Test failures with MagicMock | Pydantic v2 rejects MagicMock | Use real dependencies |
| `**/*.pdf` misses root files | Glob limitation | Use two patterns |
| Container name conflicts | Coolify multi-project | Use unique prefixes |
| Tool not called | History passed to agent | Pass `message_history=[]` |

## Frontend Architecture

**Stack**: React 18 + TypeScript + Vite + TailwindCSS

**Key files**:
- API client: `frontend/src/lib/api.ts`
- State: React hooks (no global state library)
- Routing: react-router-dom

## Testing Philosophy

- Unit tests: Business logic focus
- Integration tests: Marked with `@pytest.mark.embeddings`
- Coverage threshold: 20% (realistic baseline)
- Use real dependencies when possible

## Git Workflow

```
🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

## Database Migrations System

Automatic migration system at container rebuild.

**Workflow**:
```bash
git pull origin main
docker-compose up -d --build  # Migrations apply automatically
```

**Creating migrations**:
```bash
# 1. Create file with numeric prefix
touch database/migrations/XX_description.sql

# 2. Use idempotent patterns
ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(255);

# 3. Rebuild (applies automatically)
docker-compose up -d --build
```

**Naming**: `XX_snake_case_description.sql` (e.g., `08_add_document_tags.sql`)

## Common Development Scenarios

### Adding a New LLM Provider

1. Create provider in `web-api/app/utils/`
2. Implement OpenAI-compatible interface
3. Update `execute_rag_agent()` in `main.py`
4. Add env vars to `.env.example`

### Debugging Sources Not Appearing

1. Check `_current_request_sources` initialization
2. Verify tool saves sources to global variable
3. Check logs for "📚 Sources récupérées"

### Performance Tuning

- Embeddings: Batch size 20, timeout 90s
- PostgreSQL: HNSW index on embeddings
- Vector search: Cosine distance, default 5 results

## Gestion des Univers Produits

Les **Univers Produits** segmentent la base de connaissances par gamme.

**Tables**:
- `product_universes` - Définition des univers
- `user_universe_access` - Accès utilisateur-univers
- `documents.universe_id` - Association document-univers

**Routes API** (`web-api/app/routes/universes.py`):
- `GET /api/universes` - Liste univers
- `GET /api/universes/me/access` - Mes univers
- `POST /api/universes/users/{id}/access` - Accorder accès

**Filtrage RAG**: Automatique via `universe_ids[]` dans les requêtes chat.

---

## Archived Documentation

Detailed implementation history moved to `claudedocs/history/`:

- `RAG_PIPELINE_OPTIMIZATIONS_2025-01-24.md` - Conversational context, adjacent chunks, parent-child chunking
- `HYBRID_SEARCH_SYSTEM_2025-01-31.md` - RRF fusion, adaptive alpha, French optimization
- `QUALITY_MANAGEMENT_FIXES_2025-01-06.md` - Reingestion sync, HTTP 422 fixes

Additional guides in `claudedocs/`:
- `HYBRID_SEARCH_TESTING_GUIDE.md` - Testing procedures
- `rag_pipeline_documentation.md` - Full pipeline documentation
- `THUMBS_DOWN_VALIDATION_SYSTEM.md` - Quality management system
