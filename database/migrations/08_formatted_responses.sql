-- Migration 08: Formatted responses storage
-- Description: Créer table pour sauvegarder les réponses formatées par les templates ITOP
-- Date: 2025-01-25
-- Author: Claude Code

-- Créer la table formatted_responses
CREATE TABLE IF NOT EXISTS formatted_responses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    message_id UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    template_id UUID NOT NULL REFERENCES response_templates(id) ON DELETE CASCADE,
    formatted_content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Une seule version formatée par message (si on reformate, on remplace)
    CONSTRAINT unique_formatted_per_message UNIQUE (message_id)
);

-- Index pour récupération rapide par message_id
CREATE INDEX IF NOT EXISTS idx_formatted_responses_message_id
    ON formatted_responses(message_id);

-- Index pour statistiques par template
CREATE INDEX IF NOT EXISTS idx_formatted_responses_template_id
    ON formatted_responses(template_id);

-- Commentaires
COMMENT ON TABLE formatted_responses IS 'Stockage des réponses formatées par les templates ITOP';
COMMENT ON COLUMN formatted_responses.message_id IS 'Message assistant original auquel correspond cette réponse formatée';
COMMENT ON COLUMN formatted_responses.template_id IS 'Template utilisé pour générer cette réponse formatée';
COMMENT ON COLUMN formatted_responses.formatted_content IS 'Contenu formaté prêt pour ITOP';

-- Migration completed
DO $$
BEGIN
    RAISE NOTICE '✅ Migration 08 completed successfully: formatted_responses table created';
END $$;
