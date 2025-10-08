-- ============================================================================
-- Migration: Ajout du support toggle reranking par conversation
-- Date: 2025-01-XX
-- Description: Ajoute la colonne reranking_enabled à la table conversations
--              pour permettre l'activation/désactivation du reranking par conversation
-- ============================================================================

-- Ajouter la colonne reranking_enabled à la table conversations
-- NULL = utiliser la variable d'environnement globale RERANKER_ENABLED
-- TRUE = forcer le reranking pour cette conversation
-- FALSE = désactiver le reranking pour cette conversation
ALTER TABLE conversations
ADD COLUMN IF NOT EXISTS reranking_enabled BOOLEAN DEFAULT NULL;

-- Index pour requêtes filtrées par reranking_enabled (optionnel mais utile pour analytics)
CREATE INDEX IF NOT EXISTS idx_conversations_reranking_enabled ON conversations(reranking_enabled);

-- Commentaire pour documentation
COMMENT ON COLUMN conversations.reranking_enabled IS
'Contrôle le reranking pour cette conversation: NULL=global, TRUE=activé, FALSE=désactivé';

-- Afficher le récapitulatif
DO $$
BEGIN
    RAISE NOTICE '✅ Migration reranking terminée avec succès !';
    RAISE NOTICE '';
    RAISE NOTICE 'Modifications :';
    RAISE NOTICE '  - Colonne reranking_enabled ajoutée à conversations';
    RAISE NOTICE '  - NULL (défaut): Utilise RERANKER_ENABLED de .env';
    RAISE NOTICE '  - TRUE: Force le reranking pour cette conversation';
    RAISE NOTICE '  - FALSE: Désactive le reranking pour cette conversation';
    RAISE NOTICE '';
    RAISE NOTICE 'Usage dans le frontend :';
    RAISE NOTICE '  - Toggle button pour chaque conversation';
    RAISE NOTICE '  - Activation/désactivation en temps réel';
    RAISE NOTICE '  - Pas de redémarrage nécessaire';
END $$;
