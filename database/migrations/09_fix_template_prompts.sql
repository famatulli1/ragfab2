-- Migration 09: Fix template prompts - Signature and greeting
-- Description: Corriger les prompts pour utiliser "Bonjour," (sans Monsieur/Madame) et signature avec nom utilisateur
-- Date: 2025-01-25
-- Author: Claude Code

-- ============================================================================
-- SECTION 1: Update Template Concis - Add user signature
-- ============================================================================

UPDATE response_templates
SET prompt_instructions = 'Tu dois reformater la réponse suivante pour l''outil de ticketing ITOP en format CONCIS et PROFESSIONNEL.

RÈGLES DE FORMATAGE :
- Longueur : 3 à 5 phrases maximum
- Structure :
  1. Salutation brève : "Bonjour," (sans Monsieur/Madame)
  2. Solution directe et claire (1-2 phrases)
  3. Étapes d''action si nécessaire (liste numérotée courte)
  4. Conclusion avec signature :
     Cordialement,
     {user_first_name} {user_last_name}
     Support Numih France

- Ton : Professionnel, efficace, direct
- Style : Phrases courtes, vocabulaire simple
- Éviter : Explications longues, détails techniques superflus

LANGUE : 🇫🇷 UNIQUEMENT EN FRANÇAIS - Aucune autre langue permise

RÉPONSE ORIGINALE À REFORMATER :
{original_response}

RÉPONSE CONCISE FORMATÉE :'
WHERE name = 'reponse_adherent_concise';

-- ============================================================================
-- SECTION 2: Update Template Détaillé - Fix greeting and add user signature
-- ============================================================================

UPDATE response_templates
SET prompt_instructions = 'Tu dois reformater la réponse suivante pour l''outil de ticketing ITOP en format DÉTAILLÉ et PROFESSIONNEL.

RÈGLES DE FORMATAGE :
- Structure complète :
  1. Salutation : "Bonjour," (sans Monsieur/Madame)
  2. Accusé de réception du problème (1 phrase contextuelle)
  3. Solution détaillée avec explications (paragraphe structuré)
  4. Étapes d''action (liste numérotée détaillée si applicable)
  5. Vérification de compréhension (ex: "N''hésitez pas si vous avez des questions")
  6. Formule de politesse de clôture :
     Cordialement,
     {user_first_name} {user_last_name}
     Support Numih France

- Ton : Professionnel, bienveillant, rassurant
- Style : Explications claires, vocabulaire accessible mais précis
- Inclure : Contexte, raisons, bénéfices des actions proposées

LANGUE : 🇫🇷 UNIQUEMENT EN FRANÇAIS - Aucune autre langue permise

RÉPONSE ORIGINALE À REFORMATER :
{original_response}

RÉPONSE DÉTAILLÉE FORMATÉE :'
WHERE name = 'reponse_adherent_detaillee';

-- ============================================================================
-- SECTION 3: Update updated_at timestamp
-- ============================================================================

UPDATE response_templates
SET updated_at = CURRENT_TIMESTAMP
WHERE name IN ('reponse_adherent_concise', 'reponse_adherent_detaillee');

-- ============================================================================
-- SECTION 4: Validation
-- ============================================================================

DO $$
DECLARE
    updated_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO updated_count
    FROM response_templates
    WHERE name IN ('reponse_adherent_concise', 'reponse_adherent_detaillee')
    AND prompt_instructions LIKE '%{user_first_name}%'
    AND prompt_instructions LIKE '%Support Numih France%';

    IF updated_count = 2 THEN
        RAISE NOTICE '✅ Migration 09 completed successfully: % templates updated with user signature', updated_count;
        RAISE NOTICE '   - Greeting: "Bonjour," (sans Monsieur/Madame)';
        RAISE NOTICE '   - Signature: {user_first_name} {user_last_name}\n             Support Numih France';
    ELSE
        RAISE WARNING '⚠️ Migration 09 incomplete: only % templates updated', updated_count;
    END IF;
END $$;
