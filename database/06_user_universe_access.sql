-- ============================================================================
-- RAGFab User Universe Access Schema
-- Gestion des droits d'accès utilisateurs aux univers
-- ============================================================================

-- Table de liaison users <-> universes (N-N)
CREATE TABLE IF NOT EXISTS user_universe_access (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    universe_id UUID NOT NULL REFERENCES product_universes(id) ON DELETE CASCADE,
    is_default BOOLEAN DEFAULT false,
    granted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    granted_by UUID REFERENCES users(id) ON DELETE SET NULL,
    UNIQUE(user_id, universe_id)
);

-- Index pour les requêtes fréquentes
CREATE INDEX IF NOT EXISTS idx_user_universe_user ON user_universe_access(user_id);
CREATE INDEX IF NOT EXISTS idx_user_universe_universe ON user_universe_access(universe_id);
CREATE INDEX IF NOT EXISTS idx_user_universe_default ON user_universe_access(user_id, is_default) WHERE is_default = true;

-- Trigger pour s'assurer qu'un seul univers par défaut par utilisateur
CREATE OR REPLACE FUNCTION ensure_single_default_universe()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.is_default = true THEN
        UPDATE user_universe_access
        SET is_default = false
        WHERE user_id = NEW.user_id
          AND id != NEW.id
          AND is_default = true;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_single_default_universe ON user_universe_access;
CREATE TRIGGER trigger_single_default_universe
    AFTER INSERT OR UPDATE ON user_universe_access
    FOR EACH ROW
    WHEN (NEW.is_default = true)
    EXECUTE FUNCTION ensure_single_default_universe();

-- Vue pour faciliter les requêtes
CREATE OR REPLACE VIEW user_universes_view AS
SELECT
    uua.id,
    uua.user_id,
    u.username,
    uua.universe_id,
    pu.name AS universe_name,
    pu.slug AS universe_slug,
    pu.color AS universe_color,
    uua.is_default,
    uua.granted_at,
    uua.granted_by,
    gb.username AS granted_by_username
FROM user_universe_access uua
JOIN users u ON uua.user_id = u.id
JOIN product_universes pu ON uua.universe_id = pu.id
LEFT JOIN users gb ON uua.granted_by = gb.id
WHERE pu.is_active = true;

-- Fonction pour récupérer les univers autorisés d'un utilisateur
CREATE OR REPLACE FUNCTION get_user_allowed_universes(p_user_id UUID)
RETURNS TABLE (
    universe_id UUID,
    universe_name VARCHAR,
    universe_slug VARCHAR,
    universe_color VARCHAR,
    is_default BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        pu.id,
        pu.name,
        pu.slug,
        pu.color,
        uua.is_default
    FROM user_universe_access uua
    JOIN product_universes pu ON uua.universe_id = pu.id
    WHERE uua.user_id = p_user_id
      AND pu.is_active = true
    ORDER BY uua.is_default DESC, pu.name;
END;
$$ LANGUAGE plpgsql;

-- Fonction pour récupérer l'univers par défaut d'un utilisateur
CREATE OR REPLACE FUNCTION get_user_default_universe(p_user_id UUID)
RETURNS UUID AS $$
DECLARE
    v_universe_id UUID;
BEGIN
    SELECT universe_id INTO v_universe_id
    FROM user_universe_access uua
    JOIN product_universes pu ON uua.universe_id = pu.id
    WHERE uua.user_id = p_user_id
      AND uua.is_default = true
      AND pu.is_active = true
    LIMIT 1;

    IF v_universe_id IS NULL THEN
        SELECT universe_id INTO v_universe_id
        FROM user_universe_access uua
        JOIN product_universes pu ON uua.universe_id = pu.id
        WHERE uua.user_id = p_user_id
          AND pu.is_active = true
        ORDER BY uua.granted_at
        LIMIT 1;
    END IF;

    RETURN v_universe_id;
END;
$$ LANGUAGE plpgsql;

-- Donner accès à tous les univers aux admins existants
INSERT INTO user_universe_access (user_id, universe_id, is_default)
SELECT
    u.id AS user_id,
    pu.id AS universe_id,
    (ROW_NUMBER() OVER (PARTITION BY u.id ORDER BY pu.name) = 1) AS is_default
FROM users u
CROSS JOIN product_universes pu
WHERE u.is_admin = true
ON CONFLICT (user_id, universe_id) DO NOTHING;

-- Commentaires
COMMENT ON TABLE user_universe_access IS 'Droits d accès des utilisateurs aux univers produits';
COMMENT ON FUNCTION get_user_allowed_universes IS 'Retourne les univers autorisés pour un utilisateur';
COMMENT ON FUNCTION get_user_default_universe IS 'Retourne l univers par défaut d un utilisateur';

-- Afficher le récapitulatif
DO $$
BEGIN
    RAISE NOTICE '============================================';
    RAISE NOTICE ' User Universe Access - Migration Complete';
    RAISE NOTICE '============================================';
    RAISE NOTICE 'Table user_universe_access created';
    RAISE NOTICE 'View user_universes_view created';
    RAISE NOTICE 'Functions get_user_allowed_universes, get_user_default_universe created';
    RAISE NOTICE 'Admin users granted access to all universes';
    RAISE NOTICE '============================================';
END $$;
