-- =====================================================
-- Fix Missing Columns from Migration 05
-- =====================================================
-- Purpose: Add the 3 missing columns that were not applied manually
-- Date: 2025-10-24

-- Add section_hierarchy column (CRITICAL - fixes ingestion error)
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS section_hierarchy JSONB DEFAULT '[]';

-- Add heading_context column
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS heading_context TEXT;

-- Add document_position column
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS document_position FLOAT;

-- Create missing indexes
CREATE INDEX IF NOT EXISTS idx_chunks_section_hierarchy ON chunks USING GIN (section_hierarchy);
CREATE INDEX IF NOT EXISTS idx_chunks_document_position ON chunks(document_id, document_position);

-- Verify the fix
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'chunks'
AND column_name IN ('section_hierarchy', 'heading_context', 'document_position', 'prev_chunk_id', 'next_chunk_id', 'parent_chunk_id', 'child_chunks')
ORDER BY column_name;

-- Show success message
DO $$
BEGIN
    RAISE NOTICE '✅ Missing columns added successfully!';
    RAISE NOTICE 'Columns: section_hierarchy, heading_context, document_position';
    RAISE NOTICE 'Indexes: idx_chunks_section_hierarchy, idx_chunks_document_position';
END $$;
