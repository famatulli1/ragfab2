-- ============================================================================
-- Migration 11: Rating Quality Scores
-- Description: Tables pour tracker la qualité des chunks et documents basée sur ratings
-- Date: 2025-01-31
-- ============================================================================

-- Table pour tracker qualité des chunks
CREATE TABLE IF NOT EXISTS chunk_quality_scores (
    chunk_id UUID PRIMARY KEY REFERENCES chunks(id) ON DELETE CASCADE,
    thumbs_up_count INTEGER DEFAULT 0,
    thumbs_down_count INTEGER DEFAULT 0,
    total_appearances INTEGER DEFAULT 0,
    satisfaction_rate FLOAT GENERATED ALWAYS AS
        (CASE WHEN total_appearances > 0
         THEN thumbs_up_count::float / (thumbs_up_count + thumbs_down_count)
         ELSE NULL END) STORED,
    is_blacklisted BOOLEAN DEFAULT false,
    blacklist_reason TEXT,
    last_appearance_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index pour filtrage rapide
CREATE INDEX IF NOT EXISTS idx_chunk_quality_blacklisted
    ON chunk_quality_scores(is_blacklisted);

CREATE INDEX IF NOT EXISTS idx_chunk_quality_rate
    ON chunk_quality_scores(satisfaction_rate);

CREATE INDEX IF NOT EXISTS idx_chunk_quality_appearances
    ON chunk_quality_scores(total_appearances);

CREATE INDEX IF NOT EXISTS idx_chunk_quality_updated
    ON chunk_quality_scores(updated_at DESC);

-- Table pour tracker qualité des documents
CREATE TABLE IF NOT EXISTS document_quality_scores (
    document_id UUID PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
    thumbs_up_count INTEGER DEFAULT 0,
    thumbs_down_count INTEGER DEFAULT 0,
    total_appearances INTEGER DEFAULT 0,
    satisfaction_rate FLOAT GENERATED ALWAYS AS
        (CASE WHEN total_appearances > 0
         THEN thumbs_up_count::float / (thumbs_up_count + thumbs_down_count)
         ELSE NULL END) STORED,
    needs_reingestion BOOLEAN DEFAULT false,
    reingestion_reason TEXT,
    last_appearance_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index pour qualité documents
CREATE INDEX IF NOT EXISTS idx_document_quality_rate
    ON document_quality_scores(satisfaction_rate);

CREATE INDEX IF NOT EXISTS idx_document_quality_needs_reingestion
    ON document_quality_scores(needs_reingestion);

CREATE INDEX IF NOT EXISTS idx_document_quality_updated
    ON document_quality_scores(updated_at DESC);

-- Fonction pour recherche avec filtre qualité
CREATE OR REPLACE FUNCTION match_chunks_quality_filtered(
    query_embedding vector(1024),
    match_count int,
    satisfaction_threshold float DEFAULT 0.3,
    min_appearances int DEFAULT 3
)
RETURNS TABLE (
    id uuid,
    content text,
    metadata jsonb,
    similarity float,
    quality_score float
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id,
        c.content,
        c.metadata,
        1 - (c.embedding <=> query_embedding) as similarity,
        COALESCE(cqs.satisfaction_rate, 0.5) as quality_score  -- Neutral si pas de données
    FROM chunks c
    LEFT JOIN chunk_quality_scores cqs ON c.id = cqs.chunk_id
    WHERE
        -- Exclure chunks blacklistés
        (cqs.is_blacklisted IS NULL OR cqs.is_blacklisted = false)
        -- Exclure chunks avec mauvaise réputation ET significativité statistique
        AND (
            cqs.satisfaction_rate IS NULL  -- Pas encore évalué
            OR cqs.total_appearances < min_appearances  -- Pas assez de données
            OR cqs.satisfaction_rate > satisfaction_threshold  -- Qualité acceptable
        )
    ORDER BY
        -- Combiner similarité vectorielle + score qualité
        (1 - (c.embedding <=> query_embedding)) * 0.7 +  -- 70% vector similarity
        COALESCE(cqs.satisfaction_rate, 0.5) * 0.3  -- 30% quality score
        DESC
    LIMIT match_count * 2;  -- Sur-échantillonner pour avoir marge après filtrage
END;
$$ LANGUAGE plpgsql;

-- Vue pour analyse rapide des problèmes
CREATE OR REPLACE VIEW chunk_quality_issues AS
SELECT
    cqs.chunk_id,
    c.content,
    c.document_id,
    d.title as document_title,
    c.metadata->>'section_hierarchy' as section,
    c.metadata->>'page_number' as page,
    cqs.thumbs_up_count,
    cqs.thumbs_down_count,
    cqs.total_appearances,
    cqs.satisfaction_rate,
    cqs.is_blacklisted,
    cqs.blacklist_reason,
    cqs.last_appearance_at
FROM chunk_quality_scores cqs
JOIN chunks c ON cqs.chunk_id = c.id
JOIN documents d ON c.document_id = d.id
WHERE
    cqs.total_appearances >= 3  -- Significativité statistique
    AND (
        cqs.satisfaction_rate < 0.3  -- Très mauvaise satisfaction
        OR cqs.is_blacklisted = true  -- Déjà blacklisté
    )
ORDER BY
    cqs.thumbs_down_count * cqs.total_appearances DESC;  -- Impact score

-- Commentaires pour documentation
COMMENT ON TABLE chunk_quality_scores IS
    'Scores de qualité par chunk basés sur ratings utilisateurs - permet filtrage auto';

COMMENT ON TABLE document_quality_scores IS
    'Scores de qualité par document agrégés - identifie documents à réingérer';

COMMENT ON COLUMN chunk_quality_scores.satisfaction_rate IS
    'Taux satisfaction: thumbs_up / (thumbs_up + thumbs_down) - NULL si pas de données';

COMMENT ON COLUMN chunk_quality_scores.is_blacklisted IS
    'Si true, chunk exclu des recherches vectorielles automatiquement';

COMMENT ON COLUMN document_quality_scores.needs_reingestion IS
    'Flag automatique si satisfaction <30% avec >10 apparitions';

COMMENT ON FUNCTION match_chunks_quality_filtered IS
    'Recherche vectorielle avec filtre qualité - exclut chunks blacklistés et mauvais scores';

COMMENT ON VIEW chunk_quality_issues IS
    'Vue analytique des chunks problématiques nécessitant attention';

-- Afficher récapitulatif
DO $$
BEGIN
    RAISE NOTICE '✅ Migration 11 appliquée avec succès !';
    RAISE NOTICE '';
    RAISE NOTICE 'Tables créées :';
    RAISE NOTICE '  - chunk_quality_scores (qualité par chunk)';
    RAISE NOTICE '  - document_quality_scores (qualité par document)';
    RAISE NOTICE '';
    RAISE NOTICE 'Fonction créée :';
    RAISE NOTICE '  - match_chunks_quality_filtered (recherche avec filtre qualité)';
    RAISE NOTICE '';
    RAISE NOTICE 'Vue créée :';
    RAISE NOTICE '  - chunk_quality_issues (analyse rapide des problèmes)';
    RAISE NOTICE '';
    RAISE NOTICE 'Prochaine étape : Déployer analytics-worker pour remplir les tables';
END $$;
