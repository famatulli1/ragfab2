import { useState, useEffect } from 'react';
import { Check, X, Eye, Edit2, Trash2, Clock, CheckCircle, XCircle } from 'lucide-react';
import type { SharedFavorite, FavoriteValidation } from '../types';
import api from '../api/client';

type FilterStatus = 'all' | 'pending' | 'published' | 'rejected';

interface EditingFavorite {
  id: string;
  title: string;
  question: string;
  response: string;
  admin_notes: string;
}

export default function FavoritesValidationPanel() {
  const [favorites, setFavorites] = useState<SharedFavorite[]>([]);
  const [filterStatus, setFilterStatus] = useState<FilterStatus>('pending');
  const [isLoading, setIsLoading] = useState(true);
  const [selectedFavorite, setSelectedFavorite] = useState<SharedFavorite | null>(null);
  const [editingFavorite, setEditingFavorite] = useState<EditingFavorite | null>(null);
  const [rejectionReason, setRejectionReason] = useState('');
  const [showRejectionModal, setShowRejectionModal] = useState(false);
  const [pendingRejectId, setPendingRejectId] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const pageSize = 20;

  useEffect(() => {
    loadFavorites();
  }, [filterStatus, page]);

  const loadFavorites = async () => {
    setIsLoading(true);
    try {
      if (filterStatus === 'pending') {
        const response = await api.getPendingFavorites({ page, page_size: pageSize });
        setFavorites(response.favorites);
        setTotal(response.total);
      } else {
        const response = await api.getFavorites({
          page,
          page_size: pageSize,
          // For 'all', we'll need to fetch both published and handle filtering client-side
          // In a real implementation, the API should support status filtering
        });
        // Filter client-side for now (published only from getFavorites)
        if (filterStatus === 'published') {
          setFavorites(response.favorites);
          setTotal(response.total);
        } else if (filterStatus === 'rejected') {
          // The current API doesn't return rejected favorites
          // This would need API enhancement
          setFavorites([]);
          setTotal(0);
        } else {
          setFavorites(response.favorites);
          setTotal(response.total);
        }
      }
    } catch (error) {
      console.error('Failed to load favorites:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handlePublish = async (favoriteId: string, edits?: EditingFavorite) => {
    try {
      const validation: FavoriteValidation = {
        action: 'publish',
        ...(edits && {
          published_title: edits.title,
          published_question: edits.question,
          published_response: edits.response,
        }),
      };
      await api.validateFavorite(favoriteId, validation);
      await loadFavorites();
      setSelectedFavorite(null);
      setEditingFavorite(null);
    } catch (error) {
      console.error('Failed to publish favorite:', error);
      alert('Erreur lors de la publication');
    }
  };

  const handleReject = async () => {
    if (!pendingRejectId || !rejectionReason.trim()) return;

    try {
      const validation: FavoriteValidation = {
        action: 'reject',
        rejection_reason: rejectionReason,
      };
      await api.validateFavorite(pendingRejectId, validation);
      await loadFavorites();
      setShowRejectionModal(false);
      setPendingRejectId(null);
      setRejectionReason('');
      setSelectedFavorite(null);
    } catch (error) {
      console.error('Failed to reject favorite:', error);
      alert('Erreur lors du rejet');
    }
  };

  const handleDelete = async (favoriteId: string) => {
    if (!confirm('Etes-vous sur de vouloir supprimer ce favori ?')) return;

    try {
      await api.deleteFavorite(favoriteId);
      await loadFavorites();
      setSelectedFavorite(null);
    } catch (error) {
      console.error('Failed to delete favorite:', error);
      alert('Erreur lors de la suppression');
    }
  };

  const startEditing = (favorite: SharedFavorite) => {
    setEditingFavorite({
      id: favorite.id,
      title: favorite.title,
      question: favorite.question,
      response: favorite.response,
      admin_notes: favorite.admin_notes || '',
    });
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'pending':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300 rounded-full">
            <Clock size={12} />
            En attente
          </span>
        );
      case 'published':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300 rounded-full">
            <CheckCircle size={12} />
            Publie
          </span>
        );
      case 'rejected':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300 rounded-full">
            <XCircle size={12} />
            Rejete
          </span>
        );
      default:
        return null;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header with filters */}
      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">Validation des favoris</h2>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
              Gerez les favoris proposes par les utilisateurs
            </p>
          </div>
          <div className="text-sm text-gray-500 dark:text-gray-400">
            {total} favori{total > 1 ? 's' : ''} au total
          </div>
        </div>

        {/* Filter tabs */}
        <div className="flex gap-2">
          {(['pending', 'published', 'rejected', 'all'] as FilterStatus[]).map((status) => (
            <button
              key={status}
              onClick={() => {
                setFilterStatus(status);
                setPage(1);
              }}
              className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                filterStatus === status
                  ? 'bg-blue-500 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600'
              }`}
            >
              {status === 'pending' && 'En attente'}
              {status === 'published' && 'Publies'}
              {status === 'rejected' && 'Rejetes'}
              {status === 'all' && 'Tous'}
            </button>
          ))}
        </div>
      </div>

      {/* Favorites list */}
      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin w-8 h-8 border-2 border-gray-500 border-t-white rounded-full" />
          </div>
        ) : favorites.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-gray-500 dark:text-gray-400">Aucun favori {filterStatus === 'pending' ? 'en attente' : ''}</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-200 dark:divide-gray-700">
            {favorites.map((favorite) => (
              <div key={favorite.id} className="p-4 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors">
                <div className="flex items-start gap-4">
                  {/* Star icon */}
                  <div className="flex-shrink-0">
                    <svg className="w-6 h-6 text-yellow-500" fill="currentColor" viewBox="0 0 20 20">
                      <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                    </svg>
                  </div>

                  <div className="flex-1 min-w-0">
                    {/* Title and status */}
                    <div className="flex items-center gap-2 mb-1">
                      <h3 className="text-sm font-medium text-gray-900 dark:text-white truncate">
                        {favorite.title}
                      </h3>
                      {getStatusBadge(favorite.status)}
                      {favorite.universe_name && (
                        <span
                          className="px-2 py-0.5 text-xs rounded-full"
                          style={{
                            backgroundColor: `${favorite.universe_color}20`,
                            color: favorite.universe_color,
                          }}
                        >
                          {favorite.universe_name}
                        </span>
                      )}
                    </div>

                    {/* Question preview */}
                    <p className="text-sm text-gray-500 dark:text-gray-400 line-clamp-2 mb-2">
                      {favorite.question}
                    </p>

                    {/* Metadata */}
                    <div className="flex items-center gap-4 text-xs text-gray-400">
                      <span>Propose par: {favorite.proposed_by_username || 'Inconnu'}</span>
                      <span>{new Date(favorite.created_at).toLocaleDateString('fr-FR')}</span>
                      <span>{favorite.view_count} vues</span>
                      <span>{favorite.copy_count} copies</span>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setSelectedFavorite(favorite)}
                      className="p-2 text-gray-400 hover:text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded-lg transition-colors"
                      title="Voir details"
                    >
                      <Eye size={18} />
                    </button>
                    {favorite.status === 'pending' && (
                      <>
                        <button
                          onClick={() => {
                            startEditing(favorite);
                            setSelectedFavorite(favorite);
                          }}
                          className="p-2 text-gray-400 hover:text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded-lg transition-colors"
                          title="Editer avant publication"
                        >
                          <Edit2 size={18} />
                        </button>
                        <button
                          onClick={() => handlePublish(favorite.id)}
                          className="p-2 text-gray-400 hover:text-green-500 hover:bg-green-50 dark:hover:bg-green-900/20 rounded-lg transition-colors"
                          title="Publier"
                        >
                          <Check size={18} />
                        </button>
                        <button
                          onClick={() => {
                            setPendingRejectId(favorite.id);
                            setShowRejectionModal(true);
                          }}
                          className="p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors"
                          title="Rejeter"
                        >
                          <X size={18} />
                        </button>
                      </>
                    )}
                    <button
                      onClick={() => handleDelete(favorite.id)}
                      className="p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors"
                      title="Supprimer"
                    >
                      <Trash2 size={18} />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Pagination */}
        {total > pageSize && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-gray-200 dark:border-gray-700">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 disabled:opacity-50"
            >
              Precedent
            </button>
            <span className="text-sm text-gray-500 dark:text-gray-400">
              Page {page} sur {Math.ceil(total / pageSize)}
            </span>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={page >= Math.ceil(total / pageSize)}
              className="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 disabled:opacity-50"
            >
              Suivant
            </button>
          </div>
        )}
      </div>

      {/* Detail Modal */}
      {selectedFavorite && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-xl max-w-3xl w-full max-h-[85vh] overflow-hidden flex flex-col shadow-2xl">
            {/* Header */}
            <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700 flex items-start justify-between">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                    {editingFavorite ? 'Editer le favori' : 'Detail du favori'}
                  </h2>
                  {getStatusBadge(selectedFavorite.status)}
                </div>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                  Propose par {selectedFavorite.proposed_by_username || 'Inconnu'}
                </p>
              </div>
              <button
                onClick={() => {
                  setSelectedFavorite(null);
                  setEditingFavorite(null);
                }}
                className="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
              >
                <X size={20} className="text-gray-400" />
              </button>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {editingFavorite ? (
                <>
                  {/* Editing form */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Titre
                    </label>
                    <input
                      type="text"
                      value={editingFavorite.title}
                      onChange={(e) =>
                        setEditingFavorite({ ...editingFavorite, title: e.target.value })
                      }
                      className="w-full px-3 py-2 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-900 dark:text-white"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Question
                    </label>
                    <textarea
                      value={editingFavorite.question}
                      onChange={(e) =>
                        setEditingFavorite({ ...editingFavorite, question: e.target.value })
                      }
                      rows={3}
                      className="w-full px-3 py-2 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-900 dark:text-white"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Reponse
                    </label>
                    <textarea
                      value={editingFavorite.response}
                      onChange={(e) =>
                        setEditingFavorite({ ...editingFavorite, response: e.target.value })
                      }
                      rows={10}
                      className="w-full px-3 py-2 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-900 dark:text-white font-mono text-sm"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Notes admin
                    </label>
                    <textarea
                      value={editingFavorite.admin_notes}
                      onChange={(e) =>
                        setEditingFavorite({ ...editingFavorite, admin_notes: e.target.value })
                      }
                      rows={2}
                      placeholder="Notes internes (non visibles par les utilisateurs)"
                      className="w-full px-3 py-2 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-900 dark:text-white"
                    />
                  </div>
                </>
              ) : (
                <>
                  {/* Read-only view */}
                  <div>
                    <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-2">
                      Titre
                    </h3>
                    <p className="text-gray-900 dark:text-white">{selectedFavorite.title}</p>
                  </div>

                  <div>
                    <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-2">
                      Question
                    </h3>
                    <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
                      <p className="text-gray-900 dark:text-white">{selectedFavorite.question}</p>
                    </div>
                  </div>

                  <div>
                    <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-2">
                      Reponse
                    </h3>
                    <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4 max-h-64 overflow-y-auto">
                      <p className="text-gray-900 dark:text-white whitespace-pre-wrap">
                        {selectedFavorite.response}
                      </p>
                    </div>
                  </div>

                  {selectedFavorite.sources && selectedFavorite.sources.length > 0 && (
                    <div>
                      <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-2">
                        Sources ({selectedFavorite.sources.length})
                      </h3>
                      <div className="space-y-2">
                        {selectedFavorite.sources.map((source: any, i: number) => (
                          <div
                            key={i}
                            className="bg-gray-50 dark:bg-gray-700 rounded-lg p-3 text-sm"
                          >
                            <div className="font-medium text-gray-900 dark:text-white">
                              {source.document_title || source.title}
                            </div>
                            <p className="text-gray-500 dark:text-gray-400 text-xs mt-1 line-clamp-2">
                              {source.content}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>

            {/* Footer */}
            <div className="px-6 py-4 border-t border-gray-200 dark:border-gray-700 flex justify-end gap-3">
              {selectedFavorite.status === 'pending' && (
                <>
                  {editingFavorite ? (
                    <>
                      <button
                        onClick={() => setEditingFavorite(null)}
                        className="px-4 py-2 text-sm text-gray-700 dark:text-gray-300"
                      >
                        Annuler
                      </button>
                      <button
                        onClick={() => handlePublish(selectedFavorite.id, editingFavorite)}
                        className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white text-sm font-medium rounded-lg transition-colors"
                      >
                        Publier avec modifications
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        onClick={() => startEditing(selectedFavorite)}
                        className="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg"
                      >
                        Editer
                      </button>
                      <button
                        onClick={() => {
                          setPendingRejectId(selectedFavorite.id);
                          setShowRejectionModal(true);
                        }}
                        className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-sm font-medium rounded-lg transition-colors"
                      >
                        Rejeter
                      </button>
                      <button
                        onClick={() => handlePublish(selectedFavorite.id)}
                        className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white text-sm font-medium rounded-lg transition-colors"
                      >
                        Publier
                      </button>
                    </>
                  )}
                </>
              )}
              <button
                onClick={() => {
                  setSelectedFavorite(null);
                  setEditingFavorite(null);
                }}
                className="px-4 py-2 text-sm text-gray-500 dark:text-gray-400"
              >
                Fermer
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Rejection Modal */}
      {showRejectionModal && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-xl max-w-md w-full p-6 shadow-2xl">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
              Rejeter le favori
            </h3>
            <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
              Indiquez la raison du rejet (visible par l'utilisateur)
            </p>
            <textarea
              value={rejectionReason}
              onChange={(e) => setRejectionReason(e.target.value)}
              rows={4}
              placeholder="Raison du rejet..."
              className="w-full px-3 py-2 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-900 dark:text-white mb-4"
            />
            <div className="flex justify-end gap-3">
              <button
                onClick={() => {
                  setShowRejectionModal(false);
                  setPendingRejectId(null);
                  setRejectionReason('');
                }}
                className="px-4 py-2 text-sm text-gray-700 dark:text-gray-300"
              >
                Annuler
              </button>
              <button
                onClick={handleReject}
                disabled={!rejectionReason.trim()}
                className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
              >
                Confirmer le rejet
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
