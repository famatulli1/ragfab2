-- Migration 11: Hybrid Search settings par conversation
-- Date: 2025-10-31
-- Description: Chaque conversation se rappelle de ses propres paramètres Hybrid Search

ALTER TABLE conversations
ADD COLUMN IF NOT EXISTS hybrid_search_enabled BOOLEAN DEFAULT false;

ALTER TABLE conversations
ADD COLUMN IF NOT EXISTS hybrid_search_alpha FLOAT DEFAULT 0.5;

COMMENT ON COLUMN conversations.hybrid_search_enabled IS 'Recherche hybride activée pour cette conversation';
COMMENT ON COLUMN conversations.hybrid_search_alpha IS 'Paramètre alpha (0=keywords, 1=vector) pour cette conversation';

-- Valeurs par défaut pour conversations existantes
UPDATE conversations
SET hybrid_search_enabled = false,
    hybrid_search_alpha = 0.5
WHERE hybrid_search_enabled IS NULL;
