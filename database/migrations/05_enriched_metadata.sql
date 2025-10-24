-- Migration 05: Enriched Chunk Metadata for Contextual RAG
-- Purpose: Add structural metadata to chunks table for better context preservation
-- Date: 2025-01-24
-- Author: RAGFab Optimization Team

-- ============================================================================
-- SECTION 1: Add New Columns to Chunks Table
-- ============================================================================

-- Add previous/next chunk references for sequential context
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS prev_chunk_id UUID;
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS next_chunk_id UUID;

-- Add foreign key constraints (nullable - first/last chunks won't have prev/next)
ALTER TABLE chunks DROP CONSTRAINT IF EXISTS fk_chunks_prev_chunk;
ALTER TABLE chunks DROP CONSTRAINT IF EXISTS fk_chunks_next_chunk;

ALTER TABLE chunks ADD CONSTRAINT fk_chunks_prev_chunk
    FOREIGN KEY (prev_chunk_id) REFERENCES chunks(id) ON DELETE SET NULL;

ALTER TABLE chunks ADD CONSTRAINT fk_chunks_next_chunk
    FOREIGN KEY (next_chunk_id) REFERENCES chunks(id) ON DELETE SET NULL;

-- Add section hierarchy (array of heading names from root to current section)
-- Example: ["Guide Utilisateur", "Configuration", "Paramètres Bluetooth"]
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS section_hierarchy JSONB DEFAULT '[]';

-- Add heading context (immediate heading/title for this chunk)
-- Example: "## Configuration Bluetooth"
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS heading_context TEXT;

-- Add document position (normalized 0.0-1.0 position in document)
-- Useful for understanding chunk location in original document
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS document_position FLOAT;

-- ============================================================================
-- SECTION 2: Create Indexes for Efficient Retrieval
-- ============================================================================

-- Index for adjacent chunk retrieval (critical for contextual search)
CREATE INDEX IF NOT EXISTS idx_chunks_prev_next
    ON chunks(prev_chunk_id, next_chunk_id)
    WHERE prev_chunk_id IS NOT NULL OR next_chunk_id IS NOT NULL;

-- Index for section hierarchy queries (GIN index for JSONB)
CREATE INDEX IF NOT EXISTS idx_chunks_section_hierarchy
    ON chunks USING GIN (section_hierarchy);

-- Index for document position ordering
CREATE INDEX IF NOT EXISTS idx_chunks_document_position
    ON chunks(document_id, document_position);

-- ============================================================================
-- SECTION 3: Helper Functions
-- ============================================================================

-- Function to get chunk with adjacent context (prev + current + next)
CREATE OR REPLACE FUNCTION get_chunk_with_context(chunk_id_param UUID)
RETURNS TABLE (
    chunk_id UUID,
    content TEXT,
    prev_content TEXT,
    next_content TEXT,
    section_path TEXT,
    position_in_doc FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id AS chunk_id,
        c.content,
        prev_c.content AS prev_content,
        next_c.content AS next_content,
        array_to_string(
            ARRAY(SELECT jsonb_array_elements_text(c.section_hierarchy)),
            ' > '
        ) AS section_path,
        c.document_position AS position_in_doc
    FROM chunks c
    LEFT JOIN chunks prev_c ON c.prev_chunk_id = prev_c.id
    LEFT JOIN chunks next_c ON c.next_chunk_id = next_c.id
    WHERE c.id = chunk_id_param;
END;
$$;

-- Function to get all chunks in same section
CREATE OR REPLACE FUNCTION get_chunks_in_section(
    section_hierarchy_param JSONB,
    document_id_param UUID
)
RETURNS TABLE (
    chunk_id UUID,
    content TEXT,
    chunk_index INTEGER,
    document_position FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id AS chunk_id,
        c.content,
        c.chunk_index,
        c.document_position
    FROM chunks c
    WHERE c.document_id = document_id_param
    AND c.section_hierarchy = section_hierarchy_param
    ORDER BY c.document_position;
END;
$$;

-- ============================================================================
-- SECTION 4: Comments and Documentation
-- ============================================================================

COMMENT ON COLUMN chunks.prev_chunk_id IS 'ID du chunk précédent dans le document (NULL si premier chunk)';
COMMENT ON COLUMN chunks.next_chunk_id IS 'ID du chunk suivant dans le document (NULL si dernier chunk)';
COMMENT ON COLUMN chunks.section_hierarchy IS 'Hiérarchie de sections depuis la racine (ex: ["Guide", "Config", "Bluetooth"])';
COMMENT ON COLUMN chunks.heading_context IS 'Titre/heading immédiat du chunk (ex: "## Configuration Bluetooth")';
COMMENT ON COLUMN chunks.document_position IS 'Position normalisée dans le document (0.0 = début, 1.0 = fin)';

COMMENT ON FUNCTION get_chunk_with_context IS 'Récupère un chunk avec son contexte adjacent (prev + current + next)';
COMMENT ON FUNCTION get_chunks_in_section IS 'Récupère tous les chunks dans la même section hiérarchique';

-- ============================================================================
-- SECTION 5: Validation
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
    AND column_name IN ('prev_chunk_id', 'next_chunk_id', 'section_hierarchy', 'heading_context', 'document_position');

    IF column_count = 5 THEN
        RAISE NOTICE '✅ Migration 05 completed successfully: 5 new columns added to chunks table';
    ELSE
        RAISE WARNING '⚠️ Migration 05 incomplete: only % columns added (expected 5)', column_count;
    END IF;
END $$;
