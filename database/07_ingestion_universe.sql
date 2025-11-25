-- ============================================================================
-- RAGFab Ingestion Universe
-- Ajout du tracking d'univers dans les jobs d'ingestion
-- ============================================================================

-- Ajouter la colonne universe_id à ingestion_jobs
ALTER TABLE ingestion_jobs
ADD COLUMN IF NOT EXISTS universe_id UUID REFERENCES product_universes(id) ON DELETE SET NULL;

-- Index pour filtrage
CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_universe ON ingestion_jobs(universe_id);

-- Commentaire
COMMENT ON COLUMN ingestion_jobs.universe_id IS 'Univers cible pour le document qui sera créé';

-- Afficher le récapitulatif
DO $$
BEGIN
    RAISE NOTICE '============================================';
    RAISE NOTICE ' Ingestion Universe - Migration Complete';
    RAISE NOTICE '============================================';
    RAISE NOTICE 'Column ingestion_jobs.universe_id added';
    RAISE NOTICE '============================================';
END $$;
