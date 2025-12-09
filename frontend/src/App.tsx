import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useState, useEffect, createContext, useContext } from 'react';
import ChatPage from './pages/ChatPage';
import AdminPage from './pages/AdminPage';
import AnalyticsPage from './pages/AnalyticsPage';
import QualityManagementPage from './pages/QualityManagementPage';
import LoginPage from './pages/LoginPage';
import ProfilePage from './pages/ProfilePage';
import ProtectedRoute from './components/ProtectedRoute';
import { initSessionTimeout } from './utils/sessionTimeout';

// Theme Context
interface ThemeContextType {
  theme: 'light' | 'dark';
  toggleTheme: () => void;
}

export const ThemeContext = createContext<ThemeContextType>({
  theme: 'light',
  toggleTheme: () => {},
});

export const useTheme = () => useContext(ThemeContext);

function App() {
  const [theme, setTheme] = useState<'light' | 'dark'>('light');

  useEffect(() => {
    const savedTheme = localStorage.getItem('theme') as 'light' | 'dark' | null;
    if (savedTheme) {
      setTheme(savedTheme);
    } else if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
      setTheme('dark');
    }
  }, []);

  useEffect(() => {
    localStorage.setItem('theme', theme);
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [theme]);

  // Initialiser le système de timeout d'inactivité
  useEffect(() => {
    initSessionTimeout();
  }, []);

  const toggleTheme = () => {
    setTheme(prev => prev === 'light' ? 'dark' : 'light');
  };

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme }}>
      <BrowserRouter>
        <Routes>
          {/* Route de connexion - SEULE route publique */}
          <Route path="/login" element={<LoginPage />} />

          {/* Route chat - Protégée, accessible à tous les utilisateurs authentifiés */}
          <Route path="/" element={
            <ProtectedRoute>
              <ChatPage />
            </ProtectedRoute>
          } />

          {/* Route profil - Protégée, accessible à tous les utilisateurs authentifiés */}
          <Route path="/profile" element={
            <ProtectedRoute>
              <ProfilePage />
            </ProtectedRoute>
          } />

          {/* Route admin - Protégée, réservée aux admins */}
          <Route path="/admin" element={
            <ProtectedRoute adminOnly>
              <AdminPage />
            </ProtectedRoute>
          } />

          {/* Route analytics - Protégée, réservée aux admins */}
          <Route path="/analytics" element={
            <ProtectedRoute adminOnly>
              <AnalyticsPage />
            </ProtectedRoute>
          } />

          {/* Route quality management - Protégée, réservée aux admins */}
          <Route path="/admin/quality-management" element={
            <ProtectedRoute adminOnly>
              <QualityManagementPage />
            </ProtectedRoute>
          } />

          {/* Redirection par défaut vers login */}
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </BrowserRouter>
    </ThemeContext.Provider>
  );
}

export default App;
