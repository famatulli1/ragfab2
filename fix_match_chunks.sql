-- Fix pour l'erreur "column reference 'id' is ambiguous"
-- Solution: Renommer les colonnes intermédiaires dans les CTEs pour éviter les conflits

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
    RETURN QUERY
    WITH child_matches AS (
        SELECT
            c.id AS cid,
            c.parent_chunk_id AS pid,
            c.embedding <=> query_embedding AS dist,
            'child'::text AS source_type
        FROM chunks c
        WHERE c.chunk_level = 'child'
          AND c.embedding IS NOT NULL
        ORDER BY dist
        LIMIT match_count * 2
    ),
    normal_matches AS (
        SELECT
            c.id AS cid,
            NULL::uuid AS pid,
            c.embedding <=> query_embedding AS dist,
            'normal'::text AS source_type
        FROM chunks c
        WHERE c.chunk_level IS NULL
          AND c.embedding IS NOT NULL
        ORDER BY dist
        LIMIT match_count * 2
    ),
    combined AS (
        SELECT cid, pid, dist, source_type FROM child_matches
        UNION ALL
        SELECT cid, pid, dist, source_type FROM normal_matches
        ORDER BY dist
        LIMIT match_count
    )
    SELECT
        COALESCE(p.id, c.id),
        COALESCE(p.content, c.content),
        COALESCE(p.document_id, c.document_id),
        combined.dist,
        COALESCE(p.chunk_level, c.chunk_level),
        COALESCE(p.metadata, c.metadata),
        d.title,
        d.source,
        (1 - combined.dist)
    FROM combined
    LEFT JOIN chunks c ON c.id = combined.cid
    LEFT JOIN chunks p ON p.id = combined.pid
    LEFT JOIN documents d ON d.id = COALESCE(p.document_id, c.document_id)
    ORDER BY combined.dist;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION match_chunks_smart IS
'Intelligent chunk matching that handles both DoclingHybridChunker (normal chunks) and ParentChildChunker (searches children, returns parents). Automatically detects chunk type and applies correct strategy. FIX: Renamed intermediate columns to avoid ambiguous column errors.';
