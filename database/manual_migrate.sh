#!/bin/bash
# =====================================================
# RAGFab - Manual Migration Execution for Coolify
# =====================================================
# Usage: docker exec -i ragfab-postgres bash < database/manual_migrate.sh

set -e

echo "🔄 Starting manual migration process..."

# Check if schema_migrations table exists
TABLE_EXISTS=$(psql -U raguser -d ragdb -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'schema_migrations';" 2>/dev/null || echo "0")

if [ "$TABLE_EXISTS" -eq "0" ]; then
    echo "📋 Creating schema_migrations table..."
    psql -U raguser -d ragdb -f /docker-entrypoint-initdb.d/migrations/00_init_migrations.sql
    echo "✅ Schema_migrations table created"
else
    echo "✅ Schema_migrations table already exists"
fi

# Function to apply migration if not already applied
apply_migration() {
    local migration_file=$1
    local migration_name=$(basename "$migration_file")

    # Check if migration already applied
    APPLIED=$(psql -U raguser -d ragdb -t -c "SELECT COUNT(*) FROM schema_migrations WHERE filename = '$migration_name' AND success = true;" 2>/dev/null || echo "0")

    if [ "$APPLIED" -eq "0" ]; then
        echo "📦 Applying migration: $migration_name"

        START_TIME=$(date +%s%N)
        if psql -U raguser -d ragdb -f "/docker-entrypoint-initdb.d/migrations/$migration_name" > /dev/null 2>&1; then
            END_TIME=$(date +%s%N)
            EXECUTION_TIME=$(( (END_TIME - START_TIME) / 1000000 ))

            # Record success
            psql -U raguser -d ragdb -c "INSERT INTO schema_migrations (filename, success, execution_time_ms, error_message) VALUES ('$migration_name', true, $EXECUTION_TIME, NULL);" > /dev/null 2>&1

            echo "✅ Migration $migration_name applied successfully (${EXECUTION_TIME}ms)"
        else
            # Record failure
            psql -U raguser -d ragdb -c "INSERT INTO schema_migrations (filename, success, execution_time_ms, error_message) VALUES ('$migration_name', false, 0, 'Execution failed');" > /dev/null 2>&1

            echo "❌ Migration $migration_name failed"
            exit 1
        fi
    else
        echo "⏭️  Migration $migration_name already applied, skipping"
    fi
}

# Apply migrations in order
echo ""
echo "🚀 Applying migrations..."
apply_migration "05_enriched_metadata.sql"
apply_migration "06_parent_child_chunks.sql"

echo ""
echo "📊 Migration status:"
psql -U raguser -d ragdb -c "SELECT filename, applied_at, success, execution_time_ms FROM schema_migrations ORDER BY applied_at DESC LIMIT 10;"

echo ""
echo "🎉 All migrations applied successfully!"
