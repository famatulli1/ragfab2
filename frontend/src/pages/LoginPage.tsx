import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Lock, User, AlertCircle, MessageSquare } from 'lucide-react';
import { useTheme } from '../App';
import api from '../api/client';

export default function LoginPage() {
  const navigate = useNavigate();
  const { theme } = useTheme();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await api.login({ username, password });

      // Tous les utilisateurs peuvent se connecter
      // Rediriger vers le chat par défaut
      navigate('/');
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || 'Erreur de connexion';
      setError(errorMessage);
      setLoading(false);
    }
  };

  return (
    <div className={`min-h-screen flex items-center justify-center ${
      theme === 'dark' ? 'bg-gray-900' : 'bg-gray-50'
    }`}>
      <div className={`max-w-md w-full space-y-8 p-8 mx-4 ${
        theme === 'dark' ? 'bg-gray-800' : 'bg-white'
      } rounded-lg shadow-xl`}>
        {/* Logo et titre */}
        <div className="text-center">
          <div className="flex justify-center items-center gap-2">
            <MessageSquare className="h-12 w-12 text-blue-500" />
            <Lock className="h-8 w-8 text-blue-500" />
          </div>
          <h2 className={`mt-6 text-3xl font-bold ${
            theme === 'dark' ? 'text-white' : 'text-gray-900'
          }`}>
            RAGFab
          </h2>
          <p className={`mt-2 text-sm ${
            theme === 'dark' ? 'text-gray-400' : 'text-gray-500'
          }`}>
            Connectez-vous pour accéder à votre chat personnel
          </p>
        </div>

        {/* Formulaire */}
        <form onSubmit={handleLogin} className="mt-8 space-y-6">
          {error && (
            <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded p-3 flex items-center gap-2">
              <AlertCircle className="h-5 w-5 text-red-500 flex-shrink-0" />
              <span className="text-sm text-red-800 dark:text-red-200">{error}</span>
            </div>
          )}

          <div className="space-y-4">
            <div>
              <label className={`block text-sm font-medium mb-2 ${
                theme === 'dark' ? 'text-gray-300' : 'text-gray-700'
              }`}>
                Nom d'utilisateur
              </label>
              <div className="relative">
                <User className={`absolute left-3 top-3 h-5 w-5 ${
                  theme === 'dark' ? 'text-gray-500' : 'text-gray-400'
                }`} />
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className={`pl-10 w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                    theme === 'dark'
                      ? 'bg-gray-700 border-gray-600 text-white placeholder-gray-400'
                      : 'bg-white border-gray-300 text-gray-900 placeholder-gray-400'
                  }`}
                  placeholder="admin"
                  required
                  autoComplete="username"
                />
              </div>
            </div>

            <div>
              <label className={`block text-sm font-medium mb-2 ${
                theme === 'dark' ? 'text-gray-300' : 'text-gray-700'
              }`}>
                Mot de passe
              </label>
              <div className="relative">
                <Lock className={`absolute left-3 top-3 h-5 w-5 ${
                  theme === 'dark' ? 'text-gray-500' : 'text-gray-400'
                }`} />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className={`pl-10 w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                    theme === 'dark'
                      ? 'bg-gray-700 border-gray-600 text-white placeholder-gray-400'
                      : 'bg-white border-gray-300 text-gray-900 placeholder-gray-400'
                  }`}
                  placeholder="••••••••"
                  required
                  autoComplete="current-password"
                />
              </div>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 px-4 bg-blue-500 hover:bg-blue-600 text-white font-medium rounded-lg transition disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Connexion en cours...' : 'Se connecter'}
          </button>
        </form>

        {/* Info connexion */}
        <div className="text-center">
          <p className={`text-xs ${
            theme === 'dark' ? 'text-gray-500' : 'text-gray-400'
          }`}>
            Pas de compte ? Contactez un administrateur
          </p>
        </div>
      </div>
    </div>
  );
}
