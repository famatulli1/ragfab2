import { useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';
import api from '../api/client';

interface ProtectedRouteProps {
  children: React.ReactNode;
  adminOnly?: boolean;
}

export default function ProtectedRoute({ children, adminOnly = false }: ProtectedRouteProps) {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
  const [isAdmin, setIsAdmin] = useState<boolean>(false);

  useEffect(() => {
    const checkAuth = async () => {
      const token = sessionStorage.getItem('access_token');
      if (!token) {
        setIsAuthenticated(false);
        return;
      }

      try {
        const user = await api.getCurrentUser();
        setIsAuthenticated(true);
        setIsAdmin(user.is_admin);
      } catch (error) {
        setIsAuthenticated(false);
        sessionStorage.removeItem('access_token');
      }
    };

    checkAuth();
  }, []);

  // Loading state
  if (isAuthenticated === null) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto"></div>
          <p className="mt-4 text-gray-500 dark:text-gray-400">Vérification de l'authentification...</p>
        </div>
      </div>
    );
  }

  // Not authenticated
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  // Admin only routes
  if (adminOnly && !isAdmin) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
}
