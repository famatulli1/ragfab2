-- Migration 11: Add bounding box column for chunk highlighting in PDFs
-- Purpose: Store bbox coordinates from Docling for highlighting chunks in original PDFs
-- Date: 2025-02-02
-- Author: RAGFab PDF Highlighting Team

-- ============================================================================
-- SECTION 1: Add bbox column to chunks table
-- ============================================================================

-- Add bbox column (Docling format: bottom-left origin)
-- Format: {l: left, t: top, r: right, b: bottom}
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS bbox JSONB;

-- ============================================================================
-- SECTION 2: Create indexes for efficient retrieval
-- ============================================================================

-- Index for querying chunks by document and page (for PDF annotation)
CREATE INDEX IF NOT EXISTS idx_chunks_bbox_page
    ON chunks(document_id, ((metadata->>'page_number')::integer))
    WHERE bbox IS NOT NULL;

-- GIN index for JSONB bbox queries (if needed for complex queries)
CREATE INDEX IF NOT EXISTS idx_chunks_bbox_gin
    ON chunks USING GIN (bbox)
    WHERE bbox IS NOT NULL;

-- ============================================================================
-- SECTION 3: Helper function for PDF annotation
-- ============================================================================

-- Function to get all chunks with bbox for a specific document and page
CREATE OR REPLACE FUNCTION get_chunks_with_bbox_for_page(
    document_id_param UUID,
    page_number_param INTEGER
)
RETURNS TABLE (
    chunk_id UUID,
    content TEXT,
    bbox JSONB,
    chunk_index INTEGER
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id AS chunk_id,
        c.content,
        c.bbox,
        c.chunk_index
    FROM chunks c
    WHERE c.document_id = document_id_param
    AND (c.metadata->>'page_number')::integer = page_number_param
    AND c.bbox IS NOT NULL
    ORDER BY c.chunk_index;
END;
$$;

-- Function to get chunks with bbox for annotation (used by API)
CREATE OR REPLACE FUNCTION get_chunks_for_annotation(
    document_id_param UUID,
    chunk_ids_param UUID[] DEFAULT NULL
)
RETURNS TABLE (
    chunk_id UUID,
    page_number INTEGER,
    bbox JSONB,
    content TEXT
)
LANGUAGE plpgsql
AS $$
BEGIN
    IF chunk_ids_param IS NOT NULL THEN
        -- Filter by specific chunk IDs
        RETURN QUERY
        SELECT
            c.id AS chunk_id,
            (c.metadata->>'page_number')::integer AS page_number,
            c.bbox,
            c.content
        FROM chunks c
        WHERE c.document_id = document_id_param
        AND c.id = ANY(chunk_ids_param)
        AND c.bbox IS NOT NULL
        ORDER BY (c.metadata->>'page_number')::integer, c.chunk_index;
    ELSE
        -- Return all chunks with bbox for this document
        RETURN QUERY
        SELECT
            c.id AS chunk_id,
            (c.metadata->>'page_number')::integer AS page_number,
            c.bbox,
            c.content
        FROM chunks c
        WHERE c.document_id = document_id_param
        AND c.bbox IS NOT NULL
        ORDER BY (c.metadata->>'page_number')::integer, c.chunk_index;
    END IF;
END;
$$;

-- ============================================================================
-- SECTION 4: Comments and documentation
-- ============================================================================

COMMENT ON COLUMN chunks.bbox IS 'Bounding box coordinates from Docling (bottom-left origin): {l, t, r, b}';
COMMENT ON FUNCTION get_chunks_with_bbox_for_page IS 'Récupère tous les chunks avec bbox pour une page donnée';
COMMENT ON FUNCTION get_chunks_for_annotation IS 'Récupère les chunks avec bbox pour annotation PDF (tous ou filtrés par IDs)';

-- ============================================================================
-- SECTION 5: Validation
-- ============================================================================

-- Verify migration success
DO $$
DECLARE
    column_exists BOOLEAN;
    function_count INTEGER;
BEGIN
    -- Check if bbox column was added
    SELECT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'chunks'
        AND column_name = 'bbox'
    ) INTO column_exists;

    -- Count helper functions
    SELECT COUNT(*) INTO function_count
    FROM pg_proc p
    JOIN pg_namespace n ON p.pronamespace = n.oid
    WHERE n.nspname = 'public'
    AND p.proname IN ('get_chunks_with_bbox_for_page', 'get_chunks_for_annotation');

    IF column_exists AND function_count = 2 THEN
        RAISE NOTICE '✅ Migration 11 completed successfully: bbox column and helper functions added';
    ELSE
        RAISE WARNING '⚠️ Migration 11 incomplete: column_exists=%, functions=%', column_exists, function_count;
    END IF;
END $$;
