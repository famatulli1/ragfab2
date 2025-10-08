-- ============================================================================
-- RAGFab Images Schema
-- Tables pour stockage et gestion des images extraites des documents PDF
-- ============================================================================

-- Table des images extraites des documents
CREATE TABLE IF NOT EXISTS document_images (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_id UUID REFERENCES chunks(id) ON DELETE SET NULL,

    -- Stockage de l'image
    image_path VARCHAR(500) NOT NULL,  -- Chemin relatif: images/{job_id}/{image_id}.png
    image_base64 TEXT,  -- Image encodée en base64 pour affichage rapide inline
    image_format VARCHAR(10) NOT NULL,  -- png, jpeg, etc.
    image_size_bytes BIGINT,  -- Taille du fichier image

    -- Métadonnées de position dans le document
    page_number INTEGER NOT NULL,
    position JSONB NOT NULL,  -- {x, y, width, height} - coordonnées dans la page

    -- Contenu analysé par VLM
    description TEXT,  -- Description générée par le modèle VLM
    ocr_text TEXT,  -- Texte extrait de l'image par OCR
    confidence_score FLOAT,  -- Score de confiance du VLM (0-1)

    -- Métadonnées supplémentaires
    metadata JSONB DEFAULT '{}',  -- Métadonnées additionnelles (résolution, type graphique, etc.)

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index pour recherche rapide par document
CREATE INDEX IF NOT EXISTS idx_document_images_document_id ON document_images(document_id);

-- Index pour recherche par chunk (liens images-chunks)
CREATE INDEX IF NOT EXISTS idx_document_images_chunk_id ON document_images(chunk_id);

-- Index pour recherche par page
CREATE INDEX IF NOT EXISTS idx_document_images_page_number ON document_images(document_id, page_number);

-- Index GIN pour recherche dans le texte OCR
CREATE INDEX IF NOT EXISTS idx_document_images_ocr_text ON document_images USING gin(to_tsvector('french', COALESCE(ocr_text, '')));

-- Index GIN pour recherche dans les descriptions
CREATE INDEX IF NOT EXISTS idx_document_images_description ON document_images USING gin(to_tsvector('french', COALESCE(description, '')));

-- Fonction pour rechercher des images par texte (OCR ou description)
CREATE OR REPLACE FUNCTION search_images_by_text(
    search_query TEXT,
    document_id_filter UUID DEFAULT NULL,
    limit_results INT DEFAULT 10
)
RETURNS TABLE (
    id UUID,
    document_id UUID,
    page_number INTEGER,
    description TEXT,
    ocr_text TEXT,
    image_path VARCHAR(500),
    relevance_rank FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        di.id,
        di.document_id,
        di.page_number,
        di.description,
        di.ocr_text,
        di.image_path,
        ts_rank(
            to_tsvector('french', COALESCE(di.description, '') || ' ' || COALESCE(di.ocr_text, '')),
            plainto_tsquery('french', search_query)
        ) AS relevance_rank
    FROM document_images di
    WHERE
        (document_id_filter IS NULL OR di.document_id = document_id_filter)
        AND (
            to_tsvector('french', COALESCE(di.description, '')) @@ plainto_tsquery('french', search_query)
            OR to_tsvector('french', COALESCE(di.ocr_text, '')) @@ plainto_tsquery('french', search_query)
        )
    ORDER BY relevance_rank DESC
    LIMIT limit_results;
END;
$$;

-- Vue pour statistiques des images par document
CREATE OR REPLACE VIEW document_image_stats AS
SELECT
    d.id AS document_id,
    d.title AS document_title,
    COUNT(di.id) AS total_images,
    COUNT(di.id) FILTER (WHERE di.ocr_text IS NOT NULL AND LENGTH(di.ocr_text) > 0) AS images_with_text,
    COUNT(di.id) FILTER (WHERE di.description IS NOT NULL) AS images_with_description,
    AVG(di.confidence_score) AS avg_confidence_score,
    SUM(di.image_size_bytes) AS total_images_size_bytes
FROM documents d
LEFT JOIN document_images di ON d.id = di.document_id
GROUP BY d.id, d.title;

-- Commentaires pour documentation
COMMENT ON TABLE document_images IS 'Images extraites des documents PDF avec métadonnées VLM';
COMMENT ON COLUMN document_images.image_path IS 'Chemin relatif du fichier image dans /app/uploads/images/';
COMMENT ON COLUMN document_images.image_base64 IS 'Image encodée en base64 pour affichage inline rapide';
COMMENT ON COLUMN document_images.position IS 'Position {x, y, width, height} dans la page du document';
COMMENT ON COLUMN document_images.description IS 'Description générée par le modèle VLM';
COMMENT ON COLUMN document_images.ocr_text IS 'Texte extrait de l''image par OCR';
COMMENT ON COLUMN document_images.confidence_score IS 'Score de confiance du VLM (0.0-1.0)';
COMMENT ON FUNCTION search_images_by_text IS 'Recherche full-text dans les descriptions et textes OCR des images';
COMMENT ON VIEW document_image_stats IS 'Statistiques d''images par document';

-- Afficher le récapitulatif
DO $$
BEGIN
    RAISE NOTICE '✅ Schéma images créé avec succès !';
    RAISE NOTICE '';
    RAISE NOTICE 'Table créée :';
    RAISE NOTICE '  - document_images (images extraites avec VLM)';
    RAISE NOTICE '';
    RAISE NOTICE 'Fonctionnalités :';
    RAISE NOTICE '  - Stockage hybride (fichiers + base64)';
    RAISE NOTICE '  - Position précise dans le document';
    RAISE NOTICE '  - Description VLM + OCR text';
    RAISE NOTICE '  - Recherche full-text dans images';
    RAISE NOTICE '  - Statistiques par document';
END $$;
