-- ============================================================================
-- Migration 13: Quality Management System
-- Description: Tables pour gestion qualité manuelle + tracking analyses IA
-- Date: 2025-01-31
-- ============================================================================

-- ============================================================================
-- Table audit_log : Traçabilité complète des décisions qualité
-- ============================================================================
CREATE TABLE IF NOT EXISTS quality_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chunk_id UUID REFERENCES chunks(id) ON DELETE CASCADE,
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    action VARCHAR(50) NOT NULL, -- 'blacklist' | 'unblacklist' | 'whitelist' | 'ignore_recommendation'
    reason TEXT,
    decided_by VARCHAR(50) NOT NULL, -- 'ai_worker' | 'cron' | admin user_id
    ai_analysis JSONB, -- Stocke analyse complète Chocolatine
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Index pour requêtes rapides
CREATE INDEX IF NOT EXISTS idx_audit_log_chunk
    ON quality_audit_log(chunk_id);

CREATE INDEX IF NOT EXISTS idx_audit_log_document
    ON quality_audit_log(document_id);

CREATE INDEX IF NOT EXISTS idx_audit_log_date
    ON quality_audit_log(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_audit_log_action
    ON quality_audit_log(action);

COMMENT ON TABLE quality_audit_log IS
    'Historique complet des décisions qualité (IA + humain)';

COMMENT ON COLUMN quality_audit_log.action IS
    'Type d''action : blacklist, unblacklist, whitelist, ignore_recommendation';

COMMENT ON COLUMN quality_audit_log.decided_by IS
    'Qui a pris la décision : ai_worker, cron, ou user_id admin';

COMMENT ON COLUMN quality_audit_log.ai_analysis IS
    'JSON contenant analyse complète Chocolatine (feedbacks, reasoning, confidence)';

-- ============================================================================
-- Table analysis_runs : Tracking des analyses IA (auto + manuelles)
-- ============================================================================
CREATE TABLE IF NOT EXISTS analysis_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    status VARCHAR(20) NOT NULL, -- 'running' | 'completed' | 'failed'
    progress INTEGER DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
    started_by VARCHAR(50) NOT NULL, -- 'cron' | admin user_id
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP,
    duration_seconds INTEGER,
    chunks_analyzed INTEGER DEFAULT 0,
    chunks_blacklisted INTEGER DEFAULT 0,
    documents_flagged INTEGER DEFAULT 0,
    error_message TEXT,
    metadata JSONB -- Stats additionnelles (appels Chocolatine, etc.)
);

-- Index pour requêtes rapides
CREATE INDEX IF NOT EXISTS idx_analysis_runs_status
    ON analysis_runs(status);

CREATE INDEX IF NOT EXISTS idx_analysis_runs_date
    ON analysis_runs(started_at DESC);

CREATE INDEX IF NOT EXISTS idx_analysis_runs_started_by
    ON analysis_runs(started_by);

COMMENT ON TABLE analysis_runs IS
    'Tracking analyses qualité IA : worker nocturne + déclenchement manuel';

COMMENT ON COLUMN analysis_runs.status IS
    'Statut : running (en cours), completed (terminé), failed (erreur)';

COMMENT ON COLUMN analysis_runs.progress IS
    'Progression 0-100% pour affichage temps réel';

COMMENT ON COLUMN analysis_runs.started_by IS
    'Origine : cron (worker auto) ou user_id (trigger manuel admin)';

-- ============================================================================
-- Colonne whitelist : Protection contre blacklist automatique
-- ============================================================================
ALTER TABLE chunk_quality_scores
ADD COLUMN IF NOT EXISTS is_whitelisted BOOLEAN DEFAULT false;

COMMENT ON COLUMN chunk_quality_scores.is_whitelisted IS
    'Si true, chunk protégé contre blacklist automatique (décision admin)';

-- Index pour filtrage worker
CREATE INDEX IF NOT EXISTS idx_chunk_quality_whitelisted
    ON chunk_quality_scores(is_whitelisted)
    WHERE is_whitelisted = true;

-- ============================================================================
-- Vue pour analyses récentes avec stats
-- ============================================================================
CREATE OR REPLACE VIEW recent_analysis_runs AS
SELECT
    ar.id,
    ar.status,
    ar.started_by,
    ar.started_at,
    ar.completed_at,
    ar.duration_seconds,
    ar.chunks_analyzed,
    ar.chunks_blacklisted,
    ar.documents_flagged,
    ar.error_message,
    CASE
        WHEN ar.started_by = 'cron' THEN '🤖 Automatique'
        ELSE '👤 Manuel'
    END as run_type,
    CASE
        WHEN ar.status = 'completed' THEN '✅'
        WHEN ar.status = 'failed' THEN '❌'
        ELSE '⏳'
    END as status_icon
FROM analysis_runs ar
ORDER BY ar.started_at DESC
LIMIT 50;

COMMENT ON VIEW recent_analysis_runs IS
    'Vue des 50 dernières analyses avec icônes et formatage';

-- ============================================================================
-- Fonction helper : Marquer analyse comme complétée
-- ============================================================================
CREATE OR REPLACE FUNCTION complete_analysis_run(
    p_run_id UUID,
    p_chunks_analyzed INTEGER,
    p_chunks_blacklisted INTEGER,
    p_documents_flagged INTEGER
)
RETURNS VOID AS $$
BEGIN
    UPDATE analysis_runs
    SET
        status = 'completed',
        progress = 100,
        completed_at = NOW(),
        duration_seconds = EXTRACT(EPOCH FROM (NOW() - started_at))::INTEGER,
        chunks_analyzed = p_chunks_analyzed,
        chunks_blacklisted = p_chunks_blacklisted,
        documents_flagged = p_documents_flagged
    WHERE id = p_run_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION complete_analysis_run IS
    'Helper pour marquer analyse comme terminée avec stats finales';

-- ============================================================================
-- Fonction helper : Marquer analyse comme échouée
-- ============================================================================
CREATE OR REPLACE FUNCTION fail_analysis_run(
    p_run_id UUID,
    p_error_message TEXT
)
RETURNS VOID AS $$
BEGIN
    UPDATE analysis_runs
    SET
        status = 'failed',
        completed_at = NOW(),
        duration_seconds = EXTRACT(EPOCH FROM (NOW() - started_at))::INTEGER,
        error_message = p_error_message
    WHERE id = p_run_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fail_analysis_run IS
    'Helper pour marquer analyse comme échouée avec message d''erreur';

-- ============================================================================
-- Fonction helper : Mettre à jour progression
-- ============================================================================
CREATE OR REPLACE FUNCTION update_analysis_progress(
    p_run_id UUID,
    p_progress INTEGER
)
RETURNS VOID AS $$
BEGIN
    UPDATE analysis_runs
    SET progress = p_progress
    WHERE id = p_run_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION update_analysis_progress IS
    'Helper pour mettre à jour progression 0-100% (polling frontend)';

-- ============================================================================
-- Stats initiales
-- ============================================================================
DO $$
DECLARE
    chunks_with_quality INTEGER;
    docs_with_quality INTEGER;
BEGIN
    SELECT COUNT(*) INTO chunks_with_quality FROM chunk_quality_scores;
    SELECT COUNT(*) INTO docs_with_quality FROM document_quality_scores;

    RAISE NOTICE '✅ Migration 13 appliquée avec succès !';
    RAISE NOTICE '';
    RAISE NOTICE 'Tables créées :';
    RAISE NOTICE '  - quality_audit_log (traçabilité décisions)';
    RAISE NOTICE '  - analysis_runs (tracking analyses IA)';
    RAISE NOTICE '';
    RAISE NOTICE 'Colonnes ajoutées :';
    RAISE NOTICE '  - chunk_quality_scores.is_whitelisted (protection)';
    RAISE NOTICE '';
    RAISE NOTICE 'Fonctions helpers créées :';
    RAISE NOTICE '  - complete_analysis_run()';
    RAISE NOTICE '  - fail_analysis_run()';
    RAISE NOTICE '  - update_analysis_progress()';
    RAISE NOTICE '';
    RAISE NOTICE 'Stats actuelles :';
    RAISE NOTICE '  - Chunks avec score qualité : %', chunks_with_quality;
    RAISE NOTICE '  - Documents avec score qualité : %', docs_with_quality;
    RAISE NOTICE '';
    RAISE NOTICE 'Prochaine étape : Créer analytics-worker pour remplir les tables';
END $$;
