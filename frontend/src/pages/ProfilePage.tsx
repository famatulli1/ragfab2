import { useState, useEffect } from 'react';
import { User as UserIcon, Lock, ArrowLeft, Save, Globe, Check, Lightbulb } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';
import UserAvatar from '../components/UserAvatar';
import ChangePasswordModal from '../components/ChangePasswordModal';
import type { User, UserUniverseAccess, SuggestionMode } from '../types';

export default function ProfilePage() {
  const navigate = useNavigate();
  const [user, setUser] = useState<User | null>(null);
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [successMessage, setSuccessMessage] = useState('');
  const [errorMessage, setErrorMessage] = useState('');

  // État pour les préférences univers
  const [userUniverses, setUserUniverses] = useState<UserUniverseAccess[]>([]);
  const [defaultUniverseId, setDefaultUniverseId] = useState<string | null>(null);
  const [isSavingUniverse, setIsSavingUniverse] = useState(false);

  // État pour les préférences de suggestions
  const [suggestionMode, setSuggestionMode] = useState<SuggestionMode>(null);
  const [effectiveMode, setEffectiveMode] = useState<string>('');
  const [isSavingSuggestion, setIsSavingSuggestion] = useState(false);

  useEffect(() => {
    loadUser();
    loadUniverses();
    loadPreferences();
  }, []);

  const loadUser = async () => {
    try {
      const userData = await api.getCurrentUser();
      setUser(userData);
      setFirstName(userData.first_name || '');
      setLastName(userData.last_name || '');
    } catch (error) {
      console.error('Error loading user:', error);
      navigate('/login');
    }
  };

  const loadUniverses = async () => {
    try {
      // Charger les univers de l'utilisateur
      const universes = await api.getMyUniverseAccess();
      setUserUniverses(universes);

      // Charger l'univers par défaut
      const defaultResponse = await api.getMyDefaultUniverse();
      if (defaultResponse.default_universe) {
        setDefaultUniverseId(defaultResponse.default_universe.universe_id);
      }
    } catch (error) {
      console.error('Error loading universes:', error);
    }
  };

  const handleSetDefaultUniverse = async (universeId: string) => {
    setIsSavingUniverse(true);
    setErrorMessage('');

    try {
      await api.setMyDefaultUniverse(universeId);
      setDefaultUniverseId(universeId);
      setSuccessMessage('Univers par defaut mis a jour');
      setTimeout(() => setSuccessMessage(''), 3000);
    } catch (error: any) {
      setErrorMessage(error.response?.data?.detail || 'Erreur lors de la mise a jour');
    } finally {
      setIsSavingUniverse(false);
    }
  };

  const loadPreferences = async () => {
    try {
      const prefs = await api.getMyPreferences();
      setSuggestionMode(prefs.suggestion_mode);
      setEffectiveMode(prefs.effective_mode);
    } catch (error) {
      console.error('Error loading preferences:', error);
    }
  };

  const handleSetSuggestionMode = async (mode: SuggestionMode) => {
    setIsSavingSuggestion(true);
    setErrorMessage('');

    try {
      const result = await api.updateMyPreferences({ suggestion_mode: mode });
      setSuggestionMode(result.suggestion_mode);
      setEffectiveMode(result.effective_mode);
      setSuccessMessage('Preference de suggestions mise a jour');
      setTimeout(() => setSuccessMessage(''), 3000);
    } catch (error: any) {
      setErrorMessage(error.response?.data?.detail || 'Erreur lors de la mise a jour');
    } finally {
      setIsSavingSuggestion(false);
    }
  };

  const handleSaveProfile = async () => {
    if (!user) return;

    setIsSaving(true);
    setErrorMessage('');
    setSuccessMessage('');

    try {
      await api.updateMyProfile({
        first_name: firstName,
        last_name: lastName,
      });

      setSuccessMessage('Profil mis à jour avec succès');
      setIsEditing(false);
      await loadUser();

      // Effacer le message après 3 secondes
      setTimeout(() => setSuccessMessage(''), 3000);
    } catch (error: any) {
      setErrorMessage(error.response?.data?.detail || 'Erreur lors de la mise à jour');
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancelEdit = () => {
    if (user) {
      setFirstName(user.first_name || '');
      setLastName(user.last_name || '');
    }
    setIsEditing(false);
    setErrorMessage('');
  };

  const handlePasswordSubmit = async (currentPassword: string, newPassword: string, confirmPassword: string) => {
    await api.changeMyPassword({
      current_password: currentPassword,
      new_password: newPassword,
      confirm_password: confirmPassword,
    });
  };

  const handlePasswordChanged = () => {
    setShowPasswordModal(false);
    setSuccessMessage('Mot de passe modifié avec succès');
    setTimeout(() => setSuccessMessage(''), 3000);
  };

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
        <div className="text-gray-600 dark:text-gray-400">Chargement...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <div className="max-w-4xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-6">
          <button
            onClick={() => navigate(-1)}
            className="flex items-center gap-2 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors mb-4"
          >
            <ArrowLeft className="w-5 h-5" />
            <span>Retour</span>
          </button>

          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Mon profil</h1>
          <p className="text-gray-600 dark:text-gray-400 mt-1">Gérez vos informations personnelles et votre sécurité</p>
        </div>

        {/* Success/Error Messages */}
        {successMessage && (
          <div className="mb-6 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-4">
            <p className="text-sm text-green-800 dark:text-green-200">{successMessage}</p>
          </div>
        )}

        {errorMessage && (
          <div className="mb-6 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
            <p className="text-sm text-red-800 dark:text-red-200">{errorMessage}</p>
          </div>
        )}

        {/* Profile Section */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6 mb-6">
          <div className="flex items-start justify-between mb-6">
            <div className="flex items-center gap-4">
              <UserAvatar user={user} size="lg" />
              <div>
                <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
                  {`${user.first_name || ''} ${user.last_name || ''}`.trim() || user.username}
                </h2>
                <p className="text-sm text-gray-600 dark:text-gray-400">{user.email || user.username}</p>
              </div>
            </div>

            {!isEditing && (
              <button
                onClick={() => setIsEditing(true)}
                className="px-4 py-2 text-sm font-medium text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded-lg transition-colors"
              >
                Modifier
              </button>
            )}
          </div>

          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Prénom
                </label>
                <input
                  type="text"
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  disabled={!isEditing}
                  className={`w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white ${
                    isEditing ? 'focus:ring-2 focus:ring-blue-500 focus:border-transparent' : 'bg-gray-50 dark:bg-gray-700/50'
                  }`}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Nom
                </label>
                <input
                  type="text"
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                  disabled={!isEditing}
                  className={`w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white ${
                    isEditing ? 'focus:ring-2 focus:ring-blue-500 focus:border-transparent' : 'bg-gray-50 dark:bg-gray-700/50'
                  }`}
                />
              </div>
            </div>

            {isEditing && (
              <div className="flex gap-3 pt-2">
                <button
                  onClick={handleSaveProfile}
                  disabled={isSaving}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors ${
                    isSaving
                      ? 'bg-gray-300 dark:bg-gray-700 text-gray-500 cursor-not-allowed'
                      : 'bg-blue-600 hover:bg-blue-700 text-white'
                  }`}
                >
                  <Save className="w-4 h-4" />
                  {isSaving ? 'Enregistrement...' : 'Enregistrer'}
                </button>

                <button
                  onClick={handleCancelEdit}
                  disabled={isSaving}
                  className="px-4 py-2 rounded-lg font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                >
                  Annuler
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Account Section */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6 mb-6">
          <div className="flex items-center gap-3 mb-4">
            <UserIcon className="w-5 h-5 text-gray-600 dark:text-gray-400" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Informations du compte</h2>
          </div>

          <div className="space-y-3 text-sm">
            <div className="flex justify-between py-2 border-b border-gray-200 dark:border-gray-700">
              <span className="text-gray-600 dark:text-gray-400">Nom d'utilisateur</span>
              <span className="font-medium text-gray-900 dark:text-white">{user.username}</span>
            </div>

            <div className="flex justify-between py-2 border-b border-gray-200 dark:border-gray-700">
              <span className="text-gray-600 dark:text-gray-400">Email</span>
              <span className="font-medium text-gray-900 dark:text-white">{user.email || 'Non renseigné'}</span>
            </div>

            <div className="flex justify-between py-2 border-b border-gray-200 dark:border-gray-700">
              <span className="text-gray-600 dark:text-gray-400">Rôle</span>
              <span className="font-medium text-gray-900 dark:text-white">
                {user.is_admin ? 'Administrateur' : 'Utilisateur'}
              </span>
            </div>

            <div className="flex justify-between py-2">
              <span className="text-gray-600 dark:text-gray-400">Compte créé le</span>
              <span className="font-medium text-gray-900 dark:text-white">
                {new Date(user.created_at).toLocaleDateString('fr-FR')}
              </span>
            </div>
          </div>
        </div>

        {/* Preferences Section - Universe */}
        {userUniverses.length > 1 && (
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6 mb-6">
            <div className="flex items-center gap-3 mb-4">
              <Globe className="w-5 h-5 text-gray-600 dark:text-gray-400" />
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Préférences</h2>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Univers par défaut
                </label>
                <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">
                  Cet univers sera sélectionné automatiquement lors de vos nouvelles conversations
                </p>

                <div className="space-y-2">
                  {userUniverses.map((universe) => (
                    <button
                      key={universe.universe_id}
                      onClick={() => handleSetDefaultUniverse(universe.universe_id)}
                      disabled={isSavingUniverse}
                      className={`w-full flex items-center justify-between p-3 rounded-lg border transition-all ${
                        defaultUniverseId === universe.universe_id
                          ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                          : 'border-gray-200 dark:border-gray-600 hover:border-gray-300 dark:hover:border-gray-500 hover:bg-gray-50 dark:hover:bg-gray-700/50'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <div
                          className="w-3 h-3 rounded-full"
                          style={{ backgroundColor: universe.universe_color }}
                        />
                        <span className={`font-medium ${
                          defaultUniverseId === universe.universe_id
                            ? 'text-blue-700 dark:text-blue-300'
                            : 'text-gray-900 dark:text-white'
                        }`}>
                          {universe.universe_name}
                        </span>
                      </div>
                      {defaultUniverseId === universe.universe_id && (
                        <Check className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                      )}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Suggestions Section */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6 mb-6">
          <div className="flex items-center gap-3 mb-4">
            <Lightbulb className="w-5 h-5 text-gray-600 dark:text-gray-400" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Suggestions de reformulation</h2>
          </div>

          <div className="space-y-4">
            <div>
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">
                Controlez quand les suggestions de reformulation de questions s'affichent
              </p>

              <div className="space-y-2">
                {[
                  { value: null as SuggestionMode, label: 'Par defaut (systeme)', desc: `Utiliser la configuration systeme (${effectiveMode || 'soft'})` },
                  { value: 'off' as SuggestionMode, label: 'Desactive', desc: 'Ne jamais afficher de suggestions' },
                  { value: 'soft' as SuggestionMode, label: 'Suggestions douces', desc: 'Afficher apres la reponse' },
                  { value: 'interactive' as SuggestionMode, label: 'Interactif', desc: 'Proposer avant de repondre' }
                ].map((option) => (
                  <button
                    key={option.value ?? 'default'}
                    onClick={() => handleSetSuggestionMode(option.value)}
                    disabled={isSavingSuggestion}
                    className={`w-full flex items-center justify-between p-3 rounded-lg border transition-all ${
                      suggestionMode === option.value
                        ? 'border-amber-500 bg-amber-50 dark:bg-amber-900/20'
                        : 'border-gray-200 dark:border-gray-600 hover:border-gray-300 dark:hover:border-gray-500 hover:bg-gray-50 dark:hover:bg-gray-700/50'
                    }`}
                  >
                    <div className="text-left">
                      <span className={`font-medium ${
                        suggestionMode === option.value
                          ? 'text-amber-700 dark:text-amber-300'
                          : 'text-gray-900 dark:text-white'
                      }`}>
                        {option.label}
                      </span>
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                        {option.desc}
                      </p>
                    </div>
                    {suggestionMode === option.value && (
                      <Check className="w-5 h-5 text-amber-600 dark:text-amber-400" />
                    )}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Security Section */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
          <div className="flex items-center gap-3 mb-4">
            <Lock className="w-5 h-5 text-gray-600 dark:text-gray-400" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Sécurité</h2>
          </div>

          <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
            Modifiez votre mot de passe pour renforcer la sécurité de votre compte
          </p>

          <button
            onClick={() => setShowPasswordModal(true)}
            className="px-4 py-2 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-900 dark:text-white rounded-lg font-medium transition-colors"
          >
            Changer mon mot de passe
          </button>
        </div>
      </div>

      {/* Password Change Modal */}
      {showPasswordModal && (
        <ChangePasswordModal
          isFirstLogin={false}
          onPasswordChanged={handlePasswordChanged}
          onSubmit={handlePasswordSubmit}
        />
      )}
    </div>
  );
}
