#!/bin/bash
# =====================================================
# RAGFab - Database Migration Rollback System
# =====================================================
# Description: Rolls back the last applied migration
# Usage: ./database/rollback_last_migration.sh
# Date: 2025-01-24

set -e  # Exit on error

# =====================================================
# Configuration
# =====================================================
MIGRATIONS_DIR="/database/migrations"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# =====================================================
# Helper Functions
# =====================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_instruction() {
    echo -e "${CYAN}[ACTION]${NC} $1"
}

# =====================================================
# Get database connection parameters
# =====================================================
get_db_params() {
    # Try to read from .env file if not in environment
    if [ -z "$PGHOST" ] && [ -f "/database/../.env" ]; then
        log_info "Reading database parameters from .env file..."
        export PGHOST=$(grep "^POSTGRES_HOST=" /database/../.env | cut -d'=' -f2 || echo "postgres")
        export PGUSER=$(grep "^POSTGRES_USER=" /database/../.env | cut -d'=' -f2)
        export PGDATABASE=$(grep "^POSTGRES_DB=" /database/../.env | cut -d'=' -f2)
        export PGPASSWORD=$(grep "^POSTGRES_PASSWORD=" /database/../.env | cut -d'=' -f2)
    fi

    # Check required parameters
    if [ -z "$PGHOST" ] || [ -z "$PGUSER" ] || [ -z "$PGDATABASE" ]; then
        log_error "Missing database connection parameters"
        log_error "Required: PGHOST, PGUSER, PGDATABASE, PGPASSWORD"
        exit 1
    fi
}

# =====================================================
# Get last applied migration
# =====================================================
get_last_migration() {
    local result=$(psql -h "$PGHOST" -U "$PGUSER" -d "$PGDATABASE" -t -A -c \
        "SELECT filename FROM schema_migrations WHERE success = true ORDER BY applied_at DESC LIMIT 1" 2>&1)

    if [ $? -ne 0 ]; then
        log_error "Failed to query schema_migrations table"
        log_error "$result"
        exit 1
    fi

    if [ -z "$result" ]; then
        log_warning "No migrations found in schema_migrations table"
        exit 0
    fi

    echo "$result"
}

# =====================================================
# Find rollback file
# =====================================================
find_rollback_file() {
    local migration_filename=$1
    local base_name=$(echo "$migration_filename" | sed 's/\.sql$//')
    local rollback_file="$MIGRATIONS_DIR/${base_name}_DOWN.sql"

    if [ -f "$rollback_file" ]; then
        echo "$rollback_file"
    else
        echo ""
    fi
}

# =====================================================
# Execute rollback SQL
# =====================================================
execute_rollback() {
    local rollback_file=$1
    local migration_filename=$2

    log_info "Executing rollback SQL from: $(basename $rollback_file)"

    if psql -h "$PGHOST" -U "$PGUSER" -d "$PGDATABASE" -f "$rollback_file" > /dev/null 2>&1; then
        log_success "Rollback SQL executed successfully"

        # Remove migration record
        psql -h "$PGHOST" -U "$PGUSER" -d "$PGDATABASE" -c \
            "DELETE FROM schema_migrations WHERE filename = '$migration_filename'" > /dev/null 2>&1

        log_success "Migration record removed from schema_migrations"
        return 0
    else
        local error_msg=$(psql -h "$PGHOST" -U "$PGUSER" -d "$PGDATABASE" -f "$rollback_file" 2>&1)
        log_error "Rollback SQL execution failed"
        log_error "$error_msg"
        return 1
    fi
}

# =====================================================
# Manual rollback instructions
# =====================================================
show_manual_instructions() {
    local migration_filename=$1

    log_warning "No automatic rollback file found (${migration_filename%.sql}_DOWN.sql)"
    log_info ""
    log_info "=========================================="
    log_info "Manual Rollback Instructions"
    log_info "=========================================="
    log_info ""
    log_instruction "You need to manually rollback the changes from: $migration_filename"
    log_info ""
    log_instruction "Steps:"
    log_instruction "1. Review the migration file: cat $MIGRATIONS_DIR/$migration_filename"
    log_instruction "2. Write the reverse SQL operations (DROP, ALTER, DELETE, etc.)"
    log_instruction "3. Execute the reverse SQL manually:"
    log_instruction "   psql -h $PGHOST -U $PGUSER -d $PGDATABASE"
    log_instruction "4. After successful manual rollback, remove the migration record:"
    log_instruction "   psql -h $PGHOST -U $PGUSER -d $PGDATABASE -c \\"
    log_instruction "     \"DELETE FROM schema_migrations WHERE filename = '$migration_filename'\""
    log_info ""
    log_info "=========================================="
    log_info "Alternative: Create a rollback file for next time"
    log_info "=========================================="
    log_info ""
    log_instruction "Create: $MIGRATIONS_DIR/${migration_filename%.sql}_DOWN.sql"
    log_instruction "Example content:"
    log_info ""
    echo -e "${CYAN}-- Rollback for $migration_filename"
    echo -e "-- DROP TABLE IF EXISTS example_table;"
    echo -e "-- ALTER TABLE existing_table DROP COLUMN example_column;"
    echo -e "${NC}"
}

# =====================================================
# Main Rollback Process
# =====================================================
main() {
    log_info "=========================================="
    log_info "RAGFab Database Rollback System"
    log_info "=========================================="

    # Get database parameters
    get_db_params

    # Check if schema_migrations table exists
    if ! psql -h "$PGHOST" -U "$PGUSER" -d "$PGDATABASE" -c "SELECT 1 FROM schema_migrations LIMIT 1" > /dev/null 2>&1; then
        log_error "schema_migrations table does not exist"
        log_error "Run apply_migrations.sh first to initialize the migration system"
        exit 1
    fi

    # Get last migration
    log_info "Fetching last applied migration..."
    local last_migration=$(get_last_migration)

    if [ -z "$last_migration" ]; then
        exit 0
    fi

    log_info "Last applied migration: $last_migration"

    # Check if user really wants to rollback
    log_warning ""
    log_warning "⚠️  WARNING: This will rollback the last migration!"
    log_warning "⚠️  Migration: $last_migration"
    log_warning ""
    read -p "Are you sure you want to continue? (yes/no): " confirm

    if [ "$confirm" != "yes" ]; then
        log_info "Rollback cancelled by user"
        exit 0
    fi

    # Find rollback file
    local rollback_file=$(find_rollback_file "$last_migration")

    if [ -n "$rollback_file" ]; then
        # Automatic rollback
        log_success "Found automatic rollback file: $(basename $rollback_file)"
        if execute_rollback "$rollback_file" "$last_migration"; then
            log_info "=========================================="
            log_success "Rollback completed successfully!"
            log_info "=========================================="
            log_info ""
            log_info "Next steps:"
            log_instruction "1. Verify database state"
            log_instruction "2. Fix the migration file if needed: $MIGRATIONS_DIR/$last_migration"
            log_instruction "3. Re-apply migration: docker-compose up db-migrations"
            exit 0
        else
            exit 1
        fi
    else
        # Manual rollback required
        show_manual_instructions "$last_migration"
        exit 0
    fi
}

# =====================================================
# Execute Main
# =====================================================
main
