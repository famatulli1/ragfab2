-- PATCH: Correction type bm25_score (real → double precision)
-- Date: 2025-10-31
-- Bug: ts_rank_cd() retourne real, pas double precision
-- Solution: CAST explicite ::double precision

DROP FUNCTION IF EXISTS match_chunks_hybrid CASCADE;

CREATE OR REPLACE FUNCTION match_chunks_hybrid(
    query_embedding vector(1024),
    query_text text,
    match_count int DEFAULT 5,
    alpha float DEFAULT 0.5,
    use_hierarchical boolean DEFAULT false
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
DECLARE
    search_limit int;
BEGIN
    search_limit := match_count * 4;

    RETURN QUERY
    WITH vector_results AS (
        SELECT
            c.id,
            c.content,
            c.metadata,
            c.document_id,
            c.chunk_index,
            c.prev_chunk_id,
            c.next_chunk_id,
            c.section_hierarchy,
            c.heading_context,
            c.document_position,
            c.chunk_level,
            c.parent_chunk_id,
            1 - (c.embedding <=> query_embedding) AS similarity,
            ROW_NUMBER() OVER (ORDER BY c.embedding <=> query_embedding) AS rank
        FROM chunks c
        WHERE
            CASE
                WHEN use_hierarchical THEN c.chunk_level = 'child' OR c.chunk_level IS NULL
                ELSE true
            END
        ORDER BY c.embedding <=> query_embedding
        LIMIT search_limit
    ),

    keyword_results AS (
        SELECT
            c.id,
            c.content,
            c.metadata,
            c.document_id,
            c.chunk_index,
            c.prev_chunk_id,
            c.next_chunk_id,
            c.section_hierarchy,
            c.heading_context,
            c.document_position,
            c.chunk_level,
            c.parent_chunk_id,
            -- CORRECTION: CAST explicite en double precision
            ts_rank_cd(c.content_tsv, to_tsquery('french', query_text), 32)::double precision AS score,
            ROW_NUMBER() OVER (
                ORDER BY ts_rank_cd(c.content_tsv, to_tsquery('french', query_text), 32) DESC
            ) AS rank
        FROM chunks c
        WHERE
            c.content_tsv @@ to_tsquery('french', query_text)
            AND CASE
                WHEN use_hierarchical THEN c.chunk_level = 'child' OR c.chunk_level IS NULL
                ELSE true
            END
        ORDER BY ts_rank_cd(c.content_tsv, to_tsquery('french', query_text), 32) DESC
        LIMIT search_limit
    ),

    fused_results AS (
        SELECT
            COALESCE(v.id, k.id) AS id,
            COALESCE(v.content, k.content) AS content,
            COALESCE(v.similarity, 0.0) AS similarity,
            COALESCE(k.score, 0.0) AS bm25_score,
            (alpha * (1.0 / (60.0 + COALESCE(v.rank, 1000.0)))) +
            ((1.0 - alpha) * (1.0 / (60.0 + COALESCE(k.rank, 1000.0)))) AS combined_score,
            COALESCE(v.metadata, k.metadata) AS metadata,
            COALESCE(v.document_id, k.document_id) AS document_id,
            COALESCE(v.chunk_index, k.chunk_index) AS chunk_index,
            COALESCE(v.prev_chunk_id, k.prev_chunk_id) AS prev_chunk_id,
            COALESCE(v.next_chunk_id, k.next_chunk_id) AS next_chunk_id,
            COALESCE(v.section_hierarchy, k.section_hierarchy) AS section_hierarchy,
            COALESCE(v.heading_context, k.heading_context) AS heading_context,
            COALESCE(v.document_position, k.document_position) AS document_position,
            COALESCE(v.chunk_level, k.chunk_level) AS chunk_level,
            COALESCE(v.parent_chunk_id, k.parent_chunk_id) AS parent_chunk_id
        FROM vector_results v
        FULL OUTER JOIN keyword_results k ON v.id = k.id
        ORDER BY combined_score DESC
        LIMIT match_count
    )

    SELECT * FROM fused_results;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION match_chunks_hybrid IS 'Hybrid search (v4 - CAST bm25_score fix)';
