-- Migration 09: Add chunker type selection for document ingestion
-- Description: Allows per-job chunking strategy (hybrid vs parent-child)
-- Date: 2025-01-25
-- Author: Claude Code

-- ============================================
-- Add chunker_type column to ingestion_jobs
-- ============================================

ALTER TABLE ingestion_jobs
ADD COLUMN IF NOT EXISTS chunker_type VARCHAR(50) DEFAULT 'hybrid';

-- Update existing jobs to hybrid (current behavior)
UPDATE ingestion_jobs
SET chunker_type = 'hybrid'
WHERE chunker_type IS NULL;

-- Create index for performance
CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_chunker_type
    ON ingestion_jobs(chunker_type);

COMMENT ON COLUMN ingestion_jobs.chunker_type IS
'Chunking strategy: hybrid (DoclingHybridChunker - structured docs, respects sections/tables), parent_child (ParentChildChunker - long text/transcripts, search in children return parents)';

-- ============================================
-- Smart chunk matching function
-- Handles both hybrid and parent-child chunks
-- ============================================

CREATE OR REPLACE FUNCTION match_chunks_smart(
    query_embedding vector(1024),
    match_count int DEFAULT 5
)
RETURNS TABLE (
    id uuid,
    content text,
    document_id uuid,
    distance float,
    chunk_level chunk_level_enum,
    metadata jsonb,
    document_title text,
    document_source text,
    similarity float
) AS $$
BEGIN
    -- Strategy: Search in children (parent-child) OR normal chunks (hybrid)
    -- Then return parents for children, or chunks directly

    RETURN QUERY
    WITH child_matches AS (
        -- Search in child chunks (parent-child documents)
        SELECT
            c.id,
            c.parent_chunk_id,
            c.embedding <=> query_embedding AS dist,
            'child'::text AS source_type
        FROM chunks c
        WHERE c.chunk_level = 'child'
          AND c.embedding IS NOT NULL
        ORDER BY dist
        LIMIT match_count * 2
    ),
    normal_matches AS (
        -- Search in normal chunks (hybrid documents)
        SELECT
            c.id,
            NULL::uuid AS parent_chunk_id,
            c.embedding <=> query_embedding AS dist,
            'normal'::text AS source_type
        FROM chunks c
        WHERE c.chunk_level IS NULL
          AND c.embedding IS NOT NULL
        ORDER BY dist
        LIMIT match_count * 2
    ),
    combined AS (
        -- Combine both result sets and sort by distance
        SELECT id, parent_chunk_id, dist, source_type FROM child_matches
        UNION ALL
        SELECT id, parent_chunk_id, dist, source_type FROM normal_matches
        ORDER BY dist
        LIMIT match_count
    )
    -- Retrieve parents for child matches, or chunks directly for normal matches
    SELECT
        COALESCE(p.id, c.id)::uuid AS id,
        COALESCE(p.content, c.content)::text AS content,
        COALESCE(p.document_id, c.document_id)::uuid AS document_id,
        combined.dist::double precision AS distance,
        COALESCE(p.chunk_level, c.chunk_level) AS chunk_level,
        COALESCE(p.metadata, c.metadata)::jsonb AS metadata,
        d.title::text AS document_title,
        d.source::text AS document_source,
        (1 - combined.dist)::double precision AS similarity
    FROM combined
    LEFT JOIN chunks c ON c.id = combined.id
    LEFT JOIN chunks p ON p.id = combined.parent_chunk_id
    LEFT JOIN documents d ON d.id = COALESCE(p.document_id, c.document_id)
    ORDER BY combined.dist;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION match_chunks_smart IS
'Intelligent chunk matching that handles both DoclingHybridChunker (normal chunks) and ParentChildChunker (searches children, returns parents). Automatically detects chunk type and applies correct strategy.';

-- ============================================
-- Verification queries
-- ============================================

-- Verify column added
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'ingestion_jobs'
        AND column_name = 'chunker_type'
    ) THEN
        RAISE NOTICE 'SUCCESS: chunker_type column added to ingestion_jobs';
    ELSE
        RAISE EXCEPTION 'FAILED: chunker_type column not found';
    END IF;
END $$;

-- Verify function created
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_proc
        WHERE proname = 'match_chunks_smart'
    ) THEN
        RAISE NOTICE 'SUCCESS: match_chunks_smart function created';
    ELSE
        RAISE EXCEPTION 'FAILED: match_chunks_smart function not found';
    END IF;
END $$;
