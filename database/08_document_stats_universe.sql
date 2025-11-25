-- ============================================================================
-- RAGFab Update document_stats view to include universe info
-- ============================================================================

-- Mettre a jour la vue document_stats pour inclure l'univers
CREATE OR REPLACE VIEW document_stats AS
SELECT
    d.id,
    d.title,
    d.source,
    d.created_at,
    d.universe_id,
    pu.name AS universe_name,
    pu.color AS universe_color,
    COUNT(c.id) AS chunk_count,
    SUM(LENGTH(c.content)) AS total_content_length,
    AVG(c.token_count) AS avg_chunk_tokens
FROM documents d
LEFT JOIN chunks c ON d.id = c.document_id
LEFT JOIN product_universes pu ON d.universe_id = pu.id
GROUP BY d.id, d.title, d.source, d.created_at, d.universe_id, pu.name, pu.color;

COMMENT ON VIEW document_stats IS 'Statistiques agregees par document avec univers';

-- Afficher le recap
DO $$
BEGIN
    RAISE NOTICE '============================================';
    RAISE NOTICE ' Document Stats Universe - Migration Complete';
    RAISE NOTICE '============================================';
    RAISE NOTICE 'View document_stats updated with universe_id, universe_name, universe_color';
END $$;
