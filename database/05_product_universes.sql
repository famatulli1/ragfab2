-- ============================================================================
-- RAGFab Product Universes Schema
-- Gestion des univers produits pour la segmentation des documents
-- ============================================================================

-- Table des univers produits
CREATE TABLE IF NOT EXISTS product_universes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    slug VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    detection_keywords TEXT[],  -- Mots-clés pour détection automatique
    color VARCHAR(7) DEFAULT '#6366f1',  -- Couleur hex pour l'UI
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index pour recherche rapide
CREATE INDEX IF NOT EXISTS idx_product_universes_slug ON product_universes(slug);
CREATE INDEX IF NOT EXISTS idx_product_universes_active ON product_universes(is_active);

-- Trigger pour updated_at
CREATE OR REPLACE FUNCTION update_product_universes_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_product_universes_updated_at ON product_universes;
CREATE TRIGGER trigger_product_universes_updated_at
    BEFORE UPDATE ON product_universes
    FOR EACH ROW
    EXECUTE FUNCTION update_product_universes_updated_at();

-- Ajouter la colonne universe_id à la table documents
ALTER TABLE documents
ADD COLUMN IF NOT EXISTS universe_id UUID REFERENCES product_universes(id) ON DELETE SET NULL;

-- Index pour filtrage par univers
CREATE INDEX IF NOT EXISTS idx_documents_universe ON documents(universe_id);

-- Insérer quelques univers par défaut
INSERT INTO product_universes (name, slug, description, detection_keywords, color) VALUES
    ('Medimail', 'medimail', 'Messagerie sécurisée de santé', ARRAY['medimail', 'messagerie', 'mail santé'], '#3b82f6'),
    ('Magh2', 'magh2', 'Gestion administrative hospitalière', ARRAY['magh2', 'gestion administrative', 'hospital'], '#10b981'),
    ('Sillage', 'sillage', 'Dossier patient informatisé', ARRAY['sillage', 'dossier patient', 'dpi'], '#f59e0b')
ON CONFLICT (slug) DO NOTHING;

-- Commentaires
COMMENT ON TABLE product_universes IS 'Univers produits pour segmenter les documents RAG';
COMMENT ON COLUMN product_universes.detection_keywords IS 'Mots-clés pour suggérer automatiquement l univers lors de l ingestion';
COMMENT ON COLUMN documents.universe_id IS 'Univers produit auquel appartient ce document';

-- Afficher le récapitulatif
DO $$
BEGIN
    RAISE NOTICE '============================================';
    RAISE NOTICE ' Product Universes Schema - Migration Complete';
    RAISE NOTICE '============================================';
    RAISE NOTICE 'Table product_universes created';
    RAISE NOTICE 'Column documents.universe_id added';
    RAISE NOTICE 'Default universes inserted: Medimail, Magh2, Sillage';
    RAISE NOTICE '============================================';
END $$;
