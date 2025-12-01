import { useEffect, useState } from 'react';
import type { SharedFavorite, Source } from '../../types';
import api from '../../api/client';

interface FavoriteDetailModalProps {
  favorite: SharedFavorite;
  onClose: () => void;
  onCopy: (favoriteId: string) => void;
}

export default function FavoriteDetailModal({
  favorite,
  onClose,
  onCopy,
}: FavoriteDetailModalProps) {
  const [fullFavorite, setFullFavorite] = useState<SharedFavorite | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isCopying, setIsCopying] = useState(false);

  useEffect(() => {
    const loadFavorite = async () => {
      try {
        const data = await api.getFavoriteDetail(favorite.id);
        setFullFavorite(data);
      } catch (error) {
        console.error('Failed to load favorite details:', error);
        setFullFavorite(favorite);
      } finally {
        setIsLoading(false);
      }
    };
    loadFavorite();
  }, [favorite.id]);

  const handleCopy = async () => {
    setIsCopying(true);
    try {
      await onCopy(favorite.id);
      onClose();
    } catch (error) {
      console.error('Failed to copy favorite:', error);
    } finally {
      setIsCopying(false);
    }
  };

  // Close on escape
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [onClose]);

  const data = fullFavorite || favorite;
  const sources = data.sources || [];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="bg-gray-900 rounded-xl max-w-3xl w-full max-h-[85vh] overflow-hidden flex flex-col shadow-2xl">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-800 flex items-start justify-between">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <svg
                className="w-5 h-5 text-yellow-500 flex-shrink-0"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
              </svg>
              <h2 className="text-lg font-semibold text-white truncate">
                {data.title}
              </h2>
            </div>
            {data.universe_name && (
              <div className="flex items-center gap-1.5 mt-1">
                <span
                  className="w-2 h-2 rounded-full"
                  style={{ backgroundColor: data.universe_color || '#6B7280' }}
                />
                <span className="text-sm text-gray-400">{data.universe_name}</span>
              </div>
            )}
          </div>
          <button
            onClick={onClose}
            className="p-1.5 hover:bg-gray-800 rounded-lg transition-colors"
          >
            <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin w-8 h-8 border-2 border-gray-500 border-t-white rounded-full" />
            </div>
          ) : (
            <>
              {/* Question */}
              <div>
                <h3 className="text-sm font-medium text-gray-400 mb-2">Question</h3>
                <div className="bg-gray-800 rounded-lg p-4">
                  <p className="text-white">{data.question}</p>
                </div>
              </div>

              {/* Response */}
              <div>
                <h3 className="text-sm font-medium text-gray-400 mb-2">Reponse</h3>
                <div className="bg-gray-800 rounded-lg p-4 prose prose-invert prose-sm max-w-none">
                  <div className="text-gray-200 whitespace-pre-wrap">{data.response}</div>
                </div>
              </div>

              {/* Sources */}
              {sources.length > 0 && (
                <div>
                  <h3 className="text-sm font-medium text-gray-400 mb-2">
                    Sources ({sources.length})
                  </h3>
                  <div className="space-y-2">
                    {sources.map((source: Source, index: number) => (
                      <div key={index} className="bg-gray-800 rounded-lg p-3">
                        <div className="flex items-center gap-2 mb-1">
                          <svg className="w-4 h-4 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                          </svg>
                          <span className="text-sm font-medium text-white">
                            {source.document_title || source.title}
                          </span>
                          {source.similarity !== undefined && (
                            <span className="text-xs text-gray-500">
                              {Math.round(source.similarity * 100)}%
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-gray-400 line-clamp-3">
                          {source.content}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Stats */}
              <div className="flex items-center gap-6 text-sm text-gray-400 pt-2 border-t border-gray-800">
                <span className="flex items-center gap-1.5">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                  </svg>
                  {data.view_count} vue{data.view_count > 1 ? 's' : ''}
                </span>
                <span className="flex items-center gap-1.5">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                  </svg>
                  {data.copy_count} copie{data.copy_count > 1 ? 's' : ''}
                </span>
                <span className="text-gray-500">
                  Publie le {new Date(data.created_at).toLocaleDateString('fr-FR')}
                </span>
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-800 flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors"
          >
            Fermer
          </button>
          <button
            onClick={handleCopy}
            disabled={isCopying}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50 flex items-center gap-2"
          >
            {isCopying ? (
              <>
                <div className="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full" />
                Copie en cours...
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
                Copier dans mes conversations
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
