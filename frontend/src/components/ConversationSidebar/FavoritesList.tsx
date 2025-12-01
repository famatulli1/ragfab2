import { useState, useEffect, useCallback } from 'react';
import type { SharedFavorite, FavoriteListResponse, ProductUniverse } from '../../types';
import api from '../../api/client';

interface FavoritesListProps {
  universes?: ProductUniverse[];
  currentUniverseId?: string;
  searchQuery?: string;
  onSelectFavorite: (favorite: SharedFavorite) => void;
  onCopyFavorite: (favoriteId: string) => void;
}

export default function FavoritesList({
  universes = [],
  currentUniverseId,
  searchQuery,
  onSelectFavorite,
  onCopyFavorite,
}: FavoritesListProps) {
  const [favorites, setFavorites] = useState<SharedFavorite[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [total, setTotal] = useState(0);

  const loadFavorites = useCallback(async (pageNum: number, reset = false) => {
    setIsLoading(true);
    try {
      const response: FavoriteListResponse = await api.getFavorites({
        page: pageNum,
        page_size: 20,
        universe_id: currentUniverseId,
        search: searchQuery || undefined,
      });

      if (reset) {
        setFavorites(response.favorites);
      } else {
        setFavorites((prev) => [...prev, ...response.favorites]);
      }
      setTotal(response.total);
      setHasMore(pageNum < response.total_pages);
    } catch (error) {
      console.error('Failed to load favorites:', error);
    } finally {
      setIsLoading(false);
    }
  }, [currentUniverseId, searchQuery]);

  // Initial load and reload on filter changes
  useEffect(() => {
    setPage(1);
    loadFavorites(1, true);
  }, [currentUniverseId, searchQuery, loadFavorites]);

  const handleLoadMore = () => {
    if (!isLoading && hasMore) {
      const nextPage = page + 1;
      setPage(nextPage);
      loadFavorites(nextPage);
    }
  };

  const handleCopy = async (e: React.MouseEvent, favoriteId: string) => {
    e.stopPropagation();
    try {
      await onCopyFavorite(favoriteId);
    } catch (error) {
      console.error('Failed to copy favorite:', error);
    }
  };

  if (isLoading && favorites.length === 0) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="animate-spin w-5 h-5 border-2 border-gray-500 border-t-white rounded-full" />
      </div>
    );
  }

  if (favorites.length === 0) {
    return (
      <div className="text-center py-8 px-4">
        <div className="text-gray-400 text-sm">
          {searchQuery
            ? 'Aucun favori ne correspond a votre recherche'
            : 'Aucun favori partage pour le moment'}
        </div>
        <p className="text-gray-500 text-xs mt-2">
          Les favoris sont des solutions validees partagees par la communaute
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-1">
      <div className="px-2 py-1 text-xs text-gray-500">
        {total} favori{total > 1 ? 's' : ''} partage{total > 1 ? 's' : ''}
      </div>

      {favorites.map((favorite) => {
        const universe = universes.find((u) => u.id === favorite.universe_id);

        return (
          <div
            key={favorite.id}
            onClick={() => onSelectFavorite(favorite)}
            className="group px-2 py-2 mx-1 rounded-lg hover:bg-gray-800 cursor-pointer transition-colors"
          >
            <div className="flex items-start gap-2">
              {/* Star icon */}
              <svg
                className="w-4 h-4 text-yellow-500 flex-shrink-0 mt-0.5"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
              </svg>

              <div className="flex-1 min-w-0">
                {/* Title */}
                <div className="flex items-center gap-1.5">
                  {universe && (
                    <span
                      className="w-2 h-2 rounded-full flex-shrink-0"
                      style={{ backgroundColor: universe.color }}
                      title={universe.name}
                    />
                  )}
                  <span className="text-sm text-white truncate">
                    {favorite.title}
                  </span>
                </div>

                {/* Question preview */}
                <p className="text-xs text-gray-400 truncate mt-0.5">
                  {favorite.question}
                </p>

                {/* Stats */}
                <div className="flex items-center gap-3 mt-1 text-xs text-gray-500">
                  <span className="flex items-center gap-1">
                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                    </svg>
                    {favorite.view_count}
                  </span>
                  <span className="flex items-center gap-1">
                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                    </svg>
                    {favorite.copy_count}
                  </span>
                </div>
              </div>

              {/* Copy button */}
              <button
                onClick={(e) => handleCopy(e, favorite.id)}
                className="opacity-0 group-hover:opacity-100 p-1.5 hover:bg-gray-700 rounded transition-all"
                title="Copier dans mes conversations"
              >
                <svg className="w-4 h-4 text-gray-400 hover:text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
              </button>
            </div>
          </div>
        );
      })}

      {/* Load more */}
      {hasMore && (
        <button
          onClick={handleLoadMore}
          disabled={isLoading}
          className="w-full py-2 text-xs text-gray-400 hover:text-white hover:bg-gray-800 rounded transition-colors disabled:opacity-50"
        >
          {isLoading ? 'Chargement...' : 'Voir plus de favoris'}
        </button>
      )}
    </div>
  );
}
