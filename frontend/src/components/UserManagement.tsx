import { useState, useEffect } from 'react';
import { UserPlus, Edit2, Trash2, Key, Shield, UserX, Check, X, AlertCircle, Globe } from 'lucide-react';
import { useTheme } from '../App';
import api from '../api/client';
import type { UserListResponse, UserUpdate, ProductUniverse } from '../types';

// Type pour stocker les accès univers par utilisateur
type UserUniverseMap = Record<string, string[]>; // userId -> universeIds[]

export default function UserManagement() {
  const { theme } = useTheme();
  const [users, setUsers] = useState<UserListResponse[]>([]);
  const [universes, setUniverses] = useState<ProductUniverse[]>([]);
  const [userUniverseAccess, setUserUniverseAccess] = useState<UserUniverseMap>({});
  const [loadingUniverses, setLoadingUniverses] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Modals
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [showResetPasswordModal, setShowResetPasswordModal] = useState(false);
  const [selectedUser, setSelectedUser] = useState<UserListResponse | null>(null);

  // Filtres
  const [filterActive, setFilterActive] = useState<boolean | undefined>(undefined);
  const [filterAdmin, setFilterAdmin] = useState<boolean | undefined>(undefined);

  // Form data
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    first_name: '',
    last_name: '',
    password: '',
    is_admin: false,
    is_active: true,
  });
  const [newPassword, setNewPassword] = useState('');

  useEffect(() => {
    loadUsers();
    loadUniverses();
  }, [filterActive, filterAdmin]);

  const loadUniverses = async () => {
    try {
      const response = await api.getUniverses(true);
      setUniverses(response.universes.filter((u: ProductUniverse) => u.is_active));
    } catch (err) {
      console.error('Error loading universes:', err);
    }
  };

  const loadUsers = async () => {
    try {
      setLoading(true);
      const data = await api.listUsers(100, 0, filterActive, filterAdmin);
      setUsers(data);

      // Load universe access for all users
      const accessMap: UserUniverseMap = {};
      for (const user of data) {
        try {
          const accessResponse = await api.getUserUniverseAccess(user.id);
          accessMap[user.id] = accessResponse.accesses.map((a: { universe_id: string }) => a.universe_id);
        } catch (err) {
          accessMap[user.id] = [];
        }
      }
      setUserUniverseAccess(accessMap);

      setError('');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Erreur lors du chargement des utilisateurs');
    } finally {
      setLoading(false);
    }
  };

  const toggleUniverseAccess = async (userId: string, universeId: string, hasAccess: boolean) => {
    setLoadingUniverses(prev => ({ ...prev, [`${userId}-${universeId}`]: true }));

    try {
      if (hasAccess) {
        await api.revokeUniverseAccess(userId, universeId);
        setUserUniverseAccess(prev => ({
          ...prev,
          [userId]: (prev[userId] || []).filter(id => id !== universeId)
        }));
      } else {
        await api.grantUniverseAccess(userId, universeId, false);
        setUserUniverseAccess(prev => ({
          ...prev,
          [userId]: [...(prev[userId] || []), universeId]
        }));
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Erreur lors de la modification des accès');
    } finally {
      setLoadingUniverses(prev => ({ ...prev, [`${userId}-${universeId}`]: false }));
    }
  };

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.createUser(formData);
      setShowCreateModal(false);
      setFormData({ username: '', email: '', first_name: '', last_name: '', password: '', is_admin: false, is_active: true });
      loadUsers();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Erreur lors de la création');
    }
  };

  const handleUpdateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedUser) return;

    try {
      const updates: UserUpdate = {
        email: formData.email || undefined,
        first_name: formData.first_name || undefined,
        last_name: formData.last_name || undefined,
        is_active: formData.is_active,
        is_admin: formData.is_admin,
      };
      await api.updateUser(selectedUser.id, updates);
      setShowEditModal(false);
      setSelectedUser(null);
      loadUsers();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Erreur lors de la modification');
    }
  };

  const handleDeleteUser = async () => {
    if (!selectedUser) return;

    try {
      await api.deleteUser(selectedUser.id);
      setShowDeleteModal(false);
      setSelectedUser(null);
      loadUsers();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Erreur lors de la suppression');
    }
  };

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedUser || !newPassword) return;

    try {
      await api.resetUserPassword(selectedUser.id, newPassword);
      setShowResetPasswordModal(false);
      setSelectedUser(null);
      setNewPassword('');
      alert('Mot de passe réinitialisé avec succès');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Erreur lors de la réinitialisation');
    }
  };

  const openEditModal = (user: UserListResponse) => {
    setSelectedUser(user);
    setFormData({
      username: user.username,
      email: user.email || '',
      first_name: user.first_name || '',
      last_name: user.last_name || '',
      password: '',
      is_admin: user.is_admin,
      is_active: user.is_active,
    });
    setShowEditModal(true);
  };

  const openDeleteModal = (user: UserListResponse) => {
    setSelectedUser(user);
    setShowDeleteModal(true);
  };

  const openResetPasswordModal = (user: UserListResponse) => {
    setSelectedUser(user);
    setNewPassword('');
    setShowResetPasswordModal(true);
  };

  // Statistiques
  const stats = {
    total: users.length,
    admins: users.filter(u => u.is_admin).length,
    active: users.filter(u => u.is_active).length,
    inactive: users.filter(u => !u.is_active).length,
  };

  return (
    <div className="space-y-6">
      {/* Header avec statistiques */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className={`text-2xl font-bold ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>
            Gestion des utilisateurs
          </h2>
          <p className={`text-sm mt-1 ${theme === 'dark' ? 'text-gray-400' : 'text-gray-500'}`}>
            {stats.total} utilisateurs • {stats.admins} admins • {stats.active} actifs
          </p>
        </div>
        <button
          onClick={() => {
            setFormData({ username: '', email: '', first_name: '', last_name: '', password: '', is_admin: false, is_active: true });
            setShowCreateModal(true);
          }}
          className="flex items-center gap-2 px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg transition"
        >
          <UserPlus className="h-5 w-5" />
          Nouvel utilisateur
        </button>
      </div>

      {/* Filtres */}
      <div className="flex gap-4">
        <select
          value={filterActive === undefined ? 'all' : filterActive ? 'true' : 'false'}
          onChange={(e) => setFilterActive(e.target.value === 'all' ? undefined : e.target.value === 'true')}
          className={`px-4 py-2 border rounded-lg ${
            theme === 'dark'
              ? 'bg-gray-700 border-gray-600 text-white'
              : 'bg-white border-gray-300 text-gray-900'
          }`}
        >
          <option value="all">Tous les statuts</option>
          <option value="true">Actifs uniquement</option>
          <option value="false">Inactifs uniquement</option>
        </select>

        <select
          value={filterAdmin === undefined ? 'all' : filterAdmin ? 'true' : 'false'}
          onChange={(e) => setFilterAdmin(e.target.value === 'all' ? undefined : e.target.value === 'true')}
          className={`px-4 py-2 border rounded-lg ${
            theme === 'dark'
              ? 'bg-gray-700 border-gray-600 text-white'
              : 'bg-white border-gray-300 text-gray-900'
          }`}
        >
          <option value="all">Tous les rôles</option>
          <option value="true">Admins uniquement</option>
          <option value="false">Utilisateurs uniquement</option>
        </select>
      </div>

      {/* Messages d'erreur */}
      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded p-4 flex items-center gap-2">
          <AlertCircle className="h-5 w-5 text-red-500" />
          <span className="text-sm text-red-800 dark:text-red-200">{error}</span>
          <button onClick={() => setError('')} className="ml-auto text-red-500 hover:text-red-700">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Tableau des utilisateurs */}
      {loading ? (
        <div className="text-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto"></div>
          <p className="mt-4 text-gray-500">Chargement...</p>
        </div>
      ) : (
        <div className={`overflow-x-auto rounded-lg border ${
          theme === 'dark' ? 'border-gray-700' : 'border-gray-200'
        }`}>
          <table className="w-full">
            <thead className={theme === 'dark' ? 'bg-gray-800' : 'bg-gray-50'}>
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
                  Utilisateur
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
                  Email
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
                  Rôle
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
                  Statut
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
                  Dernière connexion
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
                  <div className="flex items-center gap-1">
                    <Globe className="h-4 w-4" />
                    Univers
                  </div>
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className={`divide-y ${theme === 'dark' ? 'divide-gray-700' : 'divide-gray-200'}`}>
              {users.map((user) => (
                <tr key={user.id} className={theme === 'dark' ? 'bg-gray-800' : 'bg-white'}>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center gap-2">
                      <span className={`font-medium ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>
                        {user.username}
                      </span>
                      {user.is_admin && (
                        <Shield className="h-4 w-4 text-yellow-500" aria-label="Administrateur" />
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={theme === 'dark' ? 'text-gray-300' : 'text-gray-700'}>
                      {user.email || '-'}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`inline-flex px-2 py-1 text-xs font-medium rounded ${
                      user.is_admin
                        ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-200'
                        : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200'
                    }`}>
                      {user.is_admin ? 'Admin' : 'Utilisateur'}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded ${
                      user.is_active
                        ? 'bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-200'
                        : 'bg-red-100 text-red-800 dark:bg-red-900/20 dark:text-red-200'
                    }`}>
                      {user.is_active ? (
                        <>
                          <Check className="h-3 w-3" />
                          Actif
                        </>
                      ) : (
                        <>
                          <UserX className="h-3 w-3" />
                          Inactif
                        </>
                      )}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    <span className={theme === 'dark' ? 'text-gray-400' : 'text-gray-500'}>
                      {user.last_login
                        ? new Date(user.last_login).toLocaleDateString('fr-FR', {
                            year: 'numeric',
                            month: 'short',
                            day: 'numeric',
                            hour: '2-digit',
                            minute: '2-digit'
                          })
                        : 'Jamais'}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex flex-wrap gap-2">
                      {universes.map((universe) => {
                        const hasAccess = (userUniverseAccess[user.id] || []).includes(universe.id);
                        const isLoading = loadingUniverses[`${user.id}-${universe.id}`];

                        return (
                          <button
                            key={universe.id}
                            onClick={() => toggleUniverseAccess(user.id, universe.id, hasAccess)}
                            disabled={isLoading}
                            className={`inline-flex items-center gap-1 px-2 py-1 text-xs rounded-full transition-all ${
                              isLoading ? 'opacity-50 cursor-wait' : 'cursor-pointer'
                            } ${
                              hasAccess
                                ? 'ring-2 ring-offset-1'
                                : 'opacity-40 hover:opacity-70'
                            }`}
                            style={{
                              backgroundColor: hasAccess ? `${universe.color}30` : `${universe.color}10`,
                              color: universe.color,
                              ringColor: hasAccess ? universe.color : 'transparent'
                            }}
                            title={hasAccess ? `Retirer l'accès à ${universe.name}` : `Donner accès à ${universe.name}`}
                          >
                            {hasAccess && <Check className="h-3 w-3" />}
                            {universe.name}
                          </button>
                        );
                      })}
                      {universes.length === 0 && (
                        <span className="text-xs text-gray-400">Aucun univers</span>
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm">
                    <div className="flex justify-end gap-2">
                      <button
                        onClick={() => openEditModal(user)}
                        className="p-2 text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded"
                        title="Modifier"
                      >
                        <Edit2 className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => openResetPasswordModal(user)}
                        className="p-2 text-purple-500 hover:bg-purple-50 dark:hover:bg-purple-900/20 rounded"
                        title="Réinitialiser le mot de passe"
                      >
                        <Key className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => openDeleteModal(user)}
                        className="p-2 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded"
                        title="Supprimer"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {users.length === 0 && (
            <div className="text-center py-12">
              <p className={theme === 'dark' ? 'text-gray-400' : 'text-gray-500'}>
                Aucun utilisateur trouvé
              </p>
            </div>
          )}
        </div>
      )}

      {/* Modal de création */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className={`max-w-md w-full rounded-lg p-6 ${
            theme === 'dark' ? 'bg-gray-800' : 'bg-white'
          }`}>
            <h3 className={`text-xl font-bold mb-4 ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>
              Créer un utilisateur
            </h3>
            <form onSubmit={handleCreateUser} className="space-y-4">
              <div>
                <label className={`block text-sm font-medium mb-1 ${
                  theme === 'dark' ? 'text-gray-300' : 'text-gray-700'
                }`}>
                  Nom d'utilisateur *
                </label>
                <input
                  type="text"
                  value={formData.username}
                  onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                  className={`w-full px-3 py-2 border rounded-lg ${
                    theme === 'dark'
                      ? 'bg-gray-700 border-gray-600 text-white'
                      : 'bg-white border-gray-300 text-gray-900'
                  }`}
                  required
                  minLength={3}
                />
              </div>
              <div>
                <label className={`block text-sm font-medium mb-1 ${
                  theme === 'dark' ? 'text-gray-300' : 'text-gray-700'
                }`}>
                  Email
                </label>
                <input
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  className={`w-full px-3 py-2 border rounded-lg ${
                    theme === 'dark'
                      ? 'bg-gray-700 border-gray-600 text-white'
                      : 'bg-white border-gray-300 text-gray-900'
                  }`}
                />
              </div>
              <div>
                <label className={`block text-sm font-medium mb-1 ${
                  theme === 'dark' ? 'text-gray-300' : 'text-gray-700'
                }`}>
                  Prénom *
                </label>
                <input
                  type="text"
                  value={formData.first_name}
                  onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
                  className={`w-full px-3 py-2 border rounded-lg ${
                    theme === 'dark'
                      ? 'bg-gray-700 border-gray-600 text-white'
                      : 'bg-white border-gray-300 text-gray-900'
                  }`}
                  required
                />
              </div>
              <div>
                <label className={`block text-sm font-medium mb-1 ${
                  theme === 'dark' ? 'text-gray-300' : 'text-gray-700'
                }`}>
                  Nom *
                </label>
                <input
                  type="text"
                  value={formData.last_name}
                  onChange={(e) => setFormData({ ...formData, last_name: e.target.value })}
                  className={`w-full px-3 py-2 border rounded-lg ${
                    theme === 'dark'
                      ? 'bg-gray-700 border-gray-600 text-white'
                      : 'bg-white border-gray-300 text-gray-900'
                  }`}
                  required
                />
              </div>
              <div>
                <label className={`block text-sm font-medium mb-1 ${
                  theme === 'dark' ? 'text-gray-300' : 'text-gray-700'
                }`}>
                  Mot de passe *
                </label>
                <input
                  type="password"
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  className={`w-full px-3 py-2 border rounded-lg ${
                    theme === 'dark'
                      ? 'bg-gray-700 border-gray-600 text-white'
                      : 'bg-white border-gray-300 text-gray-900'
                  }`}
                  required
                  minLength={8}
                />
                <p className="text-xs text-gray-500 mt-1">Minimum 8 caractères</p>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="create-is-admin"
                  checked={formData.is_admin}
                  onChange={(e) => setFormData({ ...formData, is_admin: e.target.checked })}
                  className="rounded"
                />
                <label htmlFor="create-is-admin" className={`text-sm ${
                  theme === 'dark' ? 'text-gray-300' : 'text-gray-700'
                }`}>
                  Administrateur
                </label>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="create-is-active"
                  checked={formData.is_active}
                  onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                  className="rounded"
                />
                <label htmlFor="create-is-active" className={`text-sm ${
                  theme === 'dark' ? 'text-gray-300' : 'text-gray-700'
                }`}>
                  Compte actif
                </label>
              </div>
              <div className="flex gap-2 pt-4">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className={`flex-1 px-4 py-2 border rounded-lg ${
                    theme === 'dark'
                      ? 'border-gray-600 text-gray-300 hover:bg-gray-700'
                      : 'border-gray-300 text-gray-700 hover:bg-gray-50'
                  }`}
                >
                  Annuler
                </button>
                <button
                  type="submit"
                  className="flex-1 px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg"
                >
                  Créer
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal de modification */}
      {showEditModal && selectedUser && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className={`max-w-md w-full rounded-lg p-6 ${
            theme === 'dark' ? 'bg-gray-800' : 'bg-white'
          }`}>
            <h3 className={`text-xl font-bold mb-4 ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>
              Modifier {selectedUser.username}
            </h3>
            <form onSubmit={handleUpdateUser} className="space-y-4">
              <div>
                <label className={`block text-sm font-medium mb-1 ${
                  theme === 'dark' ? 'text-gray-300' : 'text-gray-700'
                }`}>
                  Email
                </label>
                <input
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  className={`w-full px-3 py-2 border rounded-lg ${
                    theme === 'dark'
                      ? 'bg-gray-700 border-gray-600 text-white'
                      : 'bg-white border-gray-300 text-gray-900'
                  }`}
                />
              </div>
              <div>
                <label className={`block text-sm font-medium mb-1 ${
                  theme === 'dark' ? 'text-gray-300' : 'text-gray-700'
                }`}>
                  Prénom
                </label>
                <input
                  type="text"
                  value={formData.first_name}
                  onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
                  className={`w-full px-3 py-2 border rounded-lg ${
                    theme === 'dark'
                      ? 'bg-gray-700 border-gray-600 text-white'
                      : 'bg-white border-gray-300 text-gray-900'
                  }`}
                />
              </div>
              <div>
                <label className={`block text-sm font-medium mb-1 ${
                  theme === 'dark' ? 'text-gray-300' : 'text-gray-700'
                }`}>
                  Nom
                </label>
                <input
                  type="text"
                  value={formData.last_name}
                  onChange={(e) => setFormData({ ...formData, last_name: e.target.value })}
                  className={`w-full px-3 py-2 border rounded-lg ${
                    theme === 'dark'
                      ? 'bg-gray-700 border-gray-600 text-white'
                      : 'bg-white border-gray-300 text-gray-900'
                  }`}
                />
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="edit-is-admin"
                  checked={formData.is_admin}
                  onChange={(e) => setFormData({ ...formData, is_admin: e.target.checked })}
                  className="rounded"
                />
                <label htmlFor="edit-is-admin" className={`text-sm ${
                  theme === 'dark' ? 'text-gray-300' : 'text-gray-700'
                }`}>
                  Administrateur
                </label>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="edit-is-active"
                  checked={formData.is_active}
                  onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                  className="rounded"
                />
                <label htmlFor="edit-is-active" className={`text-sm ${
                  theme === 'dark' ? 'text-gray-300' : 'text-gray-700'
                }`}>
                  Compte actif
                </label>
              </div>
              <div className="flex gap-2 pt-4">
                <button
                  type="button"
                  onClick={() => {
                    setShowEditModal(false);
                    setSelectedUser(null);
                  }}
                  className={`flex-1 px-4 py-2 border rounded-lg ${
                    theme === 'dark'
                      ? 'border-gray-600 text-gray-300 hover:bg-gray-700'
                      : 'border-gray-300 text-gray-700 hover:bg-gray-50'
                  }`}
                >
                  Annuler
                </button>
                <button
                  type="submit"
                  className="flex-1 px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg"
                >
                  Enregistrer
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal de suppression */}
      {showDeleteModal && selectedUser && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className={`max-w-md w-full rounded-lg p-6 ${
            theme === 'dark' ? 'bg-gray-800' : 'bg-white'
          }`}>
            <h3 className={`text-xl font-bold mb-4 text-red-600`}>
              Supprimer l'utilisateur
            </h3>
            <p className={`mb-6 ${theme === 'dark' ? 'text-gray-300' : 'text-gray-700'}`}>
              Êtes-vous sûr de vouloir supprimer <strong>{selectedUser.username}</strong> ?
              Cette action est irréversible.
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => {
                  setShowDeleteModal(false);
                  setSelectedUser(null);
                }}
                className={`flex-1 px-4 py-2 border rounded-lg ${
                  theme === 'dark'
                    ? 'border-gray-600 text-gray-300 hover:bg-gray-700'
                    : 'border-gray-300 text-gray-700 hover:bg-gray-50'
                }`}
              >
                Annuler
              </button>
              <button
                onClick={handleDeleteUser}
                className="flex-1 px-4 py-2 bg-red-500 hover:bg-red-600 text-white rounded-lg"
              >
                Supprimer
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal de réinitialisation de mot de passe */}
      {showResetPasswordModal && selectedUser && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className={`max-w-md w-full rounded-lg p-6 ${
            theme === 'dark' ? 'bg-gray-800' : 'bg-white'
          }`}>
            <h3 className={`text-xl font-bold mb-4 ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>
              Réinitialiser le mot de passe
            </h3>
            <p className={`mb-4 text-sm ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`}>
              Définir un nouveau mot de passe pour <strong>{selectedUser.username}</strong>
            </p>
            <form onSubmit={handleResetPassword} className="space-y-4">
              <div>
                <label className={`block text-sm font-medium mb-1 ${
                  theme === 'dark' ? 'text-gray-300' : 'text-gray-700'
                }`}>
                  Nouveau mot de passe *
                </label>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className={`w-full px-3 py-2 border rounded-lg ${
                    theme === 'dark'
                      ? 'bg-gray-700 border-gray-600 text-white'
                      : 'bg-white border-gray-300 text-gray-900'
                  }`}
                  required
                  minLength={8}
                  placeholder="Minimum 8 caractères"
                />
              </div>
              <div className="flex gap-2 pt-4">
                <button
                  type="button"
                  onClick={() => {
                    setShowResetPasswordModal(false);
                    setSelectedUser(null);
                    setNewPassword('');
                  }}
                  className={`flex-1 px-4 py-2 border rounded-lg ${
                    theme === 'dark'
                      ? 'border-gray-600 text-gray-300 hover:bg-gray-700'
                      : 'border-gray-300 text-gray-700 hover:bg-gray-50'
                  }`}
                >
                  Annuler
                </button>
                <button
                  type="submit"
                  className="flex-1 px-4 py-2 bg-purple-500 hover:bg-purple-600 text-white rounded-lg"
                >
                  Réinitialiser
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
