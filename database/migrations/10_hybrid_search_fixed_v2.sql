-- HOTFIX: Correction ambiguïté chunk_level dans match_chunks_smart_hybrid
-- Date: 2025-10-31
-- Description: Qualification explicite des colonnes pour éviter ambiguïté PL/pgSQL

CREATE OR REPLACE FUNCTION match_chunks_smart_hybrid(
    query_embedding vector(1024),
    query_text text,
    match_count int DEFAULT 5,
    alpha float DEFAULT 0.5
)
RETURNS TABLE (
    id uuid,
    content text,
    similarity float,
    bm25_score float,
    combined_score float,
    metadata jsonb,
    document_id uuid,
    chunk_index integer,
    prev_chunk_id uuid,
    next_chunk_id uuid,
    section_hierarchy jsonb,
    heading_context text,
    document_position float,
    chunk_level chunk_level_enum,
    parent_chunk_id uuid
) AS $$
BEGIN
    -- Check if parent-child chunks exist (qualification explicite)
    IF EXISTS (SELECT 1 FROM chunks c WHERE c.chunk_level = 'child' LIMIT 1) THEN
        -- Use hierarchical search (search children, return parents)
        RETURN QUERY
        WITH child_results AS (
            SELECT * FROM match_chunks_hybrid(
                query_embedding,
                query_text,
                match_count * 2,  -- Get more children
                alpha,
                true  -- use_hierarchical = true
            )
        )
        SELECT DISTINCT ON (COALESCE(p.id, cr.id))
            COALESCE(p.id, cr.id) AS id,
            COALESCE(p.content, cr.content) AS content,
            cr.similarity,
            cr.bm25_score,
            cr.combined_score,
            COALESCE(p.metadata, cr.metadata) AS metadata,
            COALESCE(p.document_id, cr.document_id) AS document_id,
            COALESCE(p.chunk_index, cr.chunk_index) AS chunk_index,
            COALESCE(p.prev_chunk_id, cr.prev_chunk_id) AS prev_chunk_id,
            COALESCE(p.next_chunk_id, cr.next_chunk_id) AS next_chunk_id,
            COALESCE(p.section_hierarchy, cr.section_hierarchy) AS section_hierarchy,
            COALESCE(p.heading_context, cr.heading_context) AS heading_context,
            COALESCE(p.document_position, cr.document_position) AS document_position,
            COALESCE(p.chunk_level, cr.chunk_level) AS chunk_level,
            COALESCE(p.parent_chunk_id, cr.parent_chunk_id) AS parent_chunk_id
        FROM child_results cr
        LEFT JOIN chunks p ON cr.parent_chunk_id = p.id
        ORDER BY COALESCE(p.id, cr.id), cr.combined_score DESC
        LIMIT match_count;
    ELSE
        -- No parent-child, use direct hybrid search
        RETURN QUERY
        SELECT * FROM match_chunks_hybrid(
            query_embedding,
            query_text,
            match_count,
            alpha,
            false  -- use_hierarchical = false
        );
    END IF;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION match_chunks_smart_hybrid IS 'Smart hybrid search that automatically handles both hybrid (BM25+vector) and parent-child chunks (v2 - ambiguity fix)';
