-- =====================================================
-- RAGFab - Apply All Migrations (Combined SQL)
-- =====================================================
-- Usage: cat apply_all_migrations.sql | docker exec -i <container> psql -U raguser -d ragdb
-- Date: 2025-10-24

-- =====================================================
-- Migration 00: Initialize migration tracking table
-- =====================================================

CREATE TABLE IF NOT EXISTS schema_migrations (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL UNIQUE,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    success BOOLEAN NOT NULL,
    execution_time_ms INTEGER,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_schema_migrations_filename ON schema_migrations(filename);
CREATE INDEX IF NOT EXISTS idx_schema_migrations_applied_at ON schema_migrations(applied_at DESC);

-- Record this migration
INSERT INTO schema_migrations (filename, success, execution_time_ms, error_message)
VALUES ('00_init_migrations.sql', true, 0, NULL)
ON CONFLICT (filename) DO NOTHING;

-- =====================================================
-- Migration 05: Enriched Metadata (Adjacent Chunks)
-- =====================================================

-- Add prev_chunk_id and next_chunk_id columns
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS prev_chunk_id UUID REFERENCES chunks(id) ON DELETE SET NULL;
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS next_chunk_id UUID REFERENCES chunks(id) ON DELETE SET NULL;

-- Create indexes for efficient traversal
CREATE INDEX IF NOT EXISTS idx_chunks_prev_chunk_id ON chunks(prev_chunk_id);
CREATE INDEX IF NOT EXISTS idx_chunks_next_chunk_id ON chunks(next_chunk_id);

-- Add comments for documentation
COMMENT ON COLUMN chunks.prev_chunk_id IS 'Reference to the previous chunk in document sequence (for contextual retrieval)';
COMMENT ON COLUMN chunks.next_chunk_id IS 'Reference to the next chunk in document sequence (for contextual retrieval)';

-- Record this migration
INSERT INTO schema_migrations (filename, success, execution_time_ms, error_message)
VALUES ('05_enriched_metadata.sql', true, 0, NULL)
ON CONFLICT (filename) DO NOTHING;

-- =====================================================
-- Migration 06: Parent-Child Chunks (Hierarchical)
-- =====================================================

-- Add parent_chunk_id column for hierarchical chunking
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS parent_chunk_id UUID REFERENCES chunks(id) ON DELETE CASCADE;

-- Add child_chunks JSONB array for storing child chunk references
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS child_chunks JSONB DEFAULT '[]'::jsonb;

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_chunks_parent_chunk_id ON chunks(parent_chunk_id);
CREATE INDEX IF NOT EXISTS idx_chunks_child_chunks ON chunks USING gin(child_chunks);

-- Add comments
COMMENT ON COLUMN chunks.parent_chunk_id IS 'Reference to parent chunk (for hierarchical chunking strategy)';
COMMENT ON COLUMN chunks.child_chunks IS 'Array of child chunk IDs (for hierarchical chunking strategy)';

-- Record this migration
INSERT INTO schema_migrations (filename, success, execution_time_ms, error_message)
VALUES ('06_parent_child_chunks.sql', true, 0, NULL)
ON CONFLICT (filename) DO NOTHING;

-- =====================================================
-- Verification
-- =====================================================

-- Show applied migrations
SELECT filename, applied_at, success FROM schema_migrations ORDER BY applied_at DESC;

-- Show chunks table structure
\d chunks
