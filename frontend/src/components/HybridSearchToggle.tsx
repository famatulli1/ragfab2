import React, { useState, useEffect } from 'react';
import { Settings, HelpCircle } from 'lucide-react';

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
 */
export const HybridSearchToggle: React.FC<HybridSearchToggleProps> = ({
  conversationId: _conversationId,
  onChange
}) => {
  const [hybridEnabled, setHybridEnabled] = useState(false);
  const [alpha, setAlpha] = useState(0.5);
  const [showSettings, setShowSettings] = useState(false);
  const [showHelp, setShowHelp] = useState(false);

  // Charger l'état depuis localStorage au montage
  useEffect(() => {
    const savedEnabled = localStorage.getItem('hybrid_search_enabled');
    const savedAlpha = localStorage.getItem('hybrid_search_alpha');

    if (savedEnabled !== null) {
      setHybridEnabled(savedEnabled === 'true');
    }

    if (savedAlpha !== null) {
      setAlpha(parseFloat(savedAlpha));
    }
  }, []);

  const handleToggle = (enabled: boolean) => {
    setHybridEnabled(enabled);
    localStorage.setItem('hybrid_search_enabled', enabled.toString());

    if (onChange) {
      onChange(enabled, alpha);
    }
  };

  const handleAlphaChange = (newAlpha: number) => {
    setAlpha(newAlpha);
    localStorage.setItem('hybrid_search_alpha', newAlpha.toString());

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
    <div className="flex flex-col gap-2">
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

      {/* Help panel */}
      {showHelp && (
        <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg text-sm space-y-2 animate-fadeIn">
          <div className="font-semibold text-blue-900 flex items-center gap-2">
            <HelpCircle size={16} />
            Qu'est-ce que la Recherche Hybride ?
          </div>
          <div className="text-blue-800 space-y-2">
            <p>
              <strong>Combine deux approches :</strong>
            </p>
            <ul className="list-disc list-inside space-y-1 ml-2">
              <li><strong>Recherche sémantique</strong> : Comprend le sens de votre question</li>
              <li><strong>Recherche par mots-clés</strong> : Trouve les termes exacts (acronymes, noms propres)</li>
            </ul>
            <p className="pt-2">
              <strong>📈 Impact :</strong> +15-25% de précision, particulièrement efficace pour :
            </p>
            <ul className="list-disc list-inside space-y-1 ml-2">
              <li>Acronymes (RTT, CDI, PeopleDoc)</li>
              <li>Noms propres et marques</li>
              <li>Phrases exactes</li>
              <li>Termes techniques spécifiques</li>
            </ul>
          </div>
        </div>
      )}

      {/* Advanced settings panel */}
      {showSettings && hybridEnabled && (
        <div className="p-4 bg-gray-50 border border-gray-200 rounded-lg animate-fadeIn space-y-4">
          <div className="text-sm font-semibold text-gray-700">
            Réglages Avancés
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
      )}

      {/* Status indicator when enabled */}
      {hybridEnabled && !showSettings && (
        <div className="flex items-center gap-2 px-3 py-2 bg-green-50 border border-green-200 rounded-lg text-xs text-green-700">
          <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
          <span>
            Recherche hybride active {getAlphaEmoji(alpha)} (α={alpha.toFixed(1)})
          </span>
        </div>
      )}
    </div>
  );
};

export default HybridSearchToggle;
