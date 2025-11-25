# Quality Management Fixes (2025-01-06)

> **Archived from CLAUDE.md** - This document contains the implementation details of quality management bug fixes.

## Overview

Two critical bugs in the Quality Management system were identified and fixed:
1. **Documents à réingérer not appearing**: Thumbs down validations weren't syncing to `document_quality_scores`
2. **Unblacklist/Whitelist failing with HTTP 422**: Missing `Body(...)` decorator causing FastAPI parameter validation errors

## Problem 1: Document Reingestion Sync Bug

**Root Cause**: Two independent tracking systems not synchronized:
- `thumbs_down_validations` table (populated automatically by AI analyzer)
- `document_quality_scores` table (used by "Documents à réingérer" tab)

**Symptoms**:
- Dashboard shows "1 Sources manquantes détectées" (from validations count)
- "Documents à réingérer" tab shows 0 documents (from quality_scores)
- Multiple thumbs down on same document in different conversations doesn't aggregate

**Solution Implemented**:
1. **Migration 18** (`database/migrations/18_sync_validation_quality.sql`):
   - Syncs existing validations to `document_quality_scores`
   - Creates SQL helper function `sync_validation_to_quality_scores()`
   - Audit log entries for sync operations

2. **Backend Sync Function** (`web-api/app/routes/analytics.py:21-84`):
   - `sync_validation_sources_to_quality_scores()` helper
   - Extracts chunk_ids from `sources_used` JSONB
   - INSERT ... ON CONFLICT for robust handling
   - Graceful error handling (doesn't block on failure)

3. **Admin Validation Hook** (`web-api/app/routes/analytics.py:1101-1116`):
   - Modified `validate_thumbs_down()` endpoint
   - Calls sync function when `admin_action = 'mark_for_reingestion'`
   - Includes classification and confidence in reason

4. **Auto-Creation Hook** (`web-api/app/services/thumbs_down_analyzer.py:410-458`):
   - Modified `_save_validation()` function
   - Auto-syncs when AI classifies as `missing_sources` with high confidence
   - Immediate sync after validation insertion

**Files Modified**:
- `database/migrations/18_sync_validation_quality.sql` (NEW)
- `web-api/app/routes/analytics.py` (sync function + hook)
- `web-api/app/services/thumbs_down_analyzer.py` (auto-sync on creation)

**Testing**:
```bash
# Apply migration
docker-compose exec postgres psql -U raguser -d ragdb -f /docker-entrypoint-initdb.d/18_sync_validation_quality.sql

# Verify sync function exists
docker-compose exec postgres psql -U raguser -d ragdb -c "\df sync_validation_to_quality_scores"

# Check synced documents
docker-compose exec postgres psql -U raguser -d ragdb -c "
SELECT d.title, dqs.needs_reingestion, dqs.analysis_notes
FROM document_quality_scores dqs
JOIN documents d ON dqs.document_id = d.id
WHERE dqs.needs_reingestion = true;"
```

## Problem 2: HTTP 422 on Unblacklist/Whitelist/Ignore Endpoints

**Root Cause**: FastAPI parameter ambiguity in POST requests:
- Parameter `reason: str` without decorator
- FastAPI defaults to **query string parameter** for POST
- Frontend sends **JSON body**: `{ "reason": "..." }`
- Parameter mismatch → HTTP 422 Unprocessable Entity

**Solution Implemented**:
Added `Body(...)` decorator to 3 endpoints:

1. **unblacklist_chunk** (`web-api/app/routes/analytics.py:557`)
2. **whitelist_chunk** (`web-api/app/routes/analytics.py:607`)
3. **ignore_reingestion_recommendation** (`web-api/app/routes/analytics.py:658`)

```python
# BEFORE (broken)
async def unblacklist_chunk(chunk_id: UUID, reason: str, ...)

# AFTER (fixed)
async def unblacklist_chunk(chunk_id: UUID, reason: str = Body(...), ...)
```

## Impact & Benefits

**Problem 1 Resolution**:
- ✅ Documents now appear immediately in "Documents à réingérer" tab
- ✅ Dashboard count matches actual documents needing reingestion
- ✅ Multi-conversation scenario works correctly
- ✅ Historical validations synced via migration
- ✅ Future validations auto-sync on creation + admin validation

**Problem 2 Resolution**:
- ✅ Unblacklist/Whitelist/Ignore endpoints work correctly
- ✅ Admin can manage chunk quality without errors
- ✅ JSON body properly parsed by FastAPI

## Architecture Notes

**Dual Sync Points**:
1. **Auto-Creation** (AI Analyzer): When confidence ≥ 0.7 and classification = 'missing_sources'
2. **Admin Validation**: When admin explicitly sets `admin_action = 'mark_for_reingestion'`

**Graceful Degradation**:
- Sync errors don't block validation creation
- Missing `sources_used` handled gracefully
- Logs warnings but continues operation

## Related Files

**Backend**:
- `web-api/app/routes/analytics.py` - Sync function + endpoint fixes
- `web-api/app/services/thumbs_down_analyzer.py` - Auto-sync on creation
- `database/migrations/18_sync_validation_quality.sql` - Migration

**Tests**:
- `web-api/tests/test_quality_fixes.py` - Unit tests for both fixes
