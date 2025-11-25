-- Migration 19: Question Quality Feedback
-- Table pour stocker le feedback et apprentissage du système de qualité des questions
-- Date: 2025-01-25

-- Table principale de feedback qualité
CREATE TABLE IF NOT EXISTS question_quality_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Question analysée
    original_question TEXT NOT NULL,
    normalized_question TEXT NOT NULL,  -- Version normalisée pour matching

    -- Scores d'analyse
    heuristic_score FLOAT,              -- Score des heuristiques (0.0-1.0)
    llm_classification VARCHAR(50),      -- Classification LLM (clear, too_vague, wrong_vocabulary, etc.)
    llm_confidence FLOAT,               -- Confiance de la classification LLM

    -- Résultats de recherche associés
    results_count INT,                  -- Nombre de résultats RAG
    max_similarity FLOAT,               -- Score de similarité max
    avg_similarity FLOAT,               -- Score de similarité moyen

    -- Lien avec message (optionnel)
    message_id UUID REFERENCES messages(id) ON DELETE SET NULL,
    conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,

    -- Feedback utilisateur
    user_rating SMALLINT,               -- -1 (thumbs down) ou 1 (thumbs up)

    -- Suivi des reformulations
    was_reformulated BOOLEAN DEFAULT false,
    reformulated_question TEXT,
    reformulation_accepted BOOLEAN,     -- L'utilisateur a-t-il accepté la suggestion?
    reformulation_improved_results BOOLEAN, -- La reformulation a-t-elle amélioré les résultats?

    -- Métadonnées d'analyse
    analysis_phase VARCHAR(20) DEFAULT 'shadow', -- shadow, soft, interactive
    analyzed_by VARCHAR(20) DEFAULT 'heuristics', -- heuristics, llm, heuristics_fallback
    detected_terms TEXT[],              -- Termes domaine détectés
    suggested_terms TEXT[],             -- Termes suggérés

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index pour recherche par question normalisée (pattern matching)
CREATE INDEX IF NOT EXISTS idx_qqf_normalized_question
ON question_quality_feedback(normalized_question);

-- Index pour filtrer par rating utilisateur
CREATE INDEX IF NOT EXISTS idx_qqf_user_rating
ON question_quality_feedback(user_rating)
WHERE user_rating IS NOT NULL;

-- Index pour filtrer par classification
CREATE INDEX IF NOT EXISTS idx_qqf_classification
ON question_quality_feedback(llm_classification);

-- Index pour analytics temporelles
CREATE INDEX IF NOT EXISTS idx_qqf_created_at
ON question_quality_feedback(created_at DESC);

-- Index pour lien avec messages
CREATE INDEX IF NOT EXISTS idx_qqf_message_id
ON question_quality_feedback(message_id)
WHERE message_id IS NOT NULL;

-- Index pour lien avec conversations
CREATE INDEX IF NOT EXISTS idx_qqf_conversation_id
ON question_quality_feedback(conversation_id)
WHERE conversation_id IS NOT NULL;

-- Index pour filtrer les reformulations
CREATE INDEX IF NOT EXISTS idx_qqf_reformulated
ON question_quality_feedback(was_reformulated)
WHERE was_reformulated = true;

-- Index composite pour analytics: classification + rating
CREATE INDEX IF NOT EXISTS idx_qqf_classification_rating
ON question_quality_feedback(llm_classification, user_rating);

-- Trigger pour updated_at
CREATE OR REPLACE FUNCTION update_qqf_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_qqf_updated_at ON question_quality_feedback;
CREATE TRIGGER trigger_qqf_updated_at
    BEFORE UPDATE ON question_quality_feedback
    FOR EACH ROW
    EXECUTE FUNCTION update_qqf_updated_at();

-- Vue pour analytics de qualité des questions
CREATE OR REPLACE VIEW v_question_quality_analytics AS
SELECT
    DATE_TRUNC('day', created_at) as day,
    llm_classification,
    analysis_phase,
    COUNT(*) as total_questions,
    AVG(heuristic_score) as avg_heuristic_score,
    AVG(llm_confidence) as avg_llm_confidence,
    SUM(CASE WHEN user_rating = 1 THEN 1 ELSE 0 END) as thumbs_up_count,
    SUM(CASE WHEN user_rating = -1 THEN 1 ELSE 0 END) as thumbs_down_count,
    SUM(CASE WHEN was_reformulated THEN 1 ELSE 0 END) as reformulation_count,
    SUM(CASE WHEN reformulation_accepted THEN 1 ELSE 0 END) as reformulation_accepted_count,
    AVG(results_count) as avg_results_count,
    AVG(max_similarity) as avg_max_similarity
FROM question_quality_feedback
GROUP BY DATE_TRUNC('day', created_at), llm_classification, analysis_phase
ORDER BY day DESC;

-- Commentaires
COMMENT ON TABLE question_quality_feedback IS 'Feedback et apprentissage du système de qualité des questions';
COMMENT ON COLUMN question_quality_feedback.normalized_question IS 'Question normalisée (lowercase, sans ponctuation) pour pattern matching';
COMMENT ON COLUMN question_quality_feedback.heuristic_score IS 'Score des heuristiques rapides (0.0-1.0)';
COMMENT ON COLUMN question_quality_feedback.llm_classification IS 'Classification: clear, too_vague, wrong_vocabulary, missing_context, out_of_scope';
COMMENT ON COLUMN question_quality_feedback.analysis_phase IS 'Phase de déploiement: shadow (logging only), soft (suggestions), interactive (modal)';
COMMENT ON COLUMN question_quality_feedback.reformulation_improved_results IS 'True si la reformulation a donné de meilleurs résultats RAG';
