-- Migration 16: Correction rétroactive admin_action pour thumbs down validations
-- Description: Met à jour les validations existantes avec admin_action='pending'
--              en appliquant la logique automatique basée sur classification et confiance
-- Date: 2025-11-03

-- Lecture du seuil de confiance depuis les paramètres système (par défaut 0.7)
-- Note: Le seuil est configuré via THUMBS_DOWN_CONFIDENCE_THRESHOLD dans .env

DO $$
DECLARE
    confidence_threshold FLOAT := 0.7;
    update_count INTEGER;
BEGIN
    -- Afficher le seuil utilisé
    RAISE NOTICE 'Seuil de confiance utilisé: %', confidence_threshold;

    -- Mise à jour des validations avec admin_action automatique
    -- Logique identique à ThumbsDownAnalyzer._determine_admin_action()

    WITH updates AS (
        UPDATE thumbs_down_validations
        SET admin_action = CASE
            -- Si confiance < seuil → toujours pending (révision manuelle)
            WHEN ai_confidence < confidence_threshold THEN 'pending'

            -- Si confiance >= seuil, appliquer logique par classification
            WHEN ai_classification = 'bad_question' THEN 'contact_user'
            WHEN ai_classification = 'missing_sources' THEN 'mark_for_reingestion'
            WHEN ai_classification = 'out_of_scope' THEN 'ignore'
            WHEN ai_classification = 'bad_answer' THEN 'pending'

            -- Classification inconnue → pending
            ELSE 'pending'
        END
        WHERE admin_action = 'pending'  -- Ne touche que les validations non traitées
          AND admin_override IS NULL     -- Ne touche pas les surcharges manuelles
        RETURNING id, ai_classification, ai_confidence, admin_action
    )
    SELECT COUNT(*) INTO update_count FROM updates;

    -- Afficher résumé des mises à jour
    RAISE NOTICE '✅ Migration 16 terminée: % validations mises à jour', update_count;

    -- Afficher détails par action
    RAISE NOTICE '';
    RAISE NOTICE '📊 Résumé des actions automatiques appliquées:';

    FOR update_count IN
        SELECT
            admin_action,
            COUNT(*) as count
        FROM thumbs_down_validations
        WHERE admin_override IS NULL
        GROUP BY admin_action
        ORDER BY count DESC
    LOOP
        RAISE NOTICE '   - %: % validations',
            CASE update_count.admin_action
                WHEN 'contact_user' THEN 'Contacter utilisateur'
                WHEN 'mark_for_reingestion' THEN 'Marquer pour réingestion'
                WHEN 'ignore' THEN 'Ignorer (hors périmètre)'
                WHEN 'pending' THEN 'En attente révision'
            END,
            update_count.count;
    END LOOP;

    RAISE NOTICE '';
    RAISE NOTICE '💡 Les utilisateurs avec "bad_question" devraient maintenant apparaître dans "Utilisateurs à accompagner"';
END $$;
