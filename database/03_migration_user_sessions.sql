-- ============================================================================
-- Migration: Multi-utilisateur et reranking
-- 1. Ajouter la colonne reranking_enabled si elle n'existe pas
-- 2. Assigner les conversations orphelines au premier admin
-- 3. Rendre user_id NOT NULL
-- 4. Recréer la vue conversation_stats
-- ============================================================================

-- Étape 1: Ajouter reranking_enabled si nécessaire
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'conversations' AND column_name = 'reranking_enabled'
    ) THEN
        ALTER TABLE conversations ADD COLUMN reranking_enabled BOOLEAN DEFAULT false;
        RAISE NOTICE '✅ Colonne reranking_enabled ajoutée à la table conversations';
    ELSE
        RAISE NOTICE 'ℹ️  Colonne reranking_enabled existe déjà';
    END IF;
END $$;

-- Étape 2: Assigner les conversations orphelines
DO $$
DECLARE
    first_admin_id UUID;
    affected_rows INTEGER;
BEGIN
    -- Récupérer l'ID du premier admin
    SELECT id INTO first_admin_id
    FROM users
    WHERE is_admin = true
    ORDER BY created_at
    LIMIT 1;

    -- Vérifier qu'un admin existe
    IF first_admin_id IS NULL THEN
        RAISE EXCEPTION 'Aucun utilisateur administrateur trouvé. Créez un admin avant d''exécuter cette migration.';
    END IF;

    -- Assigner les conversations orphelines au premier admin
    UPDATE conversations
    SET user_id = first_admin_id
    WHERE user_id IS NULL;

    GET DIAGNOSTICS affected_rows = ROW_COUNT;

    -- Log du résultat
    RAISE NOTICE '✅ Migration terminée : % conversations assignées à l''admin (ID: %)', affected_rows, first_admin_id;

    IF affected_rows > 0 THEN
        RAISE NOTICE '';
        RAISE NOTICE '⚠️  IMPORTANT : % conversations existantes ont été assignées au premier administrateur.', affected_rows;
        RAISE NOTICE '   Si vous souhaitez les réassigner à d''autres utilisateurs, faites-le manuellement :';
        RAISE NOTICE '   UPDATE conversations SET user_id = ''<nouveau_user_id>'' WHERE id = ''<conversation_id>'';';
        RAISE NOTICE '';
    END IF;
END $$;

-- Étape 3: Rendre user_id NOT NULL
DO $$
BEGIN
    -- Modifier la contrainte user_id pour être NOT NULL
    ALTER TABLE conversations ALTER COLUMN user_id SET NOT NULL;
    RAISE NOTICE '✅ Colonne user_id définie comme NOT NULL';
EXCEPTION
    WHEN others THEN
        RAISE NOTICE '⚠️  Impossible de définir user_id comme NOT NULL (peut-être déjà fait)';
END $$;

-- Étape 4: Recréer la vue conversation_stats avec les nouveaux champs
CREATE OR REPLACE VIEW conversation_stats AS
SELECT
    c.id,
    c.user_id,
    c.title,
    c.provider,
    c.use_tools,
    c.reranking_enabled,
    c.created_at,
    c.updated_at,
    c.message_count,
    c.archived,
    COUNT(DISTINCT m.id) AS actual_message_count,
    COUNT(DISTINCT mr.id) FILTER (WHERE mr.rating = 1) AS thumbs_up_count,
    COUNT(DISTINCT mr.id) FILTER (WHERE mr.rating = -1) AS thumbs_down_count
FROM conversations c
LEFT JOIN messages m ON c.id = m.conversation_id
LEFT JOIN message_ratings mr ON m.id = mr.message_id
GROUP BY c.id, c.user_id, c.title, c.provider, c.use_tools, c.reranking_enabled, c.created_at, c.updated_at, c.message_count, c.archived;

-- Étape 5: Vérification finale
DO $$
DECLARE
    orphan_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO orphan_count
    FROM conversations
    WHERE user_id IS NULL;

    IF orphan_count > 0 THEN
        RAISE EXCEPTION '❌ Échec de la migration : % conversations ont toujours user_id = NULL', orphan_count;
    ELSE
        RAISE NOTICE '✅ Vérification OK : Toutes les conversations ont un user_id défini.';
        RAISE NOTICE '✅ Vue conversation_stats mise à jour avec user_id et reranking_enabled';
    END IF;
END $$;
