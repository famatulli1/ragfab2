-- Migration 15: Thumbs Down Validation System with AI Analysis
-- Description: Complete system for AI-powered thumbs down analysis, admin validation, and user accompaniment
-- Date: 2025-01-03

-- =====================================================
-- STEP 1: Create thumbs_down_validations table
-- =====================================================
CREATE TABLE IF NOT EXISTS thumbs_down_validations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID UNIQUE NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    rating_id UUID NOT NULL REFERENCES message_ratings(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Data for analysis
    user_question TEXT NOT NULL,
    assistant_response TEXT NOT NULL,
    sources_used JSONB,
    user_feedback TEXT,  -- Textual feedback from rating

    -- AI Classification
    ai_classification VARCHAR(50) CHECK (ai_classification IN (
        'bad_question',           -- Question mal formulée (orthographe, grammaire, ambiguïté)
        'bad_answer',             -- Réponse incorrecte/incomplète (problème RAG)
        'missing_sources',        -- Sources manquantes/non pertinentes (réingestion)
        'unrealistic_expectations' -- Attentes hors scope de la base documentaire
    )),
    ai_confidence FLOAT CHECK (ai_confidence >= 0 AND ai_confidence <= 1),
    ai_reasoning TEXT,
    suggested_reformulation TEXT,  -- Si bad_question, suggestion de reformulation
    missing_info_details TEXT,     -- Si missing_sources, précisions sur info manquante
    needs_admin_review BOOLEAN DEFAULT false,

    -- Admin Validation
    admin_override VARCHAR(50) CHECK (admin_override IN (
        'bad_question', 'bad_answer', 'missing_sources', 'unrealistic_expectations'
    )),
    admin_notes TEXT,
    admin_action VARCHAR(50) CHECK (admin_action IN (
        'contact_user',           -- Accompagner utilisateur
        'mark_for_reingestion',  -- Marquer document pour réingestion
        'ignore',                -- Thumbs down illégitime, aucune action
        'pending'                -- Pas d'action pour l'instant
    )) DEFAULT 'pending',
    validated_by UUID REFERENCES users(id),
    validated_at TIMESTAMP,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE thumbs_down_validations IS 'AI-powered analysis and admin validation of thumbs down ratings';
COMMENT ON COLUMN thumbs_down_validations.ai_classification IS 'AI classification: bad_question | bad_answer | missing_sources | unrealistic_expectations';
COMMENT ON COLUMN thumbs_down_validations.ai_confidence IS 'AI confidence score (0-1), triggers needs_admin_review if < 0.7';
COMMENT ON COLUMN thumbs_down_validations.needs_admin_review IS 'True if confidence < 0.7 or classification = unrealistic_expectations';
COMMENT ON COLUMN thumbs_down_validations.admin_action IS 'Action decided by admin after validation';

-- =====================================================
-- STEP 2: Create indexes for performance
-- =====================================================
CREATE INDEX IF NOT EXISTS idx_validations_user_id
    ON thumbs_down_validations(user_id);

CREATE INDEX IF NOT EXISTS idx_validations_message_id
    ON thumbs_down_validations(message_id);

CREATE INDEX IF NOT EXISTS idx_validations_rating_id
    ON thumbs_down_validations(rating_id);

CREATE INDEX IF NOT EXISTS idx_validations_needs_review
    ON thumbs_down_validations(needs_admin_review) WHERE needs_admin_review = true;

CREATE INDEX IF NOT EXISTS idx_validations_classification
    ON thumbs_down_validations(ai_classification);

CREATE INDEX IF NOT EXISTS idx_validations_admin_action
    ON thumbs_down_validations(admin_action);

CREATE INDEX IF NOT EXISTS idx_validations_pending_validation
    ON thumbs_down_validations(created_at DESC) WHERE validated_at IS NULL;

-- =====================================================
-- STEP 3: Create user_notifications table
-- =====================================================
CREATE TABLE IF NOT EXISTS user_notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    validation_id UUID REFERENCES thumbs_down_validations(id) ON DELETE CASCADE,
    type VARCHAR(50) CHECK (type IN ('question_improvement', 'system_update', 'quality_feedback')) NOT NULL,
    title VARCHAR(200) NOT NULL,
    message TEXT NOT NULL,
    is_read BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE user_notifications IS 'Notifications for users to improve question formulation or receive system feedback';
COMMENT ON COLUMN user_notifications.type IS 'question_improvement: Tips for better questions | system_update: General updates | quality_feedback: Response quality issues';

CREATE INDEX IF NOT EXISTS idx_user_notifications_user_id
    ON user_notifications(user_id);

CREATE INDEX IF NOT EXISTS idx_user_notifications_is_read
    ON user_notifications(user_id, is_read) WHERE is_read = false;

CREATE INDEX IF NOT EXISTS idx_user_notifications_created_at
    ON user_notifications(created_at DESC);

-- =====================================================
-- STEP 4: Create trigger function for auto-analysis
-- =====================================================
CREATE OR REPLACE FUNCTION auto_analyze_new_thumbs_down()
RETURNS TRIGGER AS $$
BEGIN
    -- Only trigger for thumbs down (rating = -1)
    IF NEW.rating = -1 THEN
        -- Send notification to background worker via pg_notify
        PERFORM pg_notify(
            'thumbs_down_created',
            json_build_object(
                'rating_id', NEW.id,
                'message_id', NEW.message_id,
                'user_id', NEW.user_id,
                'feedback', NEW.feedback,
                'created_at', NEW.created_at
            )::text
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION auto_analyze_new_thumbs_down IS 'Trigger function to notify background worker when new thumbs down is created';

-- =====================================================
-- STEP 5: Create trigger for automatic analysis
-- =====================================================
DROP TRIGGER IF EXISTS trigger_auto_analyze_thumbs_down ON message_ratings;

CREATE TRIGGER trigger_auto_analyze_thumbs_down
AFTER INSERT OR UPDATE ON message_ratings
FOR EACH ROW
WHEN (NEW.rating = -1)
EXECUTE FUNCTION auto_analyze_new_thumbs_down();

COMMENT ON TRIGGER trigger_auto_analyze_thumbs_down ON message_ratings IS 'Automatically triggers AI analysis when thumbs down is created or updated';

-- =====================================================
-- STEP 6: Create helper view for analytics
-- =====================================================
CREATE OR REPLACE VIEW thumbs_down_with_details AS
SELECT
    v.id as validation_id,
    v.message_id,
    v.rating_id,
    v.user_id,
    u.username,
    u.email,
    u.first_name,
    u.last_name,
    v.user_question,
    v.assistant_response,
    v.sources_used,
    v.user_feedback,
    v.ai_classification,
    v.ai_confidence,
    v.ai_reasoning,
    v.suggested_reformulation,
    v.missing_info_details,
    v.needs_admin_review,
    v.admin_override,
    COALESCE(v.admin_override, v.ai_classification) as final_classification,
    v.admin_notes,
    v.admin_action,
    v.validated_by,
    v.validated_at,
    v.created_at,
    c.id as conversation_id,
    c.title as conversation_title,
    validator.username as validated_by_username
FROM thumbs_down_validations v
JOIN users u ON v.user_id = u.id
JOIN messages m ON v.message_id = m.id
JOIN conversations c ON m.conversation_id = c.id
LEFT JOIN users validator ON v.validated_by = validator.id;

COMMENT ON VIEW thumbs_down_with_details IS 'Enriched view of thumbs down validations with user details and conversation context';

-- =====================================================
-- STEP 7: Create function to get users needing accompaniment
-- =====================================================
CREATE OR REPLACE FUNCTION get_users_to_accompany()
RETURNS TABLE (
    user_id UUID,
    username VARCHAR,
    email VARCHAR,
    first_name VARCHAR,
    last_name VARCHAR,
    bad_questions_count BIGINT,
    recent_questions TEXT[],
    last_bad_question_date TIMESTAMP
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        u.id as user_id,
        u.username,
        u.email,
        u.first_name,
        u.last_name,
        COUNT(v.id) as bad_questions_count,
        ARRAY_AGG(v.user_question ORDER BY v.created_at DESC) as recent_questions,
        MAX(v.created_at) as last_bad_question_date
    FROM thumbs_down_validations v
    JOIN users u ON v.user_id = u.id
    WHERE (v.admin_override = 'bad_question' OR
           (v.admin_override IS NULL AND v.ai_classification = 'bad_question'))
      AND v.admin_action = 'contact_user'
    GROUP BY u.id, u.username, u.email, u.first_name, u.last_name
    ORDER BY bad_questions_count DESC, last_bad_question_date DESC;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_users_to_accompany IS 'Returns list of users who need accompaniment for question formulation';

-- =====================================================
-- STEP 8: Create function to get documents for reingestion
-- =====================================================
CREATE OR REPLACE FUNCTION get_documents_for_reingestion()
RETURNS TABLE (
    document_id UUID,
    document_title VARCHAR,
    occurrences_count BIGINT,
    last_occurrence TIMESTAMP,
    chunk_ids UUID[],
    user_questions TEXT[]
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        d.id as document_id,
        d.title as document_title,
        COUNT(DISTINCT v.id) as occurrences_count,
        MAX(v.created_at) as last_occurrence,
        ARRAY_AGG(DISTINCT c.id) as chunk_ids,
        ARRAY_AGG(DISTINCT v.user_question) as user_questions
    FROM thumbs_down_validations v
    CROSS JOIN LATERAL jsonb_array_elements(v.sources_used) as source
    JOIN chunks c ON c.id = (source->>'chunk_id')::UUID
    JOIN documents d ON c.document_id = d.id
    WHERE (v.admin_override = 'missing_sources' OR
           (v.admin_override IS NULL AND v.ai_classification = 'missing_sources'))
      AND v.admin_action = 'mark_for_reingestion'
    GROUP BY d.id, d.title
    ORDER BY occurrences_count DESC, last_occurrence DESC;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_documents_for_reingestion IS 'Returns documents that need reingestion based on missing_sources validations';

-- =====================================================
-- VERIFICATION
-- =====================================================
DO $$
DECLARE
    v_validations_table BOOLEAN;
    v_notifications_table BOOLEAN;
    v_trigger BOOLEAN;
    v_view BOOLEAN;
BEGIN
    -- Check tables exist
    SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'thumbs_down_validations') INTO v_validations_table;
    SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'user_notifications') INTO v_notifications_table;

    -- Check trigger exists
    SELECT EXISTS (SELECT FROM pg_trigger WHERE tgname = 'trigger_auto_analyze_thumbs_down') INTO v_trigger;

    -- Check view exists
    SELECT EXISTS (SELECT FROM information_schema.views WHERE table_name = 'thumbs_down_with_details') INTO v_view;

    IF v_validations_table AND v_notifications_table AND v_trigger AND v_view THEN
        RAISE NOTICE '✅ Migration 15 completed successfully:';
        RAISE NOTICE '   - Table thumbs_down_validations created';
        RAISE NOTICE '   - Table user_notifications created';
        RAISE NOTICE '   - Trigger auto_analyze_new_thumbs_down active';
        RAISE NOTICE '   - View thumbs_down_with_details available';
        RAISE NOTICE '   - Helper functions created';
        RAISE NOTICE '   - System ready for AI analysis and admin validation';
    ELSE
        RAISE WARNING '⚠️  Migration 15 incomplete - some components missing';
        IF NOT v_validations_table THEN RAISE WARNING '   - Missing: thumbs_down_validations table'; END IF;
        IF NOT v_notifications_table THEN RAISE WARNING '   - Missing: user_notifications table'; END IF;
        IF NOT v_trigger THEN RAISE WARNING '   - Missing: trigger_auto_analyze_thumbs_down'; END IF;
        IF NOT v_view THEN RAISE WARNING '   - Missing: thumbs_down_with_details view'; END IF;
    END IF;
END $$;
