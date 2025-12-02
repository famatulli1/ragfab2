import React, { useState, useEffect } from 'react';
import { Settings, X } from 'lucide-react';
import api from '../api/client';
import type { Conversation } from '../types';

interface HybridSearchToggleProps {
  conversationId?: string;
  onChange?: (enabled: boolean, alpha: number) => void;
}

/**
 * Composant Toggle pour activer/désactiver Hybrid Search (BM25 + Vector)
 * Style harmonisé avec RerankingToggle (switch iOS)
 */
export const HybridSearchToggle: React.FC<HybridSearchToggleProps> = ({
  conversationId,
  onChange
}) => {
  const [hybridEnabled, setHybridEnabled] = useState(false);
  const [alpha, setAlpha] = useState(0.5);
  const [showSettings, setShowSettings] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  // Charger l'état depuis la conversation (DB) au montage ou changement de conversation
  useEffect(() => {
    if (conversationId) {
      api.getConversation(conversationId)
        .then((conversation: Conversation) => {
          setHybridEnabled(conversation.hybrid_search_enabled || false);
          setAlpha(conversation.hybrid_search_alpha || 0.5);
        })
        .catch((err: Error) => {
          console.error('Erreur chargement settings hybrid search:', err);
        });
    }
  }, [conversationId]);

  const handleToggle = async () => {
    setIsLoading(true);
    const newEnabled = !hybridEnabled;

    try {
      setHybridEnabled(newEnabled);

      // Sauvegarder dans la DB (par conversation)
      if (conversationId) {
        await api.updateConversation(conversationId, {
          hybrid_search_enabled: newEnabled,
          hybrid_search_alpha: alpha
        });
      }

      if (onChange) {
        onChange(newEnabled, alpha);
      }
    } catch (err) {
      console.error('Erreur sauvegarde hybrid_search_enabled:', err);
      // Revert on error
      setHybridEnabled(!newEnabled);
    } finally {
      setIsLoading(false);
    }
  };

  const handleAlphaChange = async (newAlpha: number) => {
    setAlpha(newAlpha);

    // Sauvegarder dans la DB (par conversation)
    if (conversationId) {
      try {
        await api.updateConversation(conversationId, {
          hybrid_search_enabled: hybridEnabled,
          hybrid_search_alpha: newAlpha
        });
      } catch (err) {
        console.error('Erreur sauvegarde hybrid_search_alpha:', err);
      }
    }

    if (onChange) {
      onChange(hybridEnabled, newAlpha);
    }
  };

  const getAlphaDescription = (alphaValue: number): string => {
    if (alphaValue < 0.3) {
      return "Privilégie mots-clés exacts (idéal pour acronymes, noms propres)";
    } else if (alphaValue >= 0.3 && alphaValue <= 0.7) {
      return "Équilibré (recommandé pour usage général)";
    } else {
      return "Privilégie sens sémantique (idéal pour questions conceptuelles)";
    }
  };

  const getAlphaEmoji = (alphaValue: number): string => {
    if (alphaValue < 0.3) return "🔤";
    if (alphaValue >= 0.3 && alphaValue <= 0.7) return "⚖️";
    return "🧠";
  };

  return (
    <>
      <div className="flex items-center gap-2">
        {/* Switch iOS style - harmonisé avec RerankingToggle */}
        <button
          onClick={handleToggle}
          disabled={isLoading}
          className={`
            relative inline-flex h-6 w-11 items-center rounded-full
            transition-colors duration-200 ease-in-out
            focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
            ${isLoading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
            ${hybridEnabled
              ? 'bg-green-500 dark:bg-green-600'
              : 'bg-gray-300 dark:bg-gray-600'
            }
          `}
          role="switch"
          aria-checked={hybridEnabled}
          aria-label={hybridEnabled ? 'Recherche hybride activée' : 'Recherche hybride désactivée'}
        >
          <span
            className={`
              inline-block h-4 w-4 transform rounded-full bg-white
              transition-transform duration-200 ease-in-out
              ${hybridEnabled ? 'translate-x-6' : 'translate-x-1'}
            `}
          />
        </button>

        {/* Label */}
        <span
          className="text-sm font-medium text-gray-700 dark:text-gray-300 cursor-help"
          title="Combine recherche par sens et par mots-clés pour de meilleurs résultats."
        >
          Recherche Hybride
        </span>

        {/* Indicateur inline quand actif */}
        {hybridEnabled && (
          <span className="flex items-center gap-1 text-xs text-green-600 dark:text-green-400">
            {getAlphaEmoji(alpha)} (α={alpha.toFixed(1)})
          </span>
        )}

        {/* Settings icon quand actif */}
        {hybridEnabled && (
          <button
            onClick={() => setShowSettings(true)}
            className="p-1 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors"
            title="Réglages avancés"
          >
            <Settings size={16} />
          </button>
        )}
      </div>

      {/* Advanced settings panel - Modal overlay */}
      {showSettings && hybridEnabled && (
        <>
          {/* Backdrop overlay */}
          <div
            className="fixed inset-0 bg-black bg-opacity-50 z-40"
            onClick={() => setShowSettings(false)}
          />

          {/* Modal panel */}
          <div className="fixed top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-full max-w-md z-50">
            <div className="p-4 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg shadow-2xl space-y-4 max-h-[80vh] overflow-y-auto">
              <div className="flex items-center justify-between">
                <div className="text-sm font-semibold text-gray-700 dark:text-gray-200">
                  Réglages Recherche Hybride
                </div>
                <button
                  onClick={() => setShowSettings(false)}
                  className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
                  title="Fermer"
                >
                  <X size={18} />
                </button>
              </div>

              {/* Alpha slider */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <label className="text-sm text-gray-600 dark:text-gray-300">
                    Balance Vector / Mots-clés (α)
                  </label>
                  <span className="text-xs font-mono bg-gray-200 dark:bg-gray-700 px-2 py-1 rounded">
                    α = {alpha.toFixed(1)}
                  </span>
                </div>

                <div className="flex items-center gap-3">
                  <span className="text-xs text-gray-500 dark:text-gray-400 min-w-[80px] text-right">
                    🔤 Mots-clés
                  </span>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.1"
                    value={alpha}
                    onChange={(e) => handleAlphaChange(parseFloat(e.target.value))}
                    className="flex-1 h-2 bg-gray-200 dark:bg-gray-600 rounded-lg appearance-none cursor-pointer accent-blue-600"
                  />
                  <span className="text-xs text-gray-500 dark:text-gray-400 min-w-[80px]">
                    🧠 Sémantique
                  </span>
                </div>

                {/* Alpha description */}
                <div className="flex items-start gap-2 p-3 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded text-xs text-gray-600 dark:text-gray-300">
                  <span className="text-lg">{getAlphaEmoji(alpha)}</span>
                  <div>
                    <div className="font-medium text-gray-700 dark:text-gray-200 mb-1">
                      {getAlphaDescription(alpha)}
                    </div>
                    <div className="text-gray-500 dark:text-gray-400">
                      {alpha < 0.3 && (
                        <>Recommandé si vous cherchez des acronymes, codes, ou noms de produits</>
                      )}
                      {alpha >= 0.3 && alpha <= 0.7 && (
                        <>Équilibre optimal pour la plupart des questions</>
                      )}
                      {alpha > 0.7 && (
                        <>Recommandé pour les questions "Pourquoi ?", "Comment ?", "Expliquer..."</>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              {/* Examples */}
              <div className="space-y-2">
                <div className="text-xs font-medium text-gray-700 dark:text-gray-200">
                  💡 Exemples d'utilisation :
                </div>
                <div className="space-y-2 text-xs text-gray-600 dark:text-gray-300">
                  <div className="flex items-start gap-2 p-2 bg-gray-50 dark:bg-gray-700 rounded border border-gray-100 dark:border-gray-600">
                    <span className="font-mono text-blue-600 dark:text-blue-400">α=0.2</span>
                    <span>→ "procédure RTT" ou "logiciel PeopleDoc"</span>
                  </div>
                  <div className="flex items-start gap-2 p-2 bg-gray-50 dark:bg-gray-700 rounded border border-gray-100 dark:border-gray-600">
                    <span className="font-mono text-green-600 dark:text-green-400">α=0.5</span>
                    <span>→ "politique de télétravail" (usage général)</span>
                  </div>
                  <div className="flex items-start gap-2 p-2 bg-gray-50 dark:bg-gray-700 rounded border border-gray-100 dark:border-gray-600">
                    <span className="font-mono text-purple-600 dark:text-purple-400">α=0.8</span>
                    <span>→ "pourquoi favoriser le télétravail ?"</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </>
  );
};

export default HybridSearchToggle;
