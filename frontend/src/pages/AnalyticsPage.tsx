import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  BarChart3,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  FileText,
  MessageSquare,
  ArrowLeft,
  ThumbsUp,
  ThumbsDown,
  User as UserIcon,
  RefreshCw,
  CheckCircle
} from 'lucide-react';
import { useTheme } from '../App';
import UserMenu from '../components/UserMenu';
import api from '../api/client';
import type { User } from '../types';

interface GlobalStats {
  thumbs_up: number;
  thumbs_down: number;
  total_ratings: number;
  satisfaction_rate: number;
  feedback_count: number;
}

interface RerankingStats {
  reranking_enabled: boolean;
  thumbs_up: number;
  thumbs_down: number;
  satisfaction_rate: number;
  feedback_ratio: number;
}

interface DepthStats {
  depth_category: string;
  thumbs_up: number;
  thumbs_down: number;
  satisfaction_rate: number;
}

interface ChunkData {
  chunk_id: string;
  content_preview: string;
  document_title: string;
  document_source: string;
  section: string;
  page_number: string;
  thumbs_up: number;
  thumbs_down: number;
  dissatisfaction_rate: number;
  impact_score: number;
}

interface DocumentData {
  document_id: string;
  title: string;
  source: string;
  thumbs_up: number;
  thumbs_down: number;
  satisfaction_rate: number;
  chunks_with_ratings: number;
  total_chunks: number;
  coverage_rate: number;
}

export default function AnalyticsPage() {
  const { theme } = useTheme();
  const navigate = useNavigate();
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState(30);

  // État des données
  const [summary, setSummary] = useState<any>(null);
  const [worstChunks, setWorstChunks] = useState<ChunkData[]>([]);
  const [worstDocuments, setWorstDocuments] = useState<DocumentData[]>([]);
  const [rerankingComparison, setRerankingComparison] = useState<any>(null);
  const [thumbsDownStats, setThumbsDownStats] = useState<any>(null);

  useEffect(() => {
    loadCurrentUser();
    loadAnalytics();
  }, [period]);

  const loadCurrentUser = async () => {
    try {
      const user = await api.getCurrentUser();
      setCurrentUser(user);

      if (!user.is_admin) {
        navigate('/chat');
      }
    } catch (error) {
      console.error('Error loading current user:', error);
      navigate('/login');
    }
  };

  const loadAnalytics = async () => {
    setLoading(true);
    try {
      const [summaryData, chunksData, documentsData, rerankingData, thumbsDownData] = await Promise.all([
        api.getAnalyticsSummary(period),
        api.getWorstChunks(10, 3),
        api.getWorstDocuments(5, 5),
        api.getRatingsByReranking(period),
        api.getThumbsDownStats(period)
      ]);

      setSummary(summaryData);
      setWorstChunks(chunksData);
      setWorstDocuments(documentsData);
      setRerankingComparison(rerankingData);
      setThumbsDownStats(thumbsDownData);
    } catch (error) {
      console.error('Error loading analytics:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = async () => {
    try {
      await api.logout();
      navigate('/login');
    } catch (error) {
      console.error('Error logging out:', error);
      navigate('/login');
    }
  };

  const globalStats: GlobalStats | null = summary?.global;
  const depthStats: DepthStats[] = summary?.by_depth || [];
  const rerankingStats: RerankingStats[] = rerankingComparison?.stats || [];

  return (
    <div className={`min-h-screen ${theme === 'dark' ? 'bg-gray-900 text-white' : 'bg-gray-50 text-gray-900'}`}>
      {/* Header */}
      <div className={`${theme === 'dark' ? 'bg-gray-800' : 'bg-white'} shadow-sm`}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <button
                onClick={() => navigate('/admin')}
                className="p-2 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
              >
                <ArrowLeft className="w-5 h-5" />
              </button>
              <div className="flex items-center gap-3">
                <BarChart3 className="w-8 h-8 text-blue-500" />
                <div>
                  <h1 className="text-2xl font-bold">Analytics RAG</h1>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    Analyse des ratings utilisateurs et qualité du système
                  </p>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-4">
              {/* Sélecteur de période */}
              <select
                value={period}
                onChange={(e) => setPeriod(Number(e.target.value))}
                className={`px-3 py-2 rounded-lg border ${
                  theme === 'dark'
                    ? 'bg-gray-700 border-gray-600 text-white'
                    : 'bg-white border-gray-300 text-gray-900'
                }`}
              >
                <option value={7}>7 derniers jours</option>
                <option value={30}>30 derniers jours</option>
                <option value={90}>90 derniers jours</option>
              </select>

              {currentUser && <UserMenu user={currentUser} onLogout={handleLogout} />}
            </div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
          </div>
        ) : (
          <div className="space-y-8">
            {/* Section 1 : KPIs Globaux */}
            <div>
              <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-blue-500" />
                Vue d'ensemble
              </h2>

              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                {/* Satisfaction Rate */}
                <div className={`p-6 rounded-lg ${theme === 'dark' ? 'bg-gray-800' : 'bg-white'} shadow`}>
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-gray-500 dark:text-gray-400">Satisfaction</p>
                      <p className="text-3xl font-bold text-green-500">
                        {(Number(globalStats?.satisfaction_rate) || 0).toFixed(1)}%
                      </p>
                    </div>
                    <ThumbsUp className="w-8 h-8 text-green-500 opacity-50" />
                  </div>
                </div>

                {/* Total Ratings */}
                <div className={`p-6 rounded-lg ${theme === 'dark' ? 'bg-gray-800' : 'bg-white'} shadow`}>
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-gray-500 dark:text-gray-400">Ratings totaux</p>
                      <p className="text-3xl font-bold">{globalStats?.total_ratings || 0}</p>
                    </div>
                    <MessageSquare className="w-8 h-8 text-blue-500 opacity-50" />
                  </div>
                </div>

                {/* Thumbs Up */}
                <div className={`p-6 rounded-lg ${theme === 'dark' ? 'bg-gray-800' : 'bg-white'} shadow`}>
                  <div>
                    <p className="text-sm text-gray-500 dark:text-gray-400">Thumbs Up</p>
                    <p className="text-2xl font-bold text-green-600">{globalStats?.thumbs_up || 0}</p>
                  </div>
                </div>

                {/* Thumbs Down */}
                <div className={`p-6 rounded-lg ${theme === 'dark' ? 'bg-gray-800' : 'bg-white'} shadow`}>
                  <div>
                    <p className="text-sm text-gray-500 dark:text-gray-400">Thumbs Down</p>
                    <p className="text-2xl font-bold text-red-600">{globalStats?.thumbs_down || 0}</p>
                  </div>
                </div>
              </div>
            </div>

            {/* Section 2 : Comparaison Reranking */}
            {rerankingStats.length > 0 && (
              <div>
                <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
                  <BarChart3 className="w-5 h-5 text-purple-500" />
                  Impact du Reranking
                </h2>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {rerankingStats.map((stat) => (
                    <div
                      key={String(stat.reranking_enabled)}
                      className={`p-6 rounded-lg ${theme === 'dark' ? 'bg-gray-800' : 'bg-white'} shadow`}
                    >
                      <h3 className="font-semibold mb-4 flex items-center gap-2">
                        {stat.reranking_enabled ? (
                          <>
                            <TrendingUp className="w-4 h-4 text-green-500" />
                            Avec Reranking
                          </>
                        ) : (
                          <>
                            <TrendingDown className="w-4 h-4 text-gray-500" />
                            Sans Reranking
                          </>
                        )}
                      </h3>

                      <div className="space-y-2">
                        <div className="flex justify-between">
                          <span className="text-sm text-gray-500 dark:text-gray-400">Satisfaction</span>
                          <span className="font-semibold">{(Number(stat.satisfaction_rate) || 0).toFixed(1)}%</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-sm text-gray-500 dark:text-gray-400">Thumbs Up</span>
                          <span className="text-green-600">{stat.thumbs_up}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-sm text-gray-500 dark:text-gray-400">Thumbs Down</span>
                          <span className="text-red-600">{stat.thumbs_down}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>

                {rerankingComparison?.impact && (
                  <div className={`mt-4 p-4 rounded-lg ${
                    rerankingComparison.impact.satisfaction_diff > 0
                      ? 'bg-green-100 dark:bg-green-900/20 text-green-800 dark:text-green-300'
                      : 'bg-yellow-100 dark:bg-yellow-900/20 text-yellow-800 dark:text-yellow-300'
                  }`}>
                    <p className="font-medium">{rerankingComparison.impact.recommendation}</p>
                  </div>
                )}
              </div>
            )}

            {/* Section 3 : Profondeur Conversation */}
            {depthStats.length > 0 && (
              <div>
                <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
                  <MessageSquare className="w-5 h-5 text-indigo-500" />
                  Satisfaction par Profondeur de Conversation
                </h2>

                <div className={`p-6 rounded-lg ${theme === 'dark' ? 'bg-gray-800' : 'bg-white'} shadow`}>
                  <div className="space-y-4">
                    {depthStats.map((stat, idx) => (
                      <div key={idx}>
                        <div className="flex justify-between items-center mb-2">
                          <span className="font-medium">{stat.depth_category}</span>
                          <span className="text-sm text-gray-500 dark:text-gray-400">
                            {(Number(stat.satisfaction_rate) || 0).toFixed(1)}%
                          </span>
                        </div>
                        <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-3">
                          <div
                            className={`h-3 rounded-full ${
                              (Number(stat.satisfaction_rate) || 0) >= 70
                                ? 'bg-green-500'
                                : (Number(stat.satisfaction_rate) || 0) >= 50
                                ? 'bg-yellow-500'
                                : 'bg-red-500'
                            }`}
                            style={{ width: `${Number(stat.satisfaction_rate) || 0}%` }}
                          />
                        </div>
                        <div className="flex justify-between text-xs text-gray-500 dark:text-gray-400 mt-1">
                          <span>{stat.thumbs_up} 👍</span>
                          <span>{stat.thumbs_down} 👎</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Section 4 : Pires Chunks */}
            {worstChunks.length > 0 && (
              <div>
                <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
                  <AlertTriangle className="w-5 h-5 text-red-500" />
                  Top 10 Chunks Problématiques
                </h2>

                <div className={`rounded-lg overflow-hidden shadow ${theme === 'dark' ? 'bg-gray-800' : 'bg-white'}`}>
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead className={theme === 'dark' ? 'bg-gray-700' : 'bg-gray-50'}>
                        <tr>
                          <th className="px-4 py-3 text-left text-xs font-medium uppercase">Document</th>
                          <th className="px-4 py-3 text-left text-xs font-medium uppercase">Section</th>
                          <th className="px-4 py-3 text-left text-xs font-medium uppercase">Aperçu</th>
                          <th className="px-4 py-3 text-center text-xs font-medium uppercase">👍</th>
                          <th className="px-4 py-3 text-center text-xs font-medium uppercase">👎</th>
                          <th className="px-4 py-3 text-center text-xs font-medium uppercase">Insatisfaction</th>
                          <th className="px-4 py-3 text-center text-xs font-medium uppercase">Impact</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                        {worstChunks.map((chunk) => (
                          <tr key={chunk.chunk_id} className="hover:bg-gray-50 dark:hover:bg-gray-700">
                            <td className="px-4 py-3 text-sm">
                              <div className="max-w-xs">
                                <p className="font-medium truncate">{chunk.document_title}</p>
                                <p className="text-xs text-gray-500 dark:text-gray-400">Page {chunk.page_number}</p>
                              </div>
                            </td>
                            <td className="px-4 py-3 text-sm">
                              <span className="text-xs text-gray-600 dark:text-gray-400">
                                {chunk.section || '-'}
                              </span>
                            </td>
                            <td className="px-4 py-3 text-sm">
                              <p className="max-w-md truncate text-gray-600 dark:text-gray-400">
                                {chunk.content_preview}
                              </p>
                            </td>
                            <td className="px-4 py-3 text-center text-sm text-green-600">
                              {chunk.thumbs_up}
                            </td>
                            <td className="px-4 py-3 text-center text-sm text-red-600 font-semibold">
                              {chunk.thumbs_down}
                            </td>
                            <td className="px-4 py-3 text-center text-sm">
                              <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                                (Number(chunk.dissatisfaction_rate) || 0) > 0.7
                                  ? 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300'
                                  : (Number(chunk.dissatisfaction_rate) || 0) > 0.5
                                  ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300'
                                  : 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300'
                              }`}>
                                {((Number(chunk.dissatisfaction_rate) || 0) * 100).toFixed(0)}%
                              </span>
                            </td>
                            <td className="px-4 py-3 text-center text-sm font-semibold">
                              {chunk.impact_score}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}

            {/* Section 5 : Pires Documents */}
            {worstDocuments.length > 0 && (
              <div>
                <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
                  <FileText className="w-5 h-5 text-orange-500" />
                  Top 5 Documents à Réingérer
                </h2>

                <div className={`rounded-lg overflow-hidden shadow ${theme === 'dark' ? 'bg-gray-800' : 'bg-white'}`}>
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead className={theme === 'dark' ? 'bg-gray-700' : 'bg-gray-50'}>
                        <tr>
                          <th className="px-4 py-3 text-left text-xs font-medium uppercase">Titre</th>
                          <th className="px-4 py-3 text-center text-xs font-medium uppercase">Satisfaction</th>
                          <th className="px-4 py-3 text-center text-xs font-medium uppercase">👍</th>
                          <th className="px-4 py-3 text-center text-xs font-medium uppercase">👎</th>
                          <th className="px-4 py-3 text-center text-xs font-medium uppercase">Chunks évalués</th>
                          <th className="px-4 py-3 text-center text-xs font-medium uppercase">Couverture</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                        {worstDocuments.map((doc) => (
                          <tr key={doc.document_id} className="hover:bg-gray-50 dark:hover:bg-gray-700">
                            <td className="px-4 py-3 text-sm">
                              <div className="max-w-md">
                                <p className="font-medium">{doc.title}</p>
                                <p className="text-xs text-gray-500 dark:text-gray-400 truncate">{doc.source}</p>
                              </div>
                            </td>
                            <td className="px-4 py-3 text-center text-sm">
                              <span className={`px-3 py-1 rounded-full text-sm font-semibold ${
                                (Number(doc.satisfaction_rate) || 0) < 30
                                  ? 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300'
                                  : (Number(doc.satisfaction_rate) || 0) < 60
                                  ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300'
                                  : 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300'
                              }`}>
                                {(Number(doc.satisfaction_rate) || 0).toFixed(1)}%
                              </span>
                            </td>
                            <td className="px-4 py-3 text-center text-sm text-green-600">{doc.thumbs_up}</td>
                            <td className="px-4 py-3 text-center text-sm text-red-600 font-semibold">{doc.thumbs_down}</td>
                            <td className="px-4 py-3 text-center text-sm">
                              {doc.chunks_with_ratings} / {doc.total_chunks}
                            </td>
                            <td className="px-4 py-3 text-center text-sm">
                              {(Number(doc.coverage_rate) || 0).toFixed(0)}%
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                <div className={`mt-4 p-4 rounded-lg ${theme === 'dark' ? 'bg-blue-900/20' : 'bg-blue-50'} border border-blue-200 dark:border-blue-800`}>
                  <p className="text-sm text-blue-800 dark:text-blue-300">
                    💡 <strong>Recommandation</strong> : Réingérer ces documents avec optimisations (parent-child chunks, contextual retrieval, hybrid search)
                  </p>
                </div>
              </div>
            )}

            {/* Section 6 : Thumbs Down Validation */}
            {thumbsDownStats && thumbsDownStats.summary && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Widget 1: Résumé Thumbs Down */}
                <div>
                  <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
                    <ThumbsDown className="w-5 h-5 text-red-500" />
                    Validation Thumbs Down
                  </h2>

                  <div className={`rounded-lg p-6 shadow ${theme === 'dark' ? 'bg-gray-800' : 'bg-white'}`}>
                    <div className="grid grid-cols-2 gap-4 mb-4">
                      <div className="text-center p-3 rounded-lg bg-red-50 dark:bg-red-900/20">
                        <div className="text-2xl font-bold text-red-600 dark:text-red-400">
                          {thumbsDownStats.summary.total_thumbs_down}
                        </div>
                        <div className="text-xs text-gray-600 dark:text-gray-400">Total thumbs down</div>
                      </div>
                      <div className="text-center p-3 rounded-lg bg-yellow-50 dark:bg-yellow-900/20">
                        <div className="text-2xl font-bold text-yellow-600 dark:text-yellow-400">
                          {thumbsDownStats.summary.pending_review}
                        </div>
                        <div className="text-xs text-gray-600 dark:text-gray-400">En attente</div>
                      </div>
                    </div>

                    <div className="space-y-2">
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-gray-600 dark:text-gray-400">❓ Questions mal formulées</span>
                        <span className="font-semibold">{thumbsDownStats.summary.bad_questions}</span>
                      </div>
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-gray-600 dark:text-gray-400">❌ Réponses incorrectes</span>
                        <span className="font-semibold">{thumbsDownStats.summary.bad_answers}</span>
                      </div>
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-gray-600 dark:text-gray-400">📚 Sources manquantes</span>
                        <span className="font-semibold">{thumbsDownStats.summary.missing_sources}</span>
                      </div>
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-gray-600 dark:text-gray-400">🎯 Attentes hors scope</span>
                        <span className="font-semibold">{thumbsDownStats.summary.unrealistic_expectations}</span>
                      </div>
                    </div>

                    <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-gray-600 dark:text-gray-400">Confiance IA moyenne</span>
                        <span className="font-semibold">{(thumbsDownStats.summary.avg_confidence * 100).toFixed(0)}%</span>
                      </div>
                      <div className="flex items-center justify-between text-sm mt-2">
                        <span className="text-gray-600 dark:text-gray-400">Overrides admin</span>
                        <span className="font-semibold">{thumbsDownStats.summary.admin_overrides}</span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Widget 2: Actions Requises */}
                <div>
                  <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
                    <CheckCircle className="w-5 h-5 text-blue-500" />
                    Actions Requises
                  </h2>

                  <div className={`rounded-lg p-6 shadow ${theme === 'dark' ? 'bg-gray-800' : 'bg-white'}`}>
                    <div className="space-y-4">
                      {/* Utilisateurs à accompagner */}
                      <div className="p-4 rounded-lg bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800">
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <User className="w-5 h-5 text-yellow-600 dark:text-yellow-400" />
                            <span className="font-semibold text-yellow-900 dark:text-yellow-200">
                              Utilisateurs à accompagner
                            </span>
                          </div>
                          <span className="text-2xl font-bold text-yellow-600 dark:text-yellow-400">
                            {thumbsDownStats.summary.users_to_contact}
                          </span>
                        </div>
                        <p className="text-xs text-yellow-800 dark:text-yellow-300">
                          Nécessitent aide pour formuler leurs questions
                        </p>
                        <button
                          onClick={() => navigate('/quality-management')}
                          className="mt-2 text-xs text-yellow-700 dark:text-yellow-400 hover:underline"
                        >
                          → Voir dans Quality Management
                        </button>
                      </div>

                      {/* Documents à réingérer */}
                      <div className="p-4 rounded-lg bg-orange-50 dark:bg-orange-900/20 border border-orange-200 dark:border-orange-800">
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <RefreshCw className="w-5 h-5 text-orange-600 dark:text-orange-400" />
                            <span className="font-semibold text-orange-900 dark:text-orange-200">
                              Documents à réingérer
                            </span>
                          </div>
                          <span className="text-2xl font-bold text-orange-600 dark:text-orange-400">
                            {thumbsDownStats.summary.documents_to_reingest}
                          </span>
                        </div>
                        <p className="text-xs text-orange-800 dark:text-orange-300">
                          Sources manquantes ou incorrectes détectées
                        </p>
                        <button
                          onClick={() => navigate('/quality-management')}
                          className="mt-2 text-xs text-orange-700 dark:text-orange-400 hover:underline"
                        >
                          → Voir dans Quality Management
                        </button>
                      </div>

                      {/* Bouton d'action principal */}
                      <button
                        onClick={() => navigate('/quality-management')}
                        className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center justify-center gap-2"
                      >
                        <ThumbsDown className="w-4 h-4" />
                        Accéder à la validation
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Message si pas de données */}
            {!globalStats?.total_ratings && (
              <div className={`p-8 rounded-lg text-center ${theme === 'dark' ? 'bg-gray-800' : 'bg-white'} shadow`}>
                <BarChart3 className="w-16 h-16 mx-auto text-gray-400 mb-4" />
                <h3 className="text-lg font-semibold mb-2">Aucune donnée disponible</h3>
                <p className="text-gray-500 dark:text-gray-400">
                  Les ratings utilisateurs apparaîtront ici une fois que les utilisateurs auront commencé à évaluer les réponses.
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
