-- Fix match_chunks function signature
-- Problem: Function has only 3 parameters but code expects 4
-- Solution: Drop old function and recreate with use_hierarchical parameter

-- Step 1: Drop old version
DROP FUNCTION IF EXISTS match_chunks(vector, integer, double precision);

-- Step 2: Create new version with 4 parameters
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
            COALESCE(p.content, cm.content) AS content,
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

-- Step 3: Display confirmation
SELECT 'Function match_chunks updated successfully!' as status;
SELECT
    proname as function_name,
    pg_get_function_arguments(oid) as arguments
FROM pg_proc
WHERE proname = 'match_chunks' AND pronamespace = 'public'::regnamespace;
