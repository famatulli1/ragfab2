-- =====================================================
-- Migration 20: User Suggestion Preference
-- =====================================================
-- Description: Add suggestion_mode column to users table
--              to allow per-user customization of question
--              reformulation suggestions display
-- Date: 2025-11-26
-- =====================================================

-- Add suggestion_mode column to users table
-- NULL = use global QUESTION_QUALITY_PHASE setting
-- 'off' = disable suggestions for this user
-- 'soft' = show suggestions after response (non-blocking)
-- 'interactive' = show suggestions before response (blocking)
ALTER TABLE users ADD COLUMN IF NOT EXISTS suggestion_mode VARCHAR(20) DEFAULT NULL;

-- Add constraint to ensure valid values
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_suggestion_mode_valid'
    ) THEN
        ALTER TABLE users ADD CONSTRAINT chk_suggestion_mode_valid
            CHECK (suggestion_mode IS NULL OR suggestion_mode IN ('off', 'soft', 'interactive'));
    END IF;
END $$;

-- Add documentation comment
COMMENT ON COLUMN users.suggestion_mode IS
    'User preference for question reformulation suggestions: NULL=use global setting, off=disabled, soft=after response, interactive=before response';
