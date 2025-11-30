import React, { useState, useEffect } from 'react';
import { Settings, HelpCircle, X } from 'lucide-react';
import api from '../api/client';
import type { Conversation } from '../types';

interface HybridSearchToggleProps {
  conversationId?: string;
  onChange?: (enabled: boolean, alpha: number) => void;
}

/**
 * Composant Toggle pour activer/désactiver Hybrid Search (BM25 + Vector)
 *
 * Hybrid Search combine:
 * - Recherche sémantique (embeddings E5-Large)
 * - Recherche par mots-clés (PostgreSQL full-text BM25)
 *
 * Impact attendu: +15-25% Recall@5
 *
 * Alpha (poids de fusion):
 * - 0.0 = 100% mots-clés (BM25)
 * - 0.5 = Équilibré (recommandé)
 * - 1.0 = 100% sémantique (vector)
 *
 * Settings par conversation (nouveauté): Chaque conversation se rappelle de ses propres settings
 */
export const HybridSearchToggle: React.FC<HybridSearchToggleProps> = ({
  conversationId,
  onChange
}) => {
  const [hybridEnabled, setHybridEnabled] = useState(false);
  const [alpha, setAlpha] = useState(0.5);
  const [showSettings, setShowSettings] = useState(false);
  const [showHelp, setShowHelp] = useState(false);

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

  const handleToggle = async (enabled: boolean) => {
    setHybridEnabled(enabled);

    // Sauvegarder dans la DB (par conversation)
    if (conversationId) {
      try {
        await api.updateConversation(conversationId, {
          hybrid_search_enabled: enabled,
          hybrid_search_alpha: alpha
        });
      } catch (err) {
        console.error('Erreur sauvegarde hybrid_search_enabled:', err);
      }
    }

    if (onChange) {
      onChange(enabled, alpha);
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
    <div className="relative flex flex-col gap-2">
      {/* Toggle principal */}
      <div className="flex items-center justify-between gap-4 p-3 bg-white border border-gray-200 rounded-lg shadow-sm">
        <div className="flex items-center gap-3">
          <input
            type="checkbox"
            id="hybrid-toggle"
            checked={hybridEnabled}
            onChange={(e) => handleToggle(e.target.checked)}
            className="w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500 focus:ring-2"
          />
          <label htmlFor="hybrid-toggle" className="text-sm font-medium text-gray-700 cursor-pointer select-none">
            Recherche Hybride (Vector + Mots-clés)
          </label>
          {hybridEnabled && (
            <span className="flex items-center gap-1 text-xs text-green-600">
              <span className="w-1.5 h-1.5 bg-green-500 rounded-full"></span>
              {getAlphaEmoji(alpha)} (α={alpha.toFixed(1)})
            </span>
          )}

          {/* Help icon */}
          <button
            onClick={() => setShowHelp(!showHelp)}
            className="p-1 text-gray-400 hover:text-gray-600 transition-colors"
            title="En savoir plus"
          >
            <HelpCircle size={16} />
          </button>
        </div>

        {/* Settings button */}
        {hybridEnabled && (
          <button
            onClick={() => setShowSettings(!showSettings)}
            className="p-2 text-gray-500 hover:bg-gray-100 rounded-md transition-colors"
            title="Réglages avancés"
          >
            <Settings size={18} />
          </button>
        )}
      </div>

      {/* Help panel - Version compacte avec bouton fermer */}
      {showHelp && (
        <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg text-xs animate-fadeIn">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-start gap-2 flex-1">
              <HelpCircle size={14} className="text-blue-600 mt-0.5 flex-shrink-0" />
              <div className="text-blue-800 space-y-1">
                <p className="font-semibold text-blue-900">Recherche Hybride = Sémantique + Mots-clés</p>
                <p>
                  ✅ <strong>Activer</strong> pour termes précis (acronymes, noms propres)
                  <br />
                  ❌ <strong>Désactiver</strong> pour questions générales
                </p>
              </div>
            </div>
            {/* Bouton fermer explicite */}
            <button
              onClick={() => setShowHelp(false)}
              className="p-1 text-blue-400 hover:text-blue-600 hover:bg-blue-100 rounded transition-colors flex-shrink-0"
              title="Fermer l'aide"
            >
              <X size={14} />
            </button>
          </div>
        </div>
      )}

      {/* Advanced settings panel - Modal overlay */}
      {showSettings && hybridEnabled && (
        <>
          {/* Backdrop overlay */}
          <div
            className="fixed inset-0 bg-black bg-opacity-50 z-40 animate-fadeIn"
            onClick={() => setShowSettings(false)}
          />

          {/* Modal panel */}
          <div className="fixed top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-full max-w-md z-50 animate-fadeIn">
            <div className="p-4 bg-white border border-gray-300 rounded-lg shadow-2xl space-y-4 max-h-[80vh] overflow-y-auto">
              <div className="flex items-center justify-between">
                <div className="text-sm font-semibold text-gray-700">
                  Réglages Avancés
                </div>
                <button
                  onClick={() => setShowSettings(false)}
                  className="p-1 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded transition-colors"
                  title="Fermer"
                >
                  ✕
                </button>
              </div>

          {/* Alpha slider */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <label className="text-sm text-gray-600">
                Balance Vector / Mots-clés (α)
              </label>
              <span className="text-xs font-mono bg-gray-200 px-2 py-1 rounded">
                α = {alpha.toFixed(1)}
              </span>
            </div>

            <div className="flex items-center gap-3">
              <span className="text-xs text-gray-500 min-w-[80px] text-right">
                🔤 Mots-clés
              </span>
              <input
                type="range"
                min="0"
                max="1"
                step="0.1"
                value={alpha}
                onChange={(e) => handleAlphaChange(parseFloat(e.target.value))}
                className="flex-1 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
              />
              <span className="text-xs text-gray-500 min-w-[80px]">
                🧠 Sémantique
              </span>
            </div>

            {/* Alpha description */}
            <div className="flex items-start gap-2 p-3 bg-white border border-gray-200 rounded text-xs text-gray-600">
              <span className="text-lg">{getAlphaEmoji(alpha)}</span>
              <div>
                <div className="font-medium text-gray-700 mb-1">
                  {getAlphaDescription(alpha)}
                </div>
                <div className="text-gray-500">
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
            <div className="text-xs font-medium text-gray-700">
              💡 Exemples d'utilisation :
            </div>
            <div className="space-y-2 text-xs text-gray-600">
              <div className="flex items-start gap-2 p-2 bg-white rounded border border-gray-100">
                <span className="font-mono text-blue-600">α=0.2</span>
                <span>→ "procédure RTT" ou "logiciel PeopleDoc"</span>
              </div>
              <div className="flex items-start gap-2 p-2 bg-white rounded border border-gray-100">
                <span className="font-mono text-green-600">α=0.5</span>
                <span>→ "politique de télétravail" (usage général)</span>
              </div>
              <div className="flex items-start gap-2 p-2 bg-white rounded border border-gray-100">
                <span className="font-mono text-purple-600">α=0.8</span>
                <span>→ "pourquoi favoriser le télétravail ?"</span>
              </div>
            </div>
          </div>

          {/* Note about adaptive alpha */}
          <div className="p-3 bg-yellow-50 border border-yellow-200 rounded text-xs text-yellow-800">
            <strong>Note :</strong> Le système ajuste automatiquement α si vous ne le personnalisez pas.
            Les acronymes et noms propres sont détectés automatiquement.
          </div>
            </div>
          </div>
        </>
      )}

      </div>
  );
};

export default HybridSearchToggle;
