-- =====================================================
-- Fix Missing Parts from Migration 06
-- =====================================================
-- Purpose: Add chunk_level enum and column that were not applied manually
-- Date: 2025-10-24

-- Create enum for chunk levels
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'chunk_level_enum') THEN
        CREATE TYPE chunk_level_enum AS ENUM ('parent', 'child');
        RAISE NOTICE '✅ Created chunk_level_enum type';
    ELSE
        RAISE NOTICE 'ℹ️  chunk_level_enum already exists';
    END IF;
END $$;

-- Add chunk_level column (default: parent for backward compatibility)
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS chunk_level chunk_level_enum DEFAULT 'parent';

-- Create missing indexes
CREATE INDEX IF NOT EXISTS idx_chunks_parent_level
    ON chunks(document_id, chunk_level)
    WHERE chunk_level = 'parent';

CREATE INDEX IF NOT EXISTS idx_chunks_child_level
    ON chunks(document_id, chunk_level)
    WHERE chunk_level = 'child';

CREATE INDEX IF NOT EXISTS idx_chunks_level_parent_id
    ON chunks(chunk_level, parent_chunk_id);

-- Verify the fix
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'chunks'
AND column_name IN ('chunk_level', 'parent_chunk_id', 'child_chunks')
ORDER BY column_name;

-- Show success message
DO $$
BEGIN
    RAISE NOTICE '✅ Migration 06 completed!';
    RAISE NOTICE 'Added: chunk_level_enum, chunk_level column, 3 indexes';
END $$;
