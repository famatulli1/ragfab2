-- Migration 06: Parent-Child Chunking Architecture
-- Purpose: Enable hierarchical chunking with large context parents and precise child chunks
-- Date: 2025-01-24
-- Author: RAGFab Optimization Team

-- ============================================================================
-- SECTION 1: Create Chunk Level Enum
-- ============================================================================

-- Create enum for chunk levels if not exists
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'chunk_level_enum') THEN
        CREATE TYPE chunk_level_enum AS ENUM ('parent', 'child');
    END IF;
END $$;

-- ============================================================================
-- SECTION 2: Add Columns to Chunks Table
-- ============================================================================

-- Add chunk_level column (default: parent for backward compatibility)
-- Parent chunks: Large context chunks (1500-4000 tokens)
-- Child chunks: Precise retrieval chunks (400-800 tokens)
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS chunk_level chunk_level_enum DEFAULT 'parent';

-- Add parent_chunk_id reference (NULL for parent chunks, UUID for child chunks)
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS parent_chunk_id UUID;

-- Add foreign key constraint
ALTER TABLE chunks DROP CONSTRAINT IF EXISTS fk_chunks_parent_chunk;
ALTER TABLE chunks ADD CONSTRAINT fk_chunks_parent_chunk
    FOREIGN KEY (parent_chunk_id) REFERENCES chunks(id) ON DELETE CASCADE;

-- ============================================================================
-- SECTION 3: Create Indexes for Efficient Hierarchical Queries
-- ============================================================================

-- Index for finding all children of a parent chunk
CREATE INDEX IF NOT EXISTS idx_chunks_parent_chunk_id
    ON chunks(parent_chunk_id)
    WHERE parent_chunk_id IS NOT NULL;

-- Index for finding parent chunks only
CREATE INDEX IF NOT EXISTS idx_chunks_parent_level
    ON chunks(document_id, chunk_level)
    WHERE chunk_level = 'parent';

-- Index for finding child chunks only
CREATE INDEX IF NOT EXISTS idx_chunks_child_level
    ON chunks(document_id, chunk_level)
    WHERE chunk_level = 'child';

-- Composite index for parent-child relationships
CREATE INDEX IF NOT EXISTS idx_chunks_level_parent_id
    ON chunks(chunk_level, parent_chunk_id);

-- ============================================================================
-- SECTION 4: Helper Functions for Parent-Child Operations
-- ============================================================================

-- Function to get all children of a parent chunk
CREATE OR REPLACE FUNCTION get_child_chunks(parent_chunk_id_param UUID)
RETURNS TABLE (
    chunk_id UUID,
    content TEXT,
    chunk_index INTEGER,
    embedding vector(1024),
    metadata JSONB
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id AS chunk_id,
        c.content,
        c.chunk_index,
        c.embedding,
        c.metadata
    FROM chunks c
    WHERE c.parent_chunk_id = parent_chunk_id_param
    AND c.chunk_level = 'child'
    ORDER BY c.chunk_index;
END;
$$;

-- Function to get parent chunk for a child chunk
CREATE OR REPLACE FUNCTION get_parent_chunk(child_chunk_id_param UUID)
RETURNS TABLE (
    chunk_id UUID,
    content TEXT,
    chunk_index INTEGER,
    metadata JSONB
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        p.id AS chunk_id,
        p.content,
        p.chunk_index,
        p.metadata
    FROM chunks c
    JOIN chunks p ON c.parent_chunk_id = p.id
    WHERE c.id = child_chunk_id_param
    AND c.chunk_level = 'child'
    AND p.chunk_level = 'parent';
END;
$$;

-- Function for hierarchical search (search children, return parents)
CREATE OR REPLACE FUNCTION hierarchical_match_chunks(
    query_embedding vector(1024),
    match_count INT DEFAULT 5,
    similarity_threshold FLOAT DEFAULT 0.0
)
RETURNS TABLE (
    parent_chunk_id UUID,
    parent_content TEXT,
    child_chunk_id UUID,
    child_content TEXT,
    similarity FLOAT,
    document_id UUID,
    document_title TEXT,
    document_source TEXT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    WITH child_matches AS (
        -- Search in child chunks for precision
        SELECT
            c.id AS child_id,
            c.content AS child_text,
            c.parent_chunk_id,
            1 - (c.embedding <=> query_embedding) AS sim,
            c.document_id AS doc_id
        FROM chunks c
        WHERE c.chunk_level = 'child'
        AND c.embedding IS NOT NULL
        AND (1 - (c.embedding <=> query_embedding)) >= similarity_threshold
        ORDER BY c.embedding <=> query_embedding
        LIMIT match_count
    )
    SELECT
        p.id AS parent_chunk_id,
        p.content AS parent_content,
        cm.child_id AS child_chunk_id,
        cm.child_text AS child_content,
        cm.sim AS similarity,
        d.id AS document_id,
        d.title AS document_title,
        d.source AS document_source
    FROM child_matches cm
    JOIN chunks p ON cm.parent_chunk_id = p.id
    JOIN documents d ON cm.doc_id = d.id
    WHERE p.chunk_level = 'parent'
    ORDER BY cm.sim DESC;
END;
$$;

-- ============================================================================
-- SECTION 5: Update match_chunks Function for Parent-Child Awareness
-- ============================================================================

-- Replace existing match_chunks function with parent-child aware version
CREATE OR REPLACE FUNCTION match_chunks(
    query_embedding vector(1024),
    match_count INT DEFAULT 10,
    similarity_threshold FLOAT DEFAULT 0.0,
    use_hierarchical BOOLEAN DEFAULT FALSE
)
RETURNS TABLE (
    id UUID,
    document_id UUID,
    content TEXT,
    similarity FLOAT,
    metadata JSONB,
    document_title TEXT,
    document_source TEXT,
    chunk_level chunk_level_enum,
    parent_chunk_id UUID
)
LANGUAGE plpgsql
AS $$
BEGIN
    IF use_hierarchical THEN
        -- Hierarchical mode: search children, return enriched with parent context
        RETURN QUERY
        WITH child_matches AS (
            SELECT
                c.id,
                c.document_id,
                c.content,
                1 - (c.embedding <=> query_embedding) AS sim,
                c.metadata,
                c.chunk_level,
                c.parent_chunk_id
            FROM chunks c
            WHERE c.chunk_level = 'child'
            AND c.embedding IS NOT NULL
            AND (1 - (c.embedding <=> query_embedding)) >= similarity_threshold
            ORDER BY c.embedding <=> query_embedding
            LIMIT match_count
        )
        SELECT
            cm.id,
            cm.document_id,
            COALESCE(p.content, cm.content) AS content,  -- Use parent content if available
            cm.sim AS similarity,
            cm.metadata,
            d.title AS document_title,
            d.source AS document_source,
            cm.chunk_level,
            cm.parent_chunk_id
        FROM child_matches cm
        LEFT JOIN chunks p ON cm.parent_chunk_id = p.id
        JOIN documents d ON cm.document_id = d.id
        ORDER BY cm.sim DESC;
    ELSE
        -- Standard mode: search all chunks (parent or child)
        RETURN QUERY
        SELECT
            c.id,
            c.document_id,
            c.content,
            1 - (c.embedding <=> query_embedding) AS similarity,
            c.metadata,
            d.title AS document_title,
            d.source AS document_source,
            c.chunk_level,
            c.parent_chunk_id
        FROM chunks c
        JOIN documents d ON c.document_id = d.id
        WHERE c.embedding IS NOT NULL
        AND (1 - (c.embedding <=> query_embedding)) >= similarity_threshold
        ORDER BY c.embedding <=> query_embedding
        LIMIT match_count;
    END IF;
END;
$$;

-- ============================================================================
-- SECTION 6: Comments and Documentation
-- ============================================================================

COMMENT ON COLUMN chunks.chunk_level IS 'Niveau du chunk: parent (large contexte) ou child (précision fine)';
COMMENT ON COLUMN chunks.parent_chunk_id IS 'ID du chunk parent (NULL pour les parents, UUID pour les enfants)';

COMMENT ON FUNCTION get_child_chunks IS 'Récupère tous les chunks enfants d''un chunk parent';
COMMENT ON FUNCTION get_parent_chunk IS 'Récupère le chunk parent d''un chunk enfant';
COMMENT ON FUNCTION hierarchical_match_chunks IS 'Recherche hiérarchique: cherche dans les enfants, retourne les parents';

-- ============================================================================
-- SECTION 7: Validation
-- ============================================================================

-- Verify migration success
DO $$
DECLARE
    column_count INTEGER;
BEGIN
    -- Count new columns
    SELECT COUNT(*) INTO column_count
    FROM information_schema.columns
    WHERE table_name = 'chunks'
    AND column_name IN ('chunk_level', 'parent_chunk_id');

    IF column_count = 2 THEN
        RAISE NOTICE '✅ Migration 06 completed successfully: Parent-Child architecture enabled';
    ELSE
        RAISE WARNING '⚠️ Migration 06 incomplete: only % columns added (expected 2)', column_count;
    END IF;
END $$;

-- Display statistics
DO $$
DECLARE
    parent_count INTEGER;
    child_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO parent_count FROM chunks WHERE chunk_level = 'parent';
    SELECT COUNT(*) INTO child_count FROM chunks WHERE chunk_level = 'child';

    RAISE NOTICE '📊 Current chunk statistics:';
    RAISE NOTICE '   - Parent chunks: %', parent_count;
    RAISE NOTICE '   - Child chunks: %', child_count;
END $$;
