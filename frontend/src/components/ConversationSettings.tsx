import { useState, useEffect } from 'react';
import { X, Archive, Trash2, AlertTriangle } from 'lucide-react';
import type { ConversationPreferences, ConversationPreferencesUpdate, ConversationStats } from '../types';
import api from '../api/client';

interface ConversationSettingsProps {
  isOpen: boolean;
  onClose: () => void;
  onBulkArchive: (olderThanDays: number) => Promise<void>;
  onBulkDelete: (archived: boolean) => Promise<void>;
}

export default function ConversationSettings({
  isOpen,
  onClose,
  onBulkArchive,
  onBulkDelete,
}: ConversationSettingsProps) {
  const [preferences, setPreferences] = useState<ConversationPreferences | null>(null);
  const [stats, setStats] = useState<ConversationStats | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  // Load preferences and stats
  useEffect(() => {
    if (isOpen) {
      loadData();
    }
  }, [isOpen]);

  const loadData = async () => {
    setIsLoading(true);
    try {
      const [prefs, statsData] = await Promise.all([
        api.getConversationPreferences(),
        api.getConversationStats(),
      ]);
      setPreferences(prefs);
      setStats(statsData);
    } catch (error) {
      console.error('Failed to load settings:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleUpdatePreferences = async (updates: ConversationPreferencesUpdate) => {
    if (!preferences) return;

    setIsSaving(true);
    try {
      const updated = await api.updateConversationPreferences(updates);
      setPreferences(updated);
    } catch (error) {
      console.error('Failed to update preferences:', error);
    } finally {
      setIsSaving(false);
    }
  };

  const handleBulkArchive = async () => {
    await onBulkArchive(30);
    await loadData();
  };

  const handleBulkDelete = async () => {
    await onBulkDelete(true);
    setShowDeleteConfirm(false);
    await loadData();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="fixed right-0 top-0 h-full w-80 bg-gray-900 text-white shadow-xl z-50 overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-700">
          <h2 className="text-lg font-semibold">Paramètres conversations</h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-800 rounded-lg transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin w-6 h-6 border-2 border-gray-500 border-t-white rounded-full" />
          </div>
        ) : (
          <div className="p-4 space-y-6">
            {/* Stats */}
            {stats && (
              <div className="bg-gray-800 rounded-lg p-4">
                <h3 className="text-sm font-medium text-gray-300 mb-3">Statistiques</h3>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <span className="text-gray-400">Actives</span>
                    <div className="font-medium">{stats.active_count}</div>
                  </div>
                  <div>
                    <span className="text-gray-400">Archivées</span>
                    <div className="font-medium">{stats.archived_count}</div>
                  </div>
                  <div className="col-span-2">
                    <span className="text-gray-400">Total</span>
                    <div className="font-medium">{stats.total_count}</div>
                  </div>
                </div>
              </div>
            )}

            {/* Auto-archive settings */}
            <div>
              <h3 className="text-sm font-medium text-gray-300 mb-3">
                Archivage automatique
              </h3>
              <p className="text-xs text-gray-500 mb-3">
                Archiver automatiquement les conversations inactives après :
              </p>
              <select
                value={preferences?.auto_archive_days || ''}
                onChange={(e) =>
                  handleUpdatePreferences({
                    auto_archive_days: e.target.value ? parseInt(e.target.value) : null,
                  })
                }
                disabled={isSaving}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
              >
                <option value="">Jamais</option>
                <option value="7">7 jours</option>
                <option value="14">14 jours</option>
                <option value="30">30 jours</option>
                <option value="60">60 jours</option>
                <option value="90">90 jours</option>
              </select>
            </div>

            {/* Auto-delete settings */}
            <div>
              <h3 className="text-sm font-medium text-gray-300 mb-3">
                Suppression automatique
              </h3>
              <p className="text-xs text-gray-500 mb-3">
                Supprimer automatiquement les conversations après :
              </p>
              <select
                value={preferences?.retention_days || ''}
                onChange={(e) =>
                  handleUpdatePreferences({
                    retention_days: e.target.value ? parseInt(e.target.value) : null,
                  })
                }
                disabled={isSaving}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500 mb-3"
              >
                <option value="">Jamais</option>
                <option value="30">30 jours</option>
                <option value="60">60 jours</option>
                <option value="90">90 jours</option>
                <option value="180">180 jours</option>
                <option value="365">1 an</option>
              </select>

              <p className="text-xs text-gray-500 mb-2">Appliquer à :</p>
              <div className="space-y-2">
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input
                    type="radio"
                    name="retention_target"
                    checked={preferences?.retention_target === 'archived'}
                    onChange={() =>
                      handleUpdatePreferences({ retention_target: 'archived' })
                    }
                    disabled={isSaving}
                    className="w-4 h-4 text-blue-600"
                  />
                  <span className="text-gray-300">Conversations archivées uniquement</span>
                </label>
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input
                    type="radio"
                    name="retention_target"
                    checked={preferences?.retention_target === 'all'}
                    onChange={() =>
                      handleUpdatePreferences({ retention_target: 'all' })
                    }
                    disabled={isSaving}
                    className="w-4 h-4 text-blue-600"
                  />
                  <span className="text-gray-300">Toutes les conversations</span>
                </label>
              </div>
            </div>

            {/* Bulk actions */}
            <div className="border-t border-gray-700 pt-6">
              <h3 className="text-sm font-medium text-gray-300 mb-3">
                Actions en masse
              </h3>

              <div className="space-y-3">
                <button
                  onClick={handleBulkArchive}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-amber-600/20 hover:bg-amber-600/30 text-amber-400 rounded-lg transition-colors text-sm"
                >
                  <Archive size={16} />
                  Archiver tout {">"} 30 jours
                </button>

                {showDeleteConfirm ? (
                  <div className="bg-red-900/20 border border-red-900 rounded-lg p-3">
                    <div className="flex items-center gap-2 text-red-400 text-sm mb-2">
                      <AlertTriangle size={16} />
                      Confirmer la suppression ?
                    </div>
                    <p className="text-xs text-gray-400 mb-3">
                      Cette action supprimera définitivement toutes les conversations archivées.
                    </p>
                    <div className="flex gap-2">
                      <button
                        onClick={handleBulkDelete}
                        className="flex-1 px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white text-sm rounded transition-colors"
                      >
                        Supprimer
                      </button>
                      <button
                        onClick={() => setShowDeleteConfirm(false)}
                        className="flex-1 px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-white text-sm rounded transition-colors"
                      >
                        Annuler
                      </button>
                    </div>
                  </div>
                ) : (
                  <button
                    onClick={() => setShowDeleteConfirm(true)}
                    disabled={!stats || stats.archived_count === 0}
                    className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-red-600/20 hover:bg-red-600/30 text-red-400 rounded-lg transition-colors text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <Trash2 size={16} />
                    Supprimer toutes les archives ({stats?.archived_count || 0})
                  </button>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
