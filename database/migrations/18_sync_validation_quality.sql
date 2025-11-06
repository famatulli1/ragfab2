-- Migration 18: Sync thumbs_down_validations to document_quality_scores
-- Description: Synchronise les validations existantes avec la table document_quality_scores
-- Date: 2025-01-06
-- Purpose: Fix bug where validated missing_sources don't appear in "Documents à réingérer" tab

-- ==============================================================================
-- PART 1: Synchronize existing validations to document_quality_scores
-- ==============================================================================

-- Insert or update document_quality_scores for all validated missing_sources
INSERT INTO document_quality_scores (
    document_id,
    needs_reingestion,
    reingestion_reason,
    updated_at
)
SELECT DISTINCT
    c.document_id,
    true AS needs_reingestion,
    'Synchronized from thumbs_down_validations - ' ||
    COUNT(*) || ' validation(s) marked missing_sources' AS reingestion_reason,
    NOW() AS updated_at
FROM thumbs_down_validations v
CROSS JOIN LATERAL jsonb_array_elements(v.sources_used) as source
JOIN chunks c ON c.id = (source->>'chunk_id')::UUID
WHERE
    -- Only validated missing_sources
    (v.admin_override = 'missing_sources' OR
     (v.ai_classification = 'missing_sources' AND v.admin_override IS NULL))
    -- That are marked for reingestion
    AND v.admin_action = 'mark_for_reingestion'
    -- Sources exist
    AND v.sources_used IS NOT NULL
    AND jsonb_typeof(v.sources_used) = 'array'
GROUP BY c.document_id

ON CONFLICT (document_id) DO UPDATE
SET
    needs_reingestion = true,
    updated_at = NOW(),
    reingestion_reason = COALESCE(
        document_quality_scores.reingestion_reason || ' | ',
        ''
    ) || 'Synchronized from thumbs_down_validations';

-- Log how many documents were synced
DO $$
DECLARE
    synced_count INTEGER;
BEGIN
    SELECT COUNT(DISTINCT c.document_id)
    INTO synced_count
    FROM thumbs_down_validations v
    CROSS JOIN LATERAL jsonb_array_elements(v.sources_used) as source
    JOIN chunks c ON c.id = (source->>'chunk_id')::UUID
    WHERE
        (v.admin_override = 'missing_sources' OR
         (v.ai_classification = 'missing_sources' AND v.admin_override IS NULL))
        AND v.admin_action = 'mark_for_reingestion'
        AND v.sources_used IS NOT NULL
        AND jsonb_typeof(v.sources_used) = 'array';

    RAISE NOTICE 'Synchronized % documents from thumbs_down_validations to document_quality_scores', synced_count;
END $$;

-- ==============================================================================
-- PART 2: Create audit log entries for the sync
-- ==============================================================================

-- Create audit log entries for each synchronized document
INSERT INTO quality_audit_log (
    document_id,
    action,
    reason,
    decided_by,
    ai_analysis
)
SELECT DISTINCT
    c.document_id,
    'mark_for_reingestion' AS action,
    'Migration 18: Synced from thumbs_down_validations (' ||
    COUNT(*) || ' validation(s))' AS reason,
    'system_migration' AS decided_by,
    jsonb_build_object(
        'migration_id', '18_sync_validation_quality',
        'validation_count', COUNT(*),
        'synced_at', NOW()
    ) AS ai_analysis
FROM thumbs_down_validations v
CROSS JOIN LATERAL jsonb_array_elements(v.sources_used) as source
JOIN chunks c ON c.id = (source->>'chunk_id')::UUID
WHERE
    (v.admin_override = 'missing_sources' OR
     (v.ai_classification = 'missing_sources' AND v.admin_override IS NULL))
    AND v.admin_action = 'mark_for_reingestion'
    AND v.sources_used IS NOT NULL
    AND jsonb_typeof(v.sources_used) = 'array'
GROUP BY c.document_id;

-- ==============================================================================
-- PART 3: Create helper function for ongoing sync (called by backend)
-- ==============================================================================

-- Function to sync a single validation to document_quality_scores
-- Note: This function is NOT used by the current backend implementation
-- Backend uses inline SQL for better error handling
-- Keeping it for potential future use or manual operations
CREATE OR REPLACE FUNCTION sync_validation_to_quality_scores(
    p_validation_id UUID,
    p_needs_reingestion BOOLEAN,
    p_reason TEXT
)
RETURNS INTEGER AS $$
DECLARE
    v_documents_count INTEGER;
BEGIN
    -- Sync all documents from this validation's sources
    WITH synced_docs AS (
        INSERT INTO document_quality_scores (
            document_id,
            needs_reingestion,
            reingestion_reason,
            updated_at
        )
        SELECT DISTINCT
            c.document_id,
            p_needs_reingestion,
            p_reason,
            NOW()
        FROM thumbs_down_validations v
        CROSS JOIN LATERAL jsonb_array_elements(v.sources_used) as source
        JOIN chunks c ON c.id = (source->>'chunk_id')::UUID
        WHERE v.id = p_validation_id
            AND v.sources_used IS NOT NULL
            AND jsonb_typeof(v.sources_used) = 'array'

        ON CONFLICT (document_id) DO UPDATE
        SET
            needs_reingestion = EXCLUDED.needs_reingestion,
            updated_at = NOW(),
            reingestion_reason = COALESCE(
                document_quality_scores.reingestion_reason || ' | ',
                ''
            ) || EXCLUDED.reingestion_reason
        RETURNING document_id
    )
    SELECT COUNT(*) INTO v_documents_count FROM synced_docs;

    RETURN v_documents_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION sync_validation_to_quality_scores IS
'Synchronizes a thumbs_down validation to document_quality_scores table. Returns number of documents synced.';

-- ==============================================================================
-- PART 4: Verification queries (commented for reference)
-- ==============================================================================

-- Uncomment to verify sync results:

-- -- Check how many documents now have needs_reingestion = true
-- SELECT COUNT(*)
-- FROM document_quality_scores
-- WHERE needs_reingestion = true;

-- -- Check which documents were synced
-- SELECT
--     dqs.document_id,
--     d.title,
--     dqs.needs_reingestion,
--     dqs.reingestion_reason,
--     dqs.updated_at
-- FROM document_quality_scores dqs
-- JOIN documents d ON dqs.document_id = d.id
-- WHERE dqs.needs_reingestion = true
-- ORDER BY dqs.updated_at DESC;

-- -- Count validations per document
-- SELECT
--     c.document_id,
--     d.title,
--     COUNT(*) as validation_count
-- FROM thumbs_down_validations v
-- CROSS JOIN LATERAL jsonb_array_elements(v.sources_used) as source
-- JOIN chunks c ON c.id = (source->>'chunk_id')::UUID
-- JOIN documents d ON c.document_id = d.id
-- WHERE
--     (v.admin_override = 'missing_sources' OR
--      (v.ai_classification = 'missing_sources' AND v.admin_override IS NULL))
--     AND v.admin_action = 'mark_for_reingestion'
--     AND v.sources_used IS NOT NULL
--     AND jsonb_typeof(v.sources_used) = 'array'
-- GROUP BY c.document_id, d.title
-- ORDER BY validation_count DESC;
