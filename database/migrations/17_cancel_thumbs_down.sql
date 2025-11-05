-- Migration 17: Add cancellation support to thumbs down ratings
-- Description: Allows admin to cancel thumbs down if caused by poorly formulated user question
-- Date: 2025-01-05
-- Author: RAGFab Team

-- Add cancellation columns to message_ratings table
ALTER TABLE message_ratings
ADD COLUMN IF NOT EXISTS is_cancelled BOOLEAN DEFAULT false,
ADD COLUMN IF NOT EXISTS cancelled_by UUID REFERENCES users(id),
ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS cancellation_reason TEXT;

-- Add comments for documentation
COMMENT ON COLUMN message_ratings.is_cancelled IS 'True if rating was cancelled by admin (soft delete)';
COMMENT ON COLUMN message_ratings.cancelled_by IS 'Admin user who cancelled the rating';
COMMENT ON COLUMN message_ratings.cancelled_at IS 'Timestamp when rating was cancelled';
COMMENT ON COLUMN message_ratings.cancellation_reason IS 'Admin reason for cancellation (required for accountability)';

-- Create partial index for performance (only index non-cancelled ratings)
-- This speeds up WHERE is_cancelled = false queries (most common case)
CREATE INDEX IF NOT EXISTS idx_message_ratings_is_cancelled
    ON message_ratings(is_cancelled) WHERE is_cancelled = false;

-- Verify migration
DO $$
BEGIN
    -- Check that all columns were created
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'message_ratings' AND column_name = 'is_cancelled'
    ) THEN
        RAISE EXCEPTION 'Migration failed: is_cancelled column not created';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'message_ratings' AND column_name = 'cancelled_by'
    ) THEN
        RAISE EXCEPTION 'Migration failed: cancelled_by column not created';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'message_ratings' AND column_name = 'cancelled_at'
    ) THEN
        RAISE EXCEPTION 'Migration failed: cancelled_at column not created';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'message_ratings' AND column_name = 'cancellation_reason'
    ) THEN
        RAISE EXCEPTION 'Migration failed: cancellation_reason column not created';
    END IF;

    -- Check that index was created
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE tablename = 'message_ratings' AND indexname = 'idx_message_ratings_is_cancelled'
    ) THEN
        RAISE EXCEPTION 'Migration failed: idx_message_ratings_is_cancelled index not created';
    END IF;

    RAISE NOTICE 'Migration 17 completed successfully: Cancellation support added to message_ratings';
END $$;
