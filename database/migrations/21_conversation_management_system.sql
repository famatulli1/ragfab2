-- ============================================================
-- CONVERSATION MANAGEMENT SYSTEM
-- Organisation par univers, archivage, suppression auto, recherche
-- Migration: 21_conversation_management_system.sql
-- ============================================================

-- ============================================================
-- 1. AJOUT UNIVERSE_ID SUR CONVERSATIONS
-- ============================================================

ALTER TABLE conversations
ADD COLUMN IF NOT EXISTS universe_id UUID REFERENCES product_universes(id) ON DELETE SET NULL;

-- Index pour filtrage par univers
CREATE INDEX IF NOT EXISTS idx_conversations_universe ON conversations(universe_id);

-- Index composite pour requêtes user + universe (conversations actives)
CREATE INDEX IF NOT EXISTS idx_conversations_user_universe
ON conversations(user_id, universe_id) WHERE archived = false;

-- ============================================================
-- 2. TABLE USER_PREFERENCES
-- ============================================================

CREATE TABLE IF NOT EXISTS user_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,

    -- Paramètres de rétention
    retention_days INTEGER DEFAULT NULL,              -- Suppression après X jours (NULL = jamais)
    retention_target VARCHAR(20) DEFAULT 'archived',  -- 'archived' ou 'all'
    auto_archive_days INTEGER DEFAULT NULL,           -- Archivage auto après X jours d'inactivité

    -- Préférences de vue
    default_view VARCHAR(20) DEFAULT 'all',           -- 'all', 'universes', 'archive'
    conversations_per_page INTEGER DEFAULT 20,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index pour lookup rapide
CREATE INDEX IF NOT EXISTS idx_user_preferences_user ON user_preferences(user_id);

-- Trigger pour auto-update de updated_at
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'trigger_user_preferences_updated_at'
    ) THEN
        CREATE TRIGGER trigger_user_preferences_updated_at
            BEFORE UPDATE ON user_preferences
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    END IF;
END $$;

-- Créer préférences par défaut pour utilisateurs existants
INSERT INTO user_preferences (user_id)
SELECT id FROM users
WHERE id NOT IN (SELECT user_id FROM user_preferences)
ON CONFLICT (user_id) DO NOTHING;

-- ============================================================
-- 3. FULL-TEXT SEARCH (FRENCH)
-- ============================================================

-- TSVector sur conversations.title
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS title_tsv tsvector;

-- Peupler les données existantes
UPDATE conversations
SET title_tsv = to_tsvector('french', COALESCE(title, ''))
WHERE title_tsv IS NULL;

-- Index GIN pour recherche rapide
CREATE INDEX IF NOT EXISTS idx_conversations_title_tsv
ON conversations USING gin(title_tsv);

-- Trigger auto-update pour title
CREATE OR REPLACE FUNCTION conversations_title_tsvector_update()
RETURNS TRIGGER AS $$
BEGIN
    NEW.title_tsv := to_tsvector('french', COALESCE(NEW.title, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tsvector_title_update ON conversations;
CREATE TRIGGER tsvector_title_update
    BEFORE INSERT OR UPDATE OF title ON conversations
    FOR EACH ROW
    EXECUTE FUNCTION conversations_title_tsvector_update();

-- TSVector sur messages.content
ALTER TABLE messages ADD COLUMN IF NOT EXISTS content_tsv tsvector;

-- Peupler les données existantes
UPDATE messages
SET content_tsv = to_tsvector('french', COALESCE(content, ''))
WHERE content_tsv IS NULL;

-- Index GIN pour recherche dans messages
CREATE INDEX IF NOT EXISTS idx_messages_content_tsv
ON messages USING gin(content_tsv);

-- Trigger auto-update pour content
CREATE OR REPLACE FUNCTION messages_content_tsvector_update()
RETURNS TRIGGER AS $$
BEGIN
    NEW.content_tsv := to_tsvector('french', COALESCE(NEW.content, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tsvector_content_update ON messages;
CREATE TRIGGER tsvector_content_update
    BEFORE INSERT OR UPDATE OF content ON messages
    FOR EACH ROW
    EXECUTE FUNCTION messages_content_tsvector_update();

-- ============================================================
-- 4. FONCTION DE RECHERCHE COMBINEE
-- ============================================================

CREATE OR REPLACE FUNCTION search_conversations(
    p_user_id UUID,
    p_query TEXT,
    p_universe_id UUID DEFAULT NULL,
    p_include_archived BOOLEAN DEFAULT FALSE,
    p_search_messages BOOLEAN DEFAULT TRUE,
    p_limit INTEGER DEFAULT 20,
    p_offset INTEGER DEFAULT 0
)
RETURNS TABLE (
    conversation_id UUID,
    title VARCHAR,
    universe_id UUID,
    universe_name VARCHAR,
    universe_color VARCHAR,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    message_count INTEGER,
    archived BOOLEAN,
    match_type VARCHAR,
    rank REAL
) AS $$
DECLARE
    v_tsquery tsquery;
BEGIN
    -- Convertir la requête en tsquery
    v_tsquery := plainto_tsquery('french', p_query);

    RETURN QUERY
    WITH title_matches AS (
        -- Recherche dans les titres
        SELECT
            c.id,
            c.title,
            c.universe_id,
            pu.name as universe_name,
            pu.color as universe_color,
            c.created_at,
            c.updated_at,
            c.message_count,
            c.archived,
            'title'::VARCHAR as match_type,
            ts_rank(c.title_tsv, v_tsquery) as rank
        FROM conversations c
        LEFT JOIN product_universes pu ON c.universe_id = pu.id
        WHERE c.user_id = p_user_id
          AND (p_include_archived OR c.archived = false)
          AND (p_universe_id IS NULL OR c.universe_id = p_universe_id)
          AND (c.title_tsv @@ v_tsquery OR c.title ILIKE '%' || p_query || '%')
    ),
    message_matches AS (
        -- Recherche dans les messages
        SELECT DISTINCT ON (c.id)
            c.id,
            c.title,
            c.universe_id,
            pu.name as universe_name,
            pu.color as universe_color,
            c.created_at,
            c.updated_at,
            c.message_count,
            c.archived,
            'message'::VARCHAR as match_type,
            ts_rank(m.content_tsv, v_tsquery) as rank
        FROM conversations c
        LEFT JOIN product_universes pu ON c.universe_id = pu.id
        JOIN messages m ON c.id = m.conversation_id
        WHERE c.user_id = p_user_id
          AND (p_include_archived OR c.archived = false)
          AND (p_universe_id IS NULL OR c.universe_id = p_universe_id)
          AND p_search_messages = true
          AND (m.content_tsv @@ v_tsquery OR m.content ILIKE '%' || p_query || '%')
        ORDER BY c.id, ts_rank(m.content_tsv, v_tsquery) DESC
    ),
    combined AS (
        SELECT * FROM title_matches
        UNION ALL
        SELECT * FROM message_matches
    ),
    deduplicated AS (
        SELECT
            combined.id,
            combined.title,
            combined.universe_id,
            combined.universe_name,
            combined.universe_color,
            combined.created_at,
            combined.updated_at,
            combined.message_count,
            combined.archived,
            (CASE
                WHEN COUNT(DISTINCT combined.match_type) > 1 THEN 'both'
                ELSE MAX(combined.match_type)
            END)::VARCHAR as match_type,
            MAX(combined.rank) as rank
        FROM combined
        GROUP BY combined.id, combined.title, combined.universe_id, combined.universe_name, combined.universe_color,
                 combined.created_at, combined.updated_at, combined.message_count, combined.archived
    )
    SELECT
        d.id,
        d.title,
        d.universe_id,
        d.universe_name,
        d.universe_color,
        d.created_at,
        d.updated_at,
        d.message_count,
        d.archived,
        d.match_type,
        d.rank
    FROM deduplicated d
    ORDER BY d.rank DESC, d.updated_at DESC
    LIMIT p_limit OFFSET p_offset;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION search_conversations IS 'Recherche full-text dans les titres et contenus des messages';

-- ============================================================
-- 5. FONCTIONS DE GESTION DES LIMITES ET RETENTION
-- ============================================================

-- Fonction pour appliquer la limite de 50 conversations actives
CREATE OR REPLACE FUNCTION enforce_conversation_limit(p_user_id UUID)
RETURNS INTEGER AS $$
DECLARE
    v_active_count INTEGER;
    v_archived INTEGER := 0;
    v_limit INTEGER := 50;
BEGIN
    -- Compter les conversations actives
    SELECT COUNT(*) INTO v_active_count
    FROM conversations
    WHERE user_id = p_user_id AND archived = false;

    -- Archiver les plus anciennes si > limite
    IF v_active_count > v_limit THEN
        WITH to_archive AS (
            SELECT id FROM conversations
            WHERE user_id = p_user_id AND archived = false
            ORDER BY updated_at ASC
            LIMIT (v_active_count - v_limit)
        )
        UPDATE conversations
        SET archived = true
        WHERE id IN (SELECT id FROM to_archive);

        GET DIAGNOSTICS v_archived = ROW_COUNT;
    END IF;

    RETURN v_archived;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION enforce_conversation_limit IS 'Archive automatiquement les conversations les plus anciennes si > 50 actives';

-- Fonction pour appliquer la politique de rétention utilisateur
CREATE OR REPLACE FUNCTION apply_user_retention_policy(p_user_id UUID)
RETURNS TABLE (archived_count INTEGER, deleted_count INTEGER) AS $$
DECLARE
    v_prefs RECORD;
    v_archived INTEGER := 0;
    v_deleted INTEGER := 0;
BEGIN
    -- Récupérer les préférences utilisateur
    SELECT * INTO v_prefs FROM user_preferences WHERE user_id = p_user_id;

    -- Si pas de préférences, les créer avec valeurs par défaut
    IF v_prefs IS NULL THEN
        INSERT INTO user_preferences (user_id) VALUES (p_user_id);
        RETURN QUERY SELECT 0, 0;
        RETURN;
    END IF;

    -- Auto-archivage des conversations inactives
    IF v_prefs.auto_archive_days IS NOT NULL THEN
        WITH archived AS (
            UPDATE conversations
            SET archived = true
            WHERE user_id = p_user_id
              AND archived = false
              AND updated_at < NOW() - (v_prefs.auto_archive_days || ' days')::INTERVAL
            RETURNING id
        )
        SELECT COUNT(*) INTO v_archived FROM archived;
    END IF;

    -- Suppression selon la politique
    IF v_prefs.retention_days IS NOT NULL THEN
        WITH deleted AS (
            DELETE FROM conversations
            WHERE user_id = p_user_id
              AND (v_prefs.retention_target = 'all' OR archived = true)
              AND updated_at < NOW() - (v_prefs.retention_days || ' days')::INTERVAL
            RETURNING id
        )
        SELECT COUNT(*) INTO v_deleted FROM deleted;
    END IF;

    RETURN QUERY SELECT v_archived, v_deleted;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION apply_user_retention_policy IS 'Applique la politique de rétention configurée par l''utilisateur';

-- Fonction pour obtenir les stats de conversations
CREATE OR REPLACE FUNCTION get_user_conversation_stats(p_user_id UUID)
RETURNS TABLE (
    active_count INTEGER,
    archived_count INTEGER,
    total_count INTEGER,
    warning_level VARCHAR,
    oldest_active_date TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*) FILTER (WHERE NOT c.archived)::INTEGER,
        COUNT(*) FILTER (WHERE c.archived)::INTEGER,
        COUNT(*)::INTEGER,
        CASE
            WHEN COUNT(*) FILTER (WHERE NOT c.archived) >= 50 THEN 'exceeded'
            WHEN COUNT(*) FILTER (WHERE NOT c.archived) >= 40 THEN 'approaching'
            ELSE 'none'
        END::VARCHAR,
        MIN(c.updated_at) FILTER (WHERE NOT c.archived)
    FROM conversations c
    WHERE c.user_id = p_user_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_user_conversation_stats IS 'Retourne les statistiques de conversations avec niveau d''alerte';

-- ============================================================
-- 6. VUE MISE A JOUR AVEC INFOS UNIVERS
-- ============================================================

CREATE OR REPLACE VIEW conversation_stats AS
SELECT
    c.id,
    c.user_id,
    c.title,
    c.provider,
    c.use_tools,
    c.reranking_enabled,
    c.hybrid_search_enabled,
    c.hybrid_search_alpha,
    c.created_at,
    c.updated_at,
    c.message_count,
    c.archived,
    c.universe_id,
    pu.name AS universe_name,
    pu.slug AS universe_slug,
    pu.color AS universe_color,
    COUNT(DISTINCT mr.id) FILTER (WHERE mr.rating = 1) AS thumbs_up_count,
    COUNT(DISTINCT mr.id) FILTER (WHERE mr.rating = -1) AS thumbs_down_count
FROM conversations c
LEFT JOIN product_universes pu ON c.universe_id = pu.id
LEFT JOIN messages m ON c.id = m.conversation_id
LEFT JOIN message_ratings mr ON m.id = mr.message_id
GROUP BY c.id, c.user_id, c.title, c.provider, c.use_tools, c.reranking_enabled,
         c.hybrid_search_enabled, c.hybrid_search_alpha, c.created_at, c.updated_at,
         c.message_count, c.archived, c.universe_id, pu.name, pu.slug, pu.color;

COMMENT ON VIEW conversation_stats IS 'Vue conversations avec statistiques de qualité et infos univers';
