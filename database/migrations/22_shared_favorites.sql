-- Migration: 22_shared_favorites.sql
-- Description: Shared Favorites system - users propose Q&A solutions, admins validate, all users can search
-- Date: 2025-12-01

-- ============================================================================
-- TABLE: shared_favorites
-- ============================================================================

CREATE TABLE IF NOT EXISTS shared_favorites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Snapshot original (immutable after creation)
    original_question TEXT NOT NULL,
    original_response TEXT NOT NULL,
    original_sources JSONB DEFAULT '[]',
    source_conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,

    -- Contenu enrichi par admin (editable)
    published_title VARCHAR(500),
    published_question TEXT,
    published_response TEXT,

    -- Recherche semantique (1024 dims - same as chunks)
    question_embedding vector(1024),

    -- Workflow status
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'published', 'rejected')),
    proposed_by UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    validated_by UUID REFERENCES users(id) ON DELETE SET NULL,
    rejection_reason TEXT,
    admin_notes TEXT,

    -- Universe filtering (follows existing pattern)
    universe_id UUID REFERENCES product_universes(id) ON DELETE SET NULL,

    -- Metrics
    view_count INTEGER DEFAULT 0,
    copy_count INTEGER DEFAULT 0,

    -- Timestamps + simple versioning
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    validated_at TIMESTAMP WITH TIME ZONE,
    last_edited_at TIMESTAMP WITH TIME ZONE,
    last_edited_by UUID REFERENCES users(id) ON DELETE SET NULL
);

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Vector search index (HNSW for better performance)
CREATE INDEX IF NOT EXISTS idx_favorites_embedding
ON shared_favorites USING hnsw (question_embedding vector_cosine_ops);

-- Status filtering
CREATE INDEX IF NOT EXISTS idx_favorites_status ON shared_favorites(status);

-- Universe filtering
CREATE INDEX IF NOT EXISTS idx_favorites_universe ON shared_favorites(universe_id)
    WHERE universe_id IS NOT NULL;

-- Admin pending queue (recent first)
CREATE INDEX IF NOT EXISTS idx_favorites_pending ON shared_favorites(created_at DESC)
    WHERE status = 'pending';

-- Published favorites (recent first for listing)
CREATE INDEX IF NOT EXISTS idx_favorites_published ON shared_favorites(validated_at DESC)
    WHERE status = 'published';

-- Popular favorites
CREATE INDEX IF NOT EXISTS idx_favorites_popular ON shared_favorites(view_count DESC)
    WHERE status = 'published';

-- User's proposed favorites
CREATE INDEX IF NOT EXISTS idx_favorites_proposed_by ON shared_favorites(proposed_by);

-- ============================================================================
-- FULL-TEXT SEARCH (French)
-- ============================================================================

ALTER TABLE shared_favorites ADD COLUMN IF NOT EXISTS question_tsv tsvector;

CREATE INDEX IF NOT EXISTS idx_favorites_tsv ON shared_favorites USING gin(question_tsv);

-- Trigger to auto-update tsvector
CREATE OR REPLACE FUNCTION favorites_tsvector_trigger()
RETURNS TRIGGER AS $$
BEGIN
    NEW.question_tsv := to_tsvector('french',
        COALESCE(NEW.published_question, NEW.original_question, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tsvector_favorites ON shared_favorites;
CREATE TRIGGER tsvector_favorites
    BEFORE INSERT OR UPDATE OF published_question, original_question ON shared_favorites
    FOR EACH ROW EXECUTE FUNCTION favorites_tsvector_trigger();

-- ============================================================================
-- SEMANTIC SEARCH FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION match_favorites(
    query_embedding vector(1024),
    match_count INT DEFAULT 5,
    similarity_threshold FLOAT DEFAULT 0.85,
    filter_universe_ids UUID[] DEFAULT NULL
) RETURNS TABLE (
    id UUID,
    title VARCHAR(500),
    question TEXT,
    response TEXT,
    sources JSONB,
    similarity FLOAT,
    universe_id UUID,
    view_count INTEGER,
    copy_count INTEGER
) LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT
        sf.id,
        COALESCE(sf.published_title, LEFT(sf.original_question, 100))::VARCHAR(500) as title,
        COALESCE(sf.published_question, sf.original_question) as question,
        COALESCE(sf.published_response, sf.original_response) as response,
        sf.original_sources as sources,
        (1 - (sf.question_embedding <=> query_embedding))::FLOAT AS similarity,
        sf.universe_id,
        sf.view_count,
        sf.copy_count
    FROM shared_favorites sf
    WHERE sf.status = 'published'
        AND sf.question_embedding IS NOT NULL
        AND (filter_universe_ids IS NULL OR sf.universe_id = ANY(filter_universe_ids))
        AND (1 - (sf.question_embedding <=> query_embedding)) >= similarity_threshold
    ORDER BY sf.question_embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- ============================================================================
-- HELPER FUNCTION: Get favorite with universe info
-- ============================================================================

CREATE OR REPLACE FUNCTION get_favorite_with_universe(favorite_id UUID)
RETURNS TABLE (
    id UUID,
    original_question TEXT,
    original_response TEXT,
    original_sources JSONB,
    source_conversation_id UUID,
    published_title VARCHAR(500),
    published_question TEXT,
    published_response TEXT,
    status VARCHAR(20),
    proposed_by UUID,
    proposed_by_username VARCHAR(255),
    validated_by UUID,
    rejection_reason TEXT,
    admin_notes TEXT,
    universe_id UUID,
    universe_name VARCHAR(255),
    universe_slug VARCHAR(100),
    universe_color VARCHAR(7),
    view_count INTEGER,
    copy_count INTEGER,
    created_at TIMESTAMP WITH TIME ZONE,
    validated_at TIMESTAMP WITH TIME ZONE,
    last_edited_at TIMESTAMP WITH TIME ZONE
) LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT
        sf.id,
        sf.original_question,
        sf.original_response,
        sf.original_sources,
        sf.source_conversation_id,
        sf.published_title,
        sf.published_question,
        sf.published_response,
        sf.status,
        sf.proposed_by,
        u.username as proposed_by_username,
        sf.validated_by,
        sf.rejection_reason,
        sf.admin_notes,
        sf.universe_id,
        pu.name as universe_name,
        pu.slug as universe_slug,
        pu.color as universe_color,
        sf.view_count,
        sf.copy_count,
        sf.created_at,
        sf.validated_at,
        sf.last_edited_at
    FROM shared_favorites sf
    LEFT JOIN users u ON sf.proposed_by = u.id
    LEFT JOIN product_universes pu ON sf.universe_id = pu.id
    WHERE sf.id = favorite_id;
END;
$$;

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE shared_favorites IS 'Shared Q&A solutions proposed by users and validated by admins';
COMMENT ON COLUMN shared_favorites.original_question IS 'Original question from conversation (immutable snapshot)';
COMMENT ON COLUMN shared_favorites.original_response IS 'Original AI response from conversation (immutable snapshot)';
COMMENT ON COLUMN shared_favorites.original_sources IS 'RAG sources array from the original message';
COMMENT ON COLUMN shared_favorites.published_title IS 'Admin-edited title for display';
COMMENT ON COLUMN shared_favorites.published_question IS 'Admin-edited question (if different from original)';
COMMENT ON COLUMN shared_favorites.published_response IS 'Admin-edited response (if different from original)';
COMMENT ON COLUMN shared_favorites.question_embedding IS '1024-dim embedding of original_question for semantic search';
COMMENT ON COLUMN shared_favorites.status IS 'pending=awaiting validation, published=visible to all, rejected=not approved';
COMMENT ON FUNCTION match_favorites IS 'Semantic search for similar favorites with 0.85 default threshold';
