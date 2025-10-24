-- Migration 07: Response Templates for Support Ticketing
-- Purpose: Enable agents to format RAG responses with professional templates
-- Date: 2025-01-24
-- Use case: ITOP ticketing system - generate formatted responses (concise/detailed)

-- ============================================================================
-- SECTION 1: Create Response Templates Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS response_templates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    display_name VARCHAR(200) NOT NULL,
    icon VARCHAR(10) DEFAULT '📝',
    description TEXT,
    prompt_instructions TEXT NOT NULL,
    is_active BOOLEAN DEFAULT true,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index for active templates (frequently queried)
CREATE INDEX IF NOT EXISTS idx_response_templates_active
    ON response_templates(is_active, sort_order)
    WHERE is_active = true;

-- ============================================================================
-- SECTION 2: Seed Initial Templates
-- ============================================================================

-- Template 1: Réponse adhérent concise
INSERT INTO response_templates (name, display_name, icon, description, prompt_instructions, sort_order)
VALUES (
    'reponse_adherent_concise',
    'Réponse adhérent concise',
    '📝',
    'Réponse courte et efficace pour ITOP (3-5 phrases maximum)',
    'Tu dois reformater la réponse suivante pour l''outil de ticketing ITOP en format CONCIS et PROFESSIONNEL.

RÈGLES DE FORMATAGE :
- Longueur : 3 à 5 phrases maximum
- Structure :
  1. Salutation brève (ex: "Bonjour,")
  2. Solution directe et claire (1-2 phrases)
  3. Étapes d''action si nécessaire (liste numérotée courte)
  4. Conclusion courte (ex: "Cordialement,")

- Ton : Professionnel, efficace, direct
- Style : Phrases courtes, vocabulaire simple
- Éviter : Explications longues, détails techniques superflus

LANGUE : 🇫🇷 UNIQUEMENT EN FRANÇAIS - Aucune autre langue permise

RÉPONSE ORIGINALE À REFORMATER :
{original_response}

RÉPONSE CONCISE FORMATÉE :',
    1
) ON CONFLICT (name) DO NOTHING;

-- Template 2: Réponse adhérent détaillée
INSERT INTO response_templates (name, display_name, icon, description, prompt_instructions, sort_order)
VALUES (
    'reponse_adherent_detaillee',
    'Réponse adhérent détaillée',
    '📋',
    'Réponse complète et structurée pour ITOP avec toutes les explications',
    'Tu dois reformater la réponse suivante pour l''outil de ticketing ITOP en format DÉTAILLÉ et PROFESSIONNEL.

RÈGLES DE FORMATAGE :
- Structure complète :
  1. Salutation formelle (ex: "Bonjour [Monsieur/Madame],")
  2. Accusé de réception du problème (1 phrase contextuelle)
  3. Solution détaillée avec explications (paragraphe structuré)
  4. Étapes d''action (liste numérotée détaillée si applicable)
  5. Vérification de compréhension (ex: "N''hésitez pas si vous avez des questions")
  6. Formule de politesse de clôture (ex: "Cordialement," + signature)

- Ton : Professionnel, bienveillant, rassurant
- Style : Explications claires, vocabulaire accessible mais précis
- Inclure : Contexte, raisons, bénéfices des actions proposées

LANGUE : 🇫🇷 UNIQUEMENT EN FRANÇAIS - Aucune autre langue permise

RÉPONSE ORIGINALE À REFORMATER :
{original_response}

RÉPONSE DÉTAILLÉE FORMATÉE :',
    2
) ON CONFLICT (name) DO NOTHING;

-- ============================================================================
-- SECTION 3: Trigger for updated_at
-- ============================================================================

-- Reuse existing update_updated_at_column function
CREATE TRIGGER update_response_templates_updated_at
    BEFORE UPDATE ON response_templates
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- SECTION 4: Comments and Documentation
-- ============================================================================

COMMENT ON TABLE response_templates IS 'Templates pour formatter les réponses RAG selon le contexte (tickets ITOP, emails, etc.)';
COMMENT ON COLUMN response_templates.name IS 'Identifiant unique du template (snake_case)';
COMMENT ON COLUMN response_templates.display_name IS 'Nom affiché dans l''interface utilisateur';
COMMENT ON COLUMN response_templates.icon IS 'Emoji représentant le template';
COMMENT ON COLUMN response_templates.prompt_instructions IS 'Instructions pour le LLM sur comment reformater la réponse';
COMMENT ON COLUMN response_templates.is_active IS 'Template actif et visible pour les utilisateurs';
COMMENT ON COLUMN response_templates.sort_order IS 'Ordre d''affichage dans l''interface';

-- ============================================================================
-- SECTION 5: Validation
-- ============================================================================

-- Verify migration success
DO $$
DECLARE
    template_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO template_count FROM response_templates;

    IF template_count >= 2 THEN
        RAISE NOTICE '✅ Migration 07 completed successfully: % response templates created', template_count;
    ELSE
        RAISE WARNING '⚠️ Migration 07 incomplete: only % templates created (expected 2)', template_count;
    END IF;
END $$;

-- Display created templates
DO $$
DECLARE
    template_record RECORD;
BEGIN
    RAISE NOTICE '📋 Response templates created:';
    FOR template_record IN
        SELECT display_name, icon, is_active
        FROM response_templates
        ORDER BY sort_order
    LOOP
        RAISE NOTICE '   % % (active: %)', template_record.icon, template_record.display_name, template_record.is_active;
    END LOOP;
END $$;
