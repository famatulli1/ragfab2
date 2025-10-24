# Database Migrations - Developer Guide

Quick reference for creating and managing database migrations in RAGFab.

## 🚀 Quick Start

### Creating a new migration

1. **Create file** with numeric prefix:
   ```bash
   touch database/migrations/07_add_your_feature.sql
   ```

2. **Write idempotent SQL**:
   ```sql
   -- Migration 07: Add your feature
   -- Description: Brief description of changes
   -- Date: 2025-01-24

   ALTER TABLE table_name ADD COLUMN IF NOT EXISTS column_name TYPE;
   CREATE INDEX IF NOT EXISTS idx_name ON table_name(column_name);
   ```

3. **(Optional) Create rollback**:
   ```bash
   touch database/migrations/07_add_your_feature_DOWN.sql
   ```

4. **Deploy** (migrations apply automatically):
   ```bash
   git add database/migrations/
   git commit -m "Add migration: your feature"
   git push
   docker-compose up -d --build  # Migrations run automatically
   ```

## 📝 Naming Convention

**Format**: `{PREFIX}_{DESCRIPTION}.sql`

- **PREFIX**: Two digits (`00-99`)
- **DESCRIPTION**: Snake_case, descriptive

**Examples**:
- ✅ `08_add_document_tags.sql`
- ✅ `09_create_audit_log.sql`
- ✅ `10_alter_chunks_add_metadata.sql`
- ✅ `10_alter_chunks_add_metadata_DOWN.sql` (rollback)

**Don't**:
- ❌ `add_tags.sql` (no prefix)
- ❌ `8_tags.sql` (single digit)
- ❌ `08-add-tags.sql` (dashes instead of underscores)

## 🔧 Migration Template

### Basic Migration

```sql
-- =====================================================
-- Migration XX: Brief Title
-- =====================================================
-- Description: Detailed description of what this migration does
-- Date: YYYY-MM-DD
-- Author: Your Name (optional)
-- Related: Issue #123, Feature request

-- Use IF NOT EXISTS / IF EXISTS for idempotency
ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(255);

-- Add indexes
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- Add constraints
ALTER TABLE users ADD CONSTRAINT IF NOT EXISTS unique_email UNIQUE(email);

-- Add comments (documentation)
COMMENT ON COLUMN users.email IS 'User email address, required for authentication';

-- Insert initial data (if needed)
INSERT INTO config (key, value)
VALUES ('feature_flag_email_verification', 'true')
ON CONFLICT (key) DO NOTHING;
```

### Rollback Template

```sql
-- =====================================================
-- Rollback for XX_migration_name.sql
-- =====================================================
-- WARNING: This will revert changes from the migration
-- Make sure you understand the impact before executing

-- Drop columns
ALTER TABLE users DROP COLUMN IF EXISTS email;

-- Drop indexes
DROP INDEX IF EXISTS idx_users_email;

-- Drop constraints
ALTER TABLE users DROP CONSTRAINT IF EXISTS unique_email;

-- Remove data (be careful!)
DELETE FROM config WHERE key = 'feature_flag_email_verification';
```

## 📋 Existing Migrations

| Prefix | File | Description | Status |
|--------|------|-------------|--------|
| `00` | `00_init_migrations.sql` | Migration tracking system | System |
| `05` | `05_enriched_metadata.sql` | Adjacent chunks metadata | RAG Phase 2.1 |
| `06` | `06_parent_child_chunks.sql` | Hierarchical chunking | RAG Phase 2.2 |

**Next available prefix**: `07`

## ⚙️ How It Works

1. **Automatic detection**: `db-migrations` service runs on every `docker-compose up`
2. **Tracking**: `schema_migrations` table records applied migrations
3. **Execution**: Migrations run in alphabetical order (hence numeric prefixes)
4. **Safety**: If any migration fails, container startup is blocked

## 🔍 Checking Migration Status

```bash
# View migration logs
docker-compose logs db-migrations

# Check applied migrations in database
docker-compose exec postgres psql -U raguser -d ragdb \
  -c "SELECT filename, applied_at, success, execution_time_ms FROM schema_migrations ORDER BY applied_at DESC;"

# View migration tracking table
docker-compose exec postgres psql -U raguser -d ragdb \
  -c "SELECT * FROM schema_migrations WHERE success = false;"  # Show failed migrations
```

## 🔄 Rolling Back

### Automatic (if `_DOWN.sql` exists)

```bash
docker-compose exec postgres bash /database/rollback_last_migration.sh
```

### Manual

```bash
# Connect to database
docker-compose exec postgres psql -U raguser -d ragdb

# Write reverse SQL
ALTER TABLE users DROP COLUMN email;

# Remove migration record
DELETE FROM schema_migrations WHERE filename = '07_add_email.sql';
```

## ✅ Best Practices

### 1. Always use idempotent operations

**Good**:
```sql
ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(255);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
```

**Bad**:
```sql
ALTER TABLE users ADD COLUMN email VARCHAR(255);  -- Will fail on retry
```

### 2. One logical change per migration

**Good**: `08_add_document_categories.sql`
- Creates `categories` table
- Adds `category_id` to `documents`
- Adds foreign key constraint
- Creates indexes

**Bad**: `08_various_changes.sql`
- Changes users table
- Changes documents table
- Changes audit log
- (Too many unrelated changes)

### 3. Test in development first

```bash
# Local testing
docker-compose up -d --build
docker-compose exec postgres psql -U raguser -d ragdb -c "\d table_name"

# Verify data
docker-compose exec postgres psql -U raguser -d ragdb -c "SELECT * FROM table_name LIMIT 5;"
```

### 4. Create rollback for complex migrations

If your migration:
- Drops columns with data
- Changes data types
- Removes constraints
- Modifies existing data

→ **Always create a `_DOWN.sql` file**

### 5. Document impact and dependencies

```sql
-- Migration 08: Add document categories
-- Purpose: Enable document categorization for better organization
-- Impact:
--   - Adds nullable column (no data loss risk)
--   - New foreign key (may slow down inserts slightly)
--   - No existing queries affected
-- Dependencies:
--   - Requires migration 05 (chunks.metadata column)
-- Related:
--   - Issue #123: Document organization feature
--   - Design doc: docs/adr/003-document-categories.md
```

## 🚨 Common Mistakes

### ❌ Forgetting IF NOT EXISTS

```sql
ALTER TABLE users ADD COLUMN email VARCHAR(255);
```

**Problem**: Fails if migration is rerun (e.g., after rollback and reapply)

**Fix**:
```sql
ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(255);
```

### ❌ Dropping columns without backup

```sql
ALTER TABLE users DROP COLUMN old_column;
```

**Problem**: Data lost permanently

**Fix**: Create `_DOWN.sql` with data backup logic first

### ❌ Missing numeric prefix

```sql
add_email_column.sql  # Wrong
```

**Problem**: Execution order undefined

**Fix**: Use `07_add_email_column.sql`

### ❌ Not testing locally

**Problem**: Migration fails in production, blocks deployment

**Fix**: Always test with `docker-compose up -d --build` locally first

## 🔐 Security Considerations

1. **Never commit sensitive data** in migrations
   ```sql
   -- ❌ BAD
   INSERT INTO users (username, password) VALUES ('admin', 'admin123');

   -- ✅ GOOD
   INSERT INTO users (username, password_hash) VALUES ('admin', 'USE_ENV_VAR_IN_PRODUCTION');
   ```

2. **Use environment variables** for secrets
   ```bash
   # In migration script (if needed)
   psql -v password="$ADMIN_PASSWORD" -f migration.sql
   ```

3. **Add proper constraints**
   ```sql
   ALTER TABLE users ADD CONSTRAINT check_email_format
     CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z]{2,}$');
   ```

## 📚 Resources

- **Full documentation**: See `/CLAUDE.md` → "Database Migrations System"
- **Migration scripts**: `/database/apply_migrations.sh`, `/database/rollback_last_migration.sh`
- **Docker service**: See `docker-compose.yml` → `db-migrations` service
- **Tracking table**: `SELECT * FROM schema_migrations;`

## 💡 Tips

1. **Leave gaps in numbering**: Use `05`, `10`, `15` to allow hotfixes like `06`, `11`
2. **Use descriptive names**: Future you will thank present you
3. **Comment liberally**: Explain the "why", not just the "what"
4. **Test rollbacks**: Don't wait for production to test your `_DOWN.sql`
5. **Keep migrations small**: Easier to test, review, and rollback

## ❓ Troubleshooting

**Problem**: Container won't start after adding migration
```bash
# Check logs
docker-compose logs db-migrations

# Common fixes:
# - SQL syntax error → Fix and rebuild
# - Missing IF NOT EXISTS → Add and rebuild
# - Dependency issue → Check migration order
```

**Problem**: Need to skip a migration temporarily
```bash
# Option 1: Disable migrations
AUTO_APPLY_MIGRATIONS=false docker-compose up -d

# Option 2: Mark as applied manually (advanced)
docker-compose exec postgres psql -U raguser -d ragdb
INSERT INTO schema_migrations (filename, success) VALUES ('07_skip_me.sql', true);
```

**Problem**: Migration worked but need to revert
```bash
# Use rollback script
docker-compose exec postgres bash /database/rollback_last_migration.sh

# Or manually mark as not applied
DELETE FROM schema_migrations WHERE filename = '07_problematic.sql';
```

---

**Questions?** Check the full documentation in `/CLAUDE.md` or ask the team!
