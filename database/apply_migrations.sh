#!/bin/bash
# =====================================================
# RAGFab - Automatic Database Migration System
# =====================================================
# Description: Detects and applies new SQL migrations automatically
# Usage: Called automatically by db-migrations service in docker-compose
# Date: 2025-01-24

set -e  # Exit on error

# =====================================================
# Configuration
# =====================================================
MIGRATIONS_DIR="/database/migrations"
MAX_RETRIES=30
RETRY_INTERVAL=2

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

# =====================================================
# Wait for PostgreSQL to be ready
# =====================================================
wait_for_postgres() {
    log_info "Waiting for PostgreSQL to be ready..."

    local retry_count=0
    until pg_isready -h "$PGHOST" -U "$PGUSER" -d "$PGDATABASE" > /dev/null 2>&1; do
        retry_count=$((retry_count + 1))

        if [ $retry_count -ge $MAX_RETRIES ]; then
            log_error "PostgreSQL did not become ready after $MAX_RETRIES attempts"
            exit 1
        fi

        log_info "Attempt $retry_count/$MAX_RETRIES - PostgreSQL not ready, retrying in ${RETRY_INTERVAL}s..."
        sleep $RETRY_INTERVAL
    done

    log_success "PostgreSQL is ready!"
}

# =====================================================
# Initialize migration tracking table
# =====================================================
initialize_migration_table() {
    log_info "Initializing migration tracking table..."

    if psql -h "$PGHOST" -U "$PGUSER" -d "$PGDATABASE" -c "SELECT 1 FROM schema_migrations LIMIT 1" > /dev/null 2>&1; then
        log_info "Migration table already exists, skipping initialization"
        return 0
    fi

    log_info "Creating schema_migrations table..."
    if psql -h "$PGHOST" -U "$PGUSER" -d "$PGDATABASE" -f "$MIGRATIONS_DIR/00_init_migrations.sql" > /dev/null 2>&1; then
        log_success "Migration tracking table created successfully"
    else
        log_error "Failed to create migration tracking table"
        exit 1
    fi
}

# =====================================================
# Check if migration was already applied
# =====================================================
is_migration_applied() {
    local filename=$1
    local result=$(psql -h "$PGHOST" -U "$PGUSER" -d "$PGDATABASE" -t -A -c \
        "SELECT COUNT(*) FROM schema_migrations WHERE filename = '$filename' AND success = true")

    if [ "$result" -gt 0 ]; then
        return 0  # Already applied
    else
        return 1  # Not applied
    fi
}

# =====================================================
# Calculate file checksum (SHA-256)
# =====================================================
calculate_checksum() {
    local filepath=$1
    if command -v sha256sum > /dev/null 2>&1; then
        sha256sum "$filepath" | awk '{print $1}'
    elif command -v shasum > /dev/null 2>&1; then
        shasum -a 256 "$filepath" | awk '{print $1}'
    else
        echo "checksum_unavailable"
    fi
}

# =====================================================
# Apply a single migration
# =====================================================
apply_migration() {
    local filepath=$1
    local filename=$(basename "$filepath")

    log_info "Applying migration: $filename"

    # Calculate checksum
    local checksum=$(calculate_checksum "$filepath")

    # Start timing
    local start_time=$(date +%s%3N)

    # Apply migration
    if psql -h "$PGHOST" -U "$PGUSER" -d "$PGDATABASE" -f "$filepath" > /dev/null 2>&1; then
        local end_time=$(date +%s%3N)
        local execution_time=$((end_time - start_time))

        # Record success
        psql -h "$PGHOST" -U "$PGUSER" -d "$PGDATABASE" -c \
            "INSERT INTO schema_migrations (filename, success, execution_time_ms, checksum)
             VALUES ('$filename', true, $execution_time, '$checksum')
             ON CONFLICT (filename) DO UPDATE
             SET applied_at = NOW(), success = true, execution_time_ms = $execution_time, checksum = '$checksum'" \
            > /dev/null 2>&1

        log_success "Migration $filename applied successfully (${execution_time}ms)"
        return 0
    else
        local end_time=$(date +%s%3N)
        local execution_time=$((end_time - start_time))

        # Get error message
        local error_msg=$(psql -h "$PGHOST" -U "$PGUSER" -d "$PGDATABASE" -f "$filepath" 2>&1 | tail -n 5)

        # Record failure
        psql -h "$PGHOST" -U "$PGUSER" -d "$PGDATABASE" -c \
            "INSERT INTO schema_migrations (filename, success, execution_time_ms, checksum, error_message)
             VALUES ('$filename', false, $execution_time, '$checksum', \$\$${error_msg}\$\$)
             ON CONFLICT (filename) DO UPDATE
             SET applied_at = NOW(), success = false, execution_time_ms = $execution_time,
                 checksum = '$checksum', error_message = \$\$${error_msg}\$\$" \
            > /dev/null 2>&1

        log_error "Migration $filename failed after ${execution_time}ms"
        log_error "Error: $error_msg"
        return 1
    fi
}

# =====================================================
# Main Migration Process
# =====================================================
main() {
    log_info "=========================================="
    log_info "RAGFab Database Migration System"
    log_info "=========================================="

    # Check if AUTO_APPLY_MIGRATIONS is disabled
    if [ "${AUTO_APPLY_MIGRATIONS:-true}" = "false" ]; then
        log_warning "AUTO_APPLY_MIGRATIONS is disabled, skipping migrations"
        exit 0
    fi

    # Wait for PostgreSQL
    wait_for_postgres

    # Initialize migration table
    initialize_migration_table

    # Get list of migration files (sorted alphabetically)
    local migration_files=$(find "$MIGRATIONS_DIR" -maxdepth 1 -name "*.sql" -type f | sort)

    if [ -z "$migration_files" ]; then
        log_warning "No migration files found in $MIGRATIONS_DIR"
        exit 0
    fi

    log_info "Found $(echo "$migration_files" | wc -l) migration file(s)"

    # Track migration statistics
    local applied_count=0
    local skipped_count=0
    local failed_count=0

    # Apply each migration
    for migration_file in $migration_files; do
        local filename=$(basename "$migration_file")

        # Skip 00_init_migrations.sql (already executed)
        if [ "$filename" = "00_init_migrations.sql" ]; then
            continue
        fi

        # Check if already applied
        if is_migration_applied "$filename"; then
            log_info "Migration $filename already applied, skipping"
            skipped_count=$((skipped_count + 1))
            continue
        fi

        # Apply migration
        if apply_migration "$migration_file"; then
            applied_count=$((applied_count + 1))
        else
            failed_count=$((failed_count + 1))
            log_error "Migration failed, stopping process"
            log_error "Database may be in inconsistent state"
            exit 1  # Exit with error (prevents container startup)
        fi
    done

    # Summary
    log_info "=========================================="
    log_info "Migration Summary:"
    log_success "  Applied: $applied_count"
    log_info "  Skipped: $skipped_count"
    if [ $failed_count -gt 0 ]; then
        log_error "  Failed: $failed_count"
    fi
    log_info "=========================================="

    if [ $applied_count -gt 0 ]; then
        log_success "All migrations applied successfully!"
    else
        log_info "No new migrations to apply"
    fi

    exit 0
}

# =====================================================
# Execute Main
# =====================================================
main
