-- Migration 10: Add conversation context to template prompts
-- Description: Modifier les prompts pour synthétiser TOUTE la conversation, pas juste la réponse actuelle
-- Date: 2025-01-25
-- Author: Claude Code

-- ============================================================================
-- SECTION 1: Update Template Concis - Add conversation context
-- ============================================================================

UPDATE response_templates
SET prompt_instructions = 'Tu dois reformater la réponse suivante pour l''outil de ticketing ITOP en format CONCIS et PROFESSIONNEL.

CONTEXTE CONVERSATIONNEL COMPLET :
{conversation_context}

RÈGLES DE FORMATAGE :
- Longueur : 3 à 5 phrases maximum
- Structure :
  1. Salutation brève : "Bonjour," (sans Monsieur/Madame)
  2. Solution directe et claire synthétisant TOUTE la procédure discutée dans la conversation
  3. Étapes d''action principales (liste numérotée courte couvrant toutes les étapes)
  4. Conclusion avec signature :
     Cordialement,
     {user_first_name} {user_last_name}
     Support Numih France

- Ton : Professionnel, efficace, direct
- Style : Phrases courtes, vocabulaire simple
- IMPORTANT : Synthétiser TOUTE la procédure complète discutée dans la conversation, pas juste la dernière réponse

LANGUE : 🇫🇷 UNIQUEMENT EN FRANÇAIS - Aucune autre langue permise

RÉPONSE CONCISE FORMATÉE (synthèse de toute la conversation) :'
WHERE name = 'reponse_adherent_concise';

-- ============================================================================
-- SECTION 2: Update Template Détaillé - Add conversation context
-- ============================================================================

UPDATE response_templates
SET prompt_instructions = 'Tu dois reformater la réponse suivante pour l''outil de ticketing ITOP en format DÉTAILLÉ et PROFESSIONNEL.

CONTEXTE CONVERSATIONNEL COMPLET :
{conversation_context}

RÈGLES DE FORMATAGE :
- Structure complète :
  1. Salutation : "Bonjour," (sans Monsieur/Madame)
  2. Accusé de réception de la demande (1 phrase contextuelle)
  3. Solution détaillée avec explications synthétisant TOUTE la procédure complète discutée dans la conversation
  4. Étapes d''action complètes (liste numérotée détaillée couvrant TOUTES les étapes mentionnées dans les différents échanges)
  5. Exemples concrets si mentionnés dans la conversation (ex: requêtes SQL, commandes, etc.)
  6. Vérification de compréhension (ex: "N''hésitez pas si vous avez des questions")
  7. Formule de politesse de clôture :
     Cordialement,
     {user_first_name} {user_last_name}
     Support Numih France

- Ton : Professionnel, bienveillant, rassurant
- Style : Explications claires, vocabulaire accessible mais précis
- Inclure : Contexte, raisons, bénéfices des actions proposées
- IMPORTANT : Inclure TOUTES les informations pertinentes de la conversation pour former une procédure complète de bout en bout

LANGUE : 🇫🇷 UNIQUEMENT EN FRANÇAIS - Aucune autre langue permise

RÉPONSE DÉTAILLÉE FORMATÉE (synthèse complète de toute la conversation) :'
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
    AND prompt_instructions LIKE '%conversation_context%';

    IF updated_count = 2 THEN
        RAISE NOTICE '✅ Migration 10 completed successfully: % templates updated with conversation context', updated_count;
        RAISE NOTICE '   - Templates will now synthesize ENTIRE conversation, not just current response';
        RAISE NOTICE '   - Concis: Short synthesis of complete procedure';
        RAISE NOTICE '   - Détaillé: Detailed synthesis of complete procedure';
    ELSE
        RAISE WARNING '⚠️ Migration 10 incomplete: only % templates updated', updated_count;
    END IF;
END $$;
