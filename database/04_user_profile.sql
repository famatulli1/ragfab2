-- ============================================================================
-- RAGFab User Profile Schema
-- Add user profile fields and first login flag
-- ============================================================================

-- Add user profile columns
ALTER TABLE users ADD COLUMN IF NOT EXISTS first_name VARCHAR(100);
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_name VARCHAR(100);
ALTER TABLE users ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN DEFAULT false;

-- Update default admin user with profile data
UPDATE users SET
  first_name = 'Admin',
  last_name = 'RAGFab',
  must_change_password = false
WHERE username = 'admin';

-- Create index for first login check
CREATE INDEX IF NOT EXISTS idx_users_must_change_password ON users(must_change_password) WHERE must_change_password = true;

-- Add comments for documentation
COMMENT ON COLUMN users.first_name IS 'User first name (for avatar personalization)';
COMMENT ON COLUMN users.last_name IS 'User last name';
COMMENT ON COLUMN users.must_change_password IS 'Flag to force password change on first login';

-- Display summary
DO $$
BEGIN
    RAISE NOTICE '✅ User profile schema updated successfully!';
    RAISE NOTICE '';
    RAISE NOTICE 'New columns added:';
    RAISE NOTICE '  - first_name (VARCHAR(100))';
    RAISE NOTICE '  - last_name (VARCHAR(100))';
    RAISE NOTICE '  - must_change_password (BOOLEAN)';
    RAISE NOTICE '';
    RAISE NOTICE 'Admin user updated with default profile data.';
END $$;
