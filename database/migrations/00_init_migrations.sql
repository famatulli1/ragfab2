-- =====================================================
-- Migration 00: Initialize Migration Tracking System
-- =====================================================
-- Description: Creates the schema_migrations table to track applied database migrations
-- Date: 2025-01-24
-- Author: RAGFab Migration System

-- Create schema_migrations table if it doesn't exist
CREATE TABLE IF NOT EXISTS schema_migrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename VARCHAR(255) NOT NULL UNIQUE,
    applied_at TIMESTAMP NOT NULL DEFAULT NOW(),
    success BOOLEAN NOT NULL DEFAULT true,
    error_message TEXT,
    execution_time_ms INTEGER,
    checksum VARCHAR(64),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create index on filename for fast lookups
CREATE INDEX IF NOT EXISTS idx_schema_migrations_filename
    ON schema_migrations(filename);

-- Create index on applied_at for chronological queries
CREATE INDEX IF NOT EXISTS idx_schema_migrations_applied_at
    ON schema_migrations(applied_at DESC);

-- Create index on success for filtering failed migrations
CREATE INDEX IF NOT EXISTS idx_schema_migrations_success
    ON schema_migrations(success);

-- Insert record for this migration itself
INSERT INTO schema_migrations (filename, success, execution_time_ms)
VALUES ('00_init_migrations.sql', true, 0)
ON CONFLICT (filename) DO NOTHING;

-- Grant permissions (if using specific migration user)
-- GRANT SELECT, INSERT, UPDATE ON schema_migrations TO raguser;

COMMENT ON TABLE schema_migrations IS 'Tracks all applied database migrations with execution metadata';
COMMENT ON COLUMN schema_migrations.filename IS 'Migration filename (e.g., 01_add_user_table.sql)';
COMMENT ON COLUMN schema_migrations.applied_at IS 'Timestamp when migration was successfully applied';
COMMENT ON COLUMN schema_migrations.success IS 'Whether migration succeeded (true) or failed (false)';
COMMENT ON COLUMN schema_migrations.error_message IS 'Error message if migration failed';
COMMENT ON COLUMN schema_migrations.execution_time_ms IS 'Migration execution time in milliseconds';
COMMENT ON COLUMN schema_migrations.checksum IS 'SHA-256 checksum of migration file content (for integrity validation)';
