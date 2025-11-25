import React, { useState, useEffect } from 'react';
import {
  Globe,
  Plus,
  Edit,
  Trash2,
  Users,
  FileText,
  Save,
  X,
  AlertCircle,
  Check,
  ChevronDown,
  ChevronUp
} from 'lucide-react';
import api from '../api/client';
import type { ProductUniverse, ProductUniverseCreate, ProductUniverseUpdate, UserUniverseAccess, UserListResponse } from '../types';

interface UniverseManagementProps {
  onUniverseChange?: () => void;
}

/**
 * Composant d'administration des univers produits.
 *
 * Permet de:
 * - Creer, modifier, supprimer des univers
 * - Gerer les acces utilisateurs aux univers
 * - Voir le nombre de documents par univers
 */
export const UniverseManagement: React.FC<UniverseManagementProps> = ({ onUniverseChange }) => {
  const [universes, setUniverses] = useState<ProductUniverse[]>([]);
  const [users, setUsers] = useState<UserListResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingUniverse, setEditingUniverse] = useState<ProductUniverse | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [expandedUniverse, setExpandedUniverse] = useState<string | null>(null);
  const [universeUserAccess, setUniverseUserAccess] = useState<Record<string, UserUniverseAccess[]>>({});
  const [documentCounts, setDocumentCounts] = useState<Record<string, number>>({});

  // Form state for create/edit
  const [formData, setFormData] = useState<ProductUniverseCreate>({
    name: '',
    slug: '',
    description: '',
    detection_keywords: [],
    color: '#6366f1',
    is_active: true
  });

  const [keywordInput, setKeywordInput] = useState('');

  // Charger les univers et utilisateurs
  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);

      const [universesResponse, usersResponse] = await Promise.all([
        api.getUniverses(true),
        api.listUsers(100, 0)
      ]);

      setUniverses(universesResponse.universes);
      setUsers(usersResponse);

      // Charger les comptes de documents pour chaque univers
      const counts: Record<string, number> = {};
      for (const universe of universesResponse.universes) {
        try {
          const countResponse = await api.getUniverseDocumentCount(universe.id);
          counts[universe.id] = countResponse.document_count;
        } catch (err) {
          counts[universe.id] = 0;
        }
      }
      setDocumentCounts(counts);

    } catch (err) {
      setError('Erreur lors du chargement des donnees');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const loadUniverseUserAccess = async (universeId: string) => {
    try {
      // Charger les acces pour tous les utilisateurs
      const accessMap: UserUniverseAccess[] = [];

      for (const user of users) {
        try {
          const response = await api.getUserUniverseAccess(user.id);
          const universeAccess = response.accesses.find(a => a.universe_id === universeId);
          if (universeAccess) {
            accessMap.push({ ...universeAccess, user_id: user.id } as any);
          }
        } catch (err) {
          console.error(`Erreur chargement acces pour ${user.id}:`, err);
        }
      }

      setUniverseUserAccess(prev => ({ ...prev, [universeId]: accessMap }));
    } catch (err) {
      console.error('Erreur chargement acces univers:', err);
    }
  };

  const handleCreateUniverse = async () => {
    try {
      setError(null);
      await api.createUniverse(formData);
      setShowCreateForm(false);
      resetForm();
      await loadData();
      if (onUniverseChange) onUniverseChange();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Erreur lors de la creation');
    }
  };

  const handleUpdateUniverse = async () => {
    if (!editingUniverse) return;

    try {
      setError(null);
      const updates: ProductUniverseUpdate = {
        name: formData.name,
        description: formData.description,
        detection_keywords: formData.detection_keywords,
        color: formData.color,
        is_active: formData.is_active
      };

      await api.updateUniverse(editingUniverse.id, updates);
      setEditingUniverse(null);
      resetForm();
      await loadData();
      if (onUniverseChange) onUniverseChange();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Erreur lors de la mise a jour');
    }
  };

  const handleDeleteUniverse = async (universeId: string) => {
    if (!confirm('Etes-vous sur de vouloir supprimer cet univers ?')) {
      return;
    }

    try {
      setError(null);
      await api.deleteUniverse(universeId);
      await loadData();
      if (onUniverseChange) onUniverseChange();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Erreur lors de la suppression');
    }
  };

  const handleGrantAccess = async (userId: string, universeId: string) => {
    try {
      await api.grantUniverseAccess(userId, universeId, false);
      await loadUniverseUserAccess(universeId);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Erreur lors de l\'attribution de l\'acces');
    }
  };

  const handleRevokeAccess = async (userId: string, universeId: string) => {
    try {
      await api.revokeUniverseAccess(userId, universeId);
      await loadUniverseUserAccess(universeId);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Erreur lors de la revocation de l\'acces');
    }
  };

  const resetForm = () => {
    setFormData({
      name: '',
      slug: '',
      description: '',
      detection_keywords: [],
      color: '#6366f1',
      is_active: true
    });
    setKeywordInput('');
  };

  const startEdit = (universe: ProductUniverse) => {
    setEditingUniverse(universe);
    setFormData({
      name: universe.name,
      slug: universe.slug,
      description: universe.description || '',
      detection_keywords: universe.detection_keywords || [],
      color: universe.color,
      is_active: universe.is_active
    });
    setShowCreateForm(false);
  };

  const handleToggleExpand = async (universeId: string) => {
    if (expandedUniverse === universeId) {
      setExpandedUniverse(null);
    } else {
      setExpandedUniverse(universeId);
      if (!universeUserAccess[universeId]) {
        await loadUniverseUserAccess(universeId);
      }
    }
  };

  const addKeyword = () => {
    if (keywordInput.trim() && !formData.detection_keywords?.includes(keywordInput.trim())) {
      setFormData((prev: ProductUniverseCreate) => ({
        ...prev,
        detection_keywords: [...(prev.detection_keywords || []), keywordInput.trim()]
      }));
      setKeywordInput('');
    }
  };

  const removeKeyword = (keyword: string) => {
    setFormData((prev: ProductUniverseCreate) => ({
      ...prev,
      detection_keywords: (prev.detection_keywords || []).filter((k: string) => k !== keyword)
    }));
  };

  const generateSlug = (name: string): string => {
    return name
      .toLowerCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-|-$/g, '');
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  const colorPresets = [
    '#3b82f6', // Blue
    '#10b981', // Green
    '#f59e0b', // Amber
    '#ef4444', // Red
    '#8b5cf6', // Purple
    '#ec4899', // Pink
    '#14b8a6', // Teal
    '#f97316', // Orange
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Globe size={24} className="text-indigo-600" />
          <h2 className="text-xl font-semibold text-gray-800">Univers Produits</h2>
        </div>
        <button
          onClick={() => {
            setShowCreateForm(true);
            setEditingUniverse(null);
            resetForm();
          }}
          className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
        >
          <Plus size={18} />
          Nouvel univers
        </button>
      </div>

      {/* Error message */}
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-red-700">
          <AlertCircle size={18} />
          <span>{error}</span>
          <button onClick={() => setError(null)} className="ml-auto">
            <X size={18} />
          </button>
        </div>
      )}

      {/* Create/Edit Form */}
      {(showCreateForm || editingUniverse) && (
        <div className="p-6 bg-white border border-gray-200 rounded-lg shadow-sm space-y-4">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-medium text-gray-800">
              {editingUniverse ? 'Modifier l\'univers' : 'Creer un nouvel univers'}
            </h3>
            <button
              onClick={() => {
                setShowCreateForm(false);
                setEditingUniverse(null);
                resetForm();
              }}
              className="p-1 text-gray-400 hover:text-gray-600"
            >
              <X size={20} />
            </button>
          </div>

          <div className="grid grid-cols-2 gap-4">
            {/* Name */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Nom *</label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => {
                  setFormData((prev: ProductUniverseCreate) => ({
                    ...prev,
                    name: e.target.value,
                    slug: !editingUniverse ? generateSlug(e.target.value) : prev.slug
                  }));
                }}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                placeholder="Ex: Medimail"
              />
            </div>

            {/* Slug */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Slug *</label>
              <input
                type="text"
                value={formData.slug}
                onChange={(e) => setFormData((prev: ProductUniverseCreate) => ({ ...prev, slug: e.target.value }))}
                disabled={!!editingUniverse}
                className={`w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 ${editingUniverse ? 'bg-gray-100' : ''}`}
                placeholder="Ex: medimail"
              />
              {editingUniverse && (
                <p className="text-xs text-gray-500 mt-1">Le slug ne peut pas etre modifie</p>
              )}
            </div>
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData((prev: ProductUniverseCreate) => ({ ...prev, description: e.target.value }))}
              rows={2}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              placeholder="Description de l'univers produit..."
            />
          </div>

          {/* Color */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Couleur</label>
            <div className="flex items-center gap-4">
              <div className="flex gap-2">
                {colorPresets.map(color => (
                  <button
                    key={color}
                    onClick={() => setFormData((prev: ProductUniverseCreate) => ({ ...prev, color }))}
                    className={`w-8 h-8 rounded-full border-2 transition-all ${formData.color === color ? 'border-gray-800 scale-110' : 'border-transparent hover:scale-105'}`}
                    style={{ backgroundColor: color }}
                  />
                ))}
              </div>
              <input
                type="color"
                value={formData.color}
                onChange={(e) => setFormData((prev: ProductUniverseCreate) => ({ ...prev, color: e.target.value }))}
                className="w-10 h-10 rounded cursor-pointer"
              />
              <span className="text-sm text-gray-500 font-mono">{formData.color}</span>
            </div>
          </div>

          {/* Detection Keywords */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Mots-cles de detection</label>
            <div className="flex gap-2 mb-2">
              <input
                type="text"
                value={keywordInput}
                onChange={(e) => setKeywordInput(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), addKeyword())}
                className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                placeholder="Ajouter un mot-cle..."
              />
              <button
                onClick={addKeyword}
                className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200"
              >
                Ajouter
              </button>
            </div>
            <div className="flex flex-wrap gap-2">
              {(formData.detection_keywords || []).map((keyword: string) => (
                <span
                  key={keyword}
                  className="inline-flex items-center gap-1 px-3 py-1 bg-gray-100 text-gray-700 rounded-full text-sm"
                >
                  {keyword}
                  <button onClick={() => removeKeyword(keyword)} className="hover:text-red-500">
                    <X size={14} />
                  </button>
                </span>
              ))}
            </div>
          </div>

          {/* Active toggle */}
          <div className="flex items-center gap-3">
            <input
              type="checkbox"
              id="is_active"
              checked={formData.is_active}
              onChange={(e) => setFormData((prev: ProductUniverseCreate) => ({ ...prev, is_active: e.target.checked }))}
              className="w-4 h-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500"
            />
            <label htmlFor="is_active" className="text-sm text-gray-700">Univers actif</label>
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-3 pt-4 border-t">
            <button
              onClick={() => {
                setShowCreateForm(false);
                setEditingUniverse(null);
                resetForm();
              }}
              className="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
            >
              Annuler
            </button>
            <button
              onClick={editingUniverse ? handleUpdateUniverse : handleCreateUniverse}
              className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
            >
              <Save size={18} />
              {editingUniverse ? 'Mettre a jour' : 'Creer'}
            </button>
          </div>
        </div>
      )}

      {/* Universes List */}
      <div className="space-y-3">
        {universes.map(universe => (
          <div key={universe.id} className="bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
            {/* Universe Header */}
            <div className="p-4 flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div
                  className="w-4 h-4 rounded-full"
                  style={{ backgroundColor: universe.color }}
                />
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-medium text-gray-800">{universe.name}</h3>
                    <span className="text-xs font-mono text-gray-400">({universe.slug})</span>
                    {!universe.is_active && (
                      <span className="px-2 py-0.5 text-xs bg-gray-100 text-gray-500 rounded">Inactif</span>
                    )}
                  </div>
                  {universe.description && (
                    <p className="text-sm text-gray-500">{universe.description}</p>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-4">
                {/* Stats */}
                <div className="flex items-center gap-4 text-sm text-gray-500">
                  <span className="flex items-center gap-1">
                    <FileText size={14} />
                    {documentCounts[universe.id] || 0} docs
                  </span>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleToggleExpand(universe.id)}
                    className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded"
                    title="Gerer les acces"
                  >
                    <Users size={18} />
                  </button>
                  <button
                    onClick={() => startEdit(universe)}
                    className="p-2 text-gray-400 hover:text-indigo-600 hover:bg-indigo-50 rounded"
                    title="Modifier"
                  >
                    <Edit size={18} />
                  </button>
                  <button
                    onClick={() => handleDeleteUniverse(universe.id)}
                    className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded"
                    title="Supprimer"
                    disabled={documentCounts[universe.id] > 0}
                  >
                    <Trash2 size={18} />
                  </button>
                  <button
                    onClick={() => handleToggleExpand(universe.id)}
                    className="p-2 text-gray-400 hover:text-gray-600"
                  >
                    {expandedUniverse === universe.id ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                  </button>
                </div>
              </div>
            </div>

            {/* Expanded User Access Section */}
            {expandedUniverse === universe.id && (
              <div className="border-t border-gray-100 p-4 bg-gray-50">
                <h4 className="text-sm font-medium text-gray-700 mb-3 flex items-center gap-2">
                  <Users size={16} />
                  Acces utilisateurs
                </h4>

                <div className="space-y-2 max-h-64 overflow-y-auto">
                  {users.map(user => {
                    const hasAccess = universeUserAccess[universe.id]?.some(
                      a => (a as any).user_id === user.id
                    );

                    return (
                      <div
                        key={user.id}
                        className="flex items-center justify-between p-2 bg-white rounded border border-gray-200"
                      >
                        <div className="flex items-center gap-2">
                          <div className={`w-2 h-2 rounded-full ${user.is_active ? 'bg-green-500' : 'bg-gray-300'}`} />
                          <span className="text-sm text-gray-700">{user.username}</span>
                          {user.is_admin && (
                            <span className="px-1.5 py-0.5 text-xs bg-indigo-100 text-indigo-600 rounded">Admin</span>
                          )}
                        </div>

                        <button
                          onClick={() => hasAccess
                            ? handleRevokeAccess(user.id, universe.id)
                            : handleGrantAccess(user.id, universe.id)
                          }
                          className={`px-3 py-1 text-xs rounded transition-colors ${
                            hasAccess
                              ? 'bg-green-100 text-green-700 hover:bg-red-100 hover:text-red-700'
                              : 'bg-gray-100 text-gray-600 hover:bg-green-100 hover:text-green-700'
                          }`}
                        >
                          {hasAccess ? (
                            <span className="flex items-center gap-1">
                              <Check size={12} />
                              Acces
                            </span>
                          ) : (
                            'Donner acces'
                          )}
                        </button>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Keywords */}
            {universe.detection_keywords && universe.detection_keywords.length > 0 && (
              <div className="border-t border-gray-100 px-4 py-2 bg-gray-50">
                <div className="flex flex-wrap gap-1">
                  {universe.detection_keywords.map((keyword: string) => (
                    <span
                      key={keyword}
                      className="px-2 py-0.5 text-xs rounded-full"
                      style={{ backgroundColor: `${universe.color}20`, color: universe.color }}
                    >
                      {keyword}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}

        {universes.length === 0 && (
          <div className="text-center py-8 text-gray-500">
            <Globe size={48} className="mx-auto mb-4 text-gray-300" />
            <p>Aucun univers produit cree</p>
            <p className="text-sm">Cliquez sur "Nouvel univers" pour commencer</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default UniverseManagement;
