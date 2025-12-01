import { useState } from 'react';
import type { FavoriteSearchResult } from '../../types';

interface FavoriteSuggestionBannerProps {
  suggestions: FavoriteSearchResult[];
  onAccept: (favoriteId: string) => void;
  onDecline: () => void;
  onViewDetail: (favorite: FavoriteSearchResult) => void;
}

export default function FavoriteSuggestionBanner({
  suggestions,
  onAccept,
  onDecline,
  onViewDetail,
}: FavoriteSuggestionBannerProps) {
  const [expanded, setExpanded] = useState(false);

  if (suggestions.length === 0) {
    return null;
  }

  const topSuggestion = suggestions[0];
  const hasMore = suggestions.length > 1;

  return (
    <div className="mx-4 mb-4 bg-gradient-to-r from-indigo-950/80 to-purple-950/80 border border-indigo-500/50 rounded-xl overflow-hidden shadow-lg shadow-indigo-500/10">
      {/* Header */}
      <div className="px-4 py-3 flex items-start gap-3">
        <div className="p-2 bg-indigo-500/30 rounded-lg">
          <svg
            className="w-5 h-5 text-indigo-300"
            fill="currentColor"
            viewBox="0 0 20 20"
          >
            <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
          </svg>
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="text-sm font-semibold text-white">
              Solution similaire trouvee !
            </h3>
            <span className="text-xs bg-indigo-500/40 text-indigo-200 px-2 py-0.5 rounded-full font-medium">
              {Math.round(topSuggestion.similarity * 100)}% de correspondance
            </span>
          </div>
          <p className="text-sm text-gray-200 line-clamp-2">
            {topSuggestion.title}
          </p>
          {topSuggestion.universe_name && (
            <div className="flex items-center gap-1.5 mt-1">
              <span
                className="w-2 h-2 rounded-full"
                style={{ backgroundColor: topSuggestion.universe_color || '#6B7280' }}
              />
              <span className="text-xs text-gray-300">{topSuggestion.universe_name}</span>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            onClick={() => onViewDetail(topSuggestion)}
            className="px-3 py-1.5 text-xs text-indigo-300 hover:text-white transition-colors underline-offset-2 hover:underline"
          >
            Voir details
          </button>
          <button
            onClick={onDecline}
            className="px-3 py-1.5 text-xs text-gray-300 hover:text-white bg-gray-700/80 hover:bg-gray-600 rounded-lg transition-colors"
          >
            Non merci
          </button>
          <button
            onClick={() => onAccept(topSuggestion.id)}
            className="px-3 py-1.5 text-xs font-medium text-white bg-indigo-600 hover:bg-indigo-500 rounded-lg transition-colors"
          >
            Utiliser cette solution
          </button>
        </div>
      </div>

      {/* More suggestions */}
      {hasMore && (
        <div className="border-t border-indigo-500/30">
          <button
            onClick={() => setExpanded(!expanded)}
            className="w-full px-4 py-2 text-xs text-indigo-300 hover:text-white flex items-center gap-1 transition-colors"
          >
            <svg
              className={`w-4 h-4 transition-transform ${expanded ? 'rotate-180' : ''}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
            {expanded ? 'Masquer' : `Voir ${suggestions.length - 1} autre${suggestions.length > 2 ? 's' : ''} suggestion${suggestions.length > 2 ? 's' : ''}`}
          </button>

          {expanded && (
            <div className="px-4 pb-3 space-y-2">
              {suggestions.slice(1).map((suggestion) => (
                <div
                  key={suggestion.id}
                  className="flex items-center gap-3 p-2 bg-gray-800/50 rounded-lg hover:bg-gray-800 transition-colors"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      {suggestion.universe_color && (
                        <span
                          className="w-2 h-2 rounded-full flex-shrink-0"
                          style={{ backgroundColor: suggestion.universe_color }}
                        />
                      )}
                      <span className="text-sm text-white truncate">{suggestion.title}</span>
                      <span className="text-xs text-gray-500">
                        {Math.round(suggestion.similarity * 100)}%
                      </span>
                    </div>
                    <p className="text-xs text-gray-400 truncate mt-0.5">
                      {suggestion.question}
                    </p>
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => onViewDetail(suggestion)}
                      className="p-1.5 text-gray-400 hover:text-white transition-colors"
                      title="Voir details"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                      </svg>
                    </button>
                    <button
                      onClick={() => onAccept(suggestion.id)}
                      className="p-1.5 text-indigo-400 hover:text-indigo-300 transition-colors"
                      title="Utiliser cette solution"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
