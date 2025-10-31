import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle } from 'lucide-react';
import { api } from '../lib/api';

const ReingestionBadge = () => {
  const [count, setCount] = useState<number>(0);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchCount();
    // Rafraîchir toutes les 30 secondes
    const interval = setInterval(fetchCount, 30000);
    return () => clearInterval(interval);
  }, []);

  const fetchCount = async () => {
    try {
      setLoading(true);
      const data = await api.get('/analytics/quality/reingestion-count');
      setCount(data.count);
    } catch (error) {
      console.error('Error fetching reingestion count:', error);
    } finally {
      setLoading(false);
    }
  };

  if (count === 0) return null;

  return (
    <Link
      to="/admin/quality-management"
      className="relative inline-flex items-center gap-2 px-3 py-1.5 bg-orange-100 dark:bg-orange-900/30 text-orange-800 dark:text-orange-200 rounded-lg hover:bg-orange-200 dark:hover:bg-orange-900/50 transition-colors border border-orange-300 dark:border-orange-700"
      title={`${count} document${count > 1 ? 's' : ''} à réingérer`}
    >
      <AlertTriangle className="w-4 h-4" />
      <span className="text-sm font-medium">
        {count} doc{count > 1 ? 's' : ''} à réingérer
      </span>
      {loading && (
        <div className="absolute -top-1 -right-1">
          <div className="w-2 h-2 bg-orange-500 rounded-full animate-pulse" />
        </div>
      )}
    </Link>
  );
};

export default ReingestionBadge;
