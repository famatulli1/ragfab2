import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import {
  Brain,
  Star,
  CheckCircle,
  XCircle,
  TrendingDown,
  FileText,
  History,
  Loader2,
  AlertCircle,
  RefreshCw,
  Shield,
  Ban,
  ArrowLeft
} from 'lucide-react';

interface BlacklistedChunk {
  chunk_id: string;
  content_preview: string;
  full_content: string;
  document_title: string;
  document_source: string;
  section: string | null;
  page_number: string | null;
  thumbs_up_count: number;
  thumbs_down_count: number;
  total_appearances: number;
  satisfaction_rate: number | null;
  blacklist_reason: string | null;
  is_whitelisted: boolean;
  updated_at: string;
  last_ai_analysis: any;
}

interface ReingestionDoc {
  document_id: string;
  title: string;
  source: string;
  ingestion_date: string;
  thumbs_up_count: number;
  thumbs_down_count: number;
  total_appearances: number;
  satisfaction_rate: number | null;
  reingestion_reason: string | null;
  updated_at: string;
  blacklisted_chunks_count: number;
  last_ai_analysis: any;
}

interface AnalysisRun {
  id: string;
  status: string;
  progress: number;
  started_by: string;
  started_at: string;
  completed_at: string | null;
  duration_seconds: number | null;
  chunks_analyzed: number;
  chunks_blacklisted: number;
  documents_flagged: number;
  error_message: string | null;
  run_type: string;
  status_label: string;
}

interface AuditLogEntry {
  id: string;
  chunk_id: string | null;
  document_id: string | null;
  action: string;
  reason: string;
  decided_by: string;
  ai_analysis: any;
  created_at: string;
  chunk_preview: string | null;
  document_title: string | null;
}

const QualityManagementPage = () => {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<'blacklisted' | 'reingestion' | 'trigger' | 'history'>('blacklisted');

  // Tab 1: Blacklisted Chunks
  const [blacklistedChunks, setBlacklistedChunks] = useState<BlacklistedChunk[]>([]);
  const [loadingBlacklisted, setLoadingBlacklisted] = useState(false);
  const [_selectedChunk, setSelectedChunk] = useState<BlacklistedChunk | null>(null);

  // Tab 2: Reingestion Recommendations
  const [reingestionDocs, setReingestionDocs] = useState<ReingestionDoc[]>([]);
  const [loadingReingestion, setLoadingReingestion] = useState(false);
  const [_selectedDoc, setSelectedDoc] = useState<ReingestionDoc | null>(null);

  // Tab 3: Manual Trigger
  const [analysisInProgress, setAnalysisInProgress] = useState(false);
  const [currentRunId, setCurrentRunId] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [analysisStatus, setAnalysisStatus] = useState<AnalysisRun | null>(null);

  // Tab 4: History
  const [analysisHistory, setAnalysisHistory] = useState<AnalysisRun[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [auditLog, setAuditLog] = useState<AuditLogEntry[]>([]);
  const [loadingAudit, setLoadingAudit] = useState(false);

  // Reingestion Modal
  const [showReingestionModal, setShowReingestionModal] = useState(false);
  const [selectedDocForReingest, setSelectedDocForReingest] = useState<ReingestionDoc | null>(null);
  const [reingestionConfig, setReingestionConfig] = useState<{
    ocr_engine: 'rapidocr' | 'easyocr' | 'tesseract';
    vlm_engine: 'paddleocr-vl' | 'internvl' | 'none';
    chunker_type: 'hybrid' | 'parent_child';
  }>({
    ocr_engine: 'rapidocr',
    vlm_engine: 'paddleocr-vl',
    chunker_type: 'hybrid'
  });
  const [reingesting, setReingesting] = useState(false);

  useEffect(() => {
    if (activeTab === 'blacklisted') {
      fetchBlacklistedChunks();
    } else if (activeTab === 'reingestion') {
      fetchReingestionDocs();
    } else if (activeTab === 'history') {
      fetchAnalysisHistory();
      fetchAuditLog();
    }
  }, [activeTab]);

  // Poll analysis progress
  useEffect(() => {
    if (!currentRunId || !analysisInProgress) return;

    const interval = setInterval(async () => {
      try {
        const status = await api.getAnalysisStatus(currentRunId);
        setAnalysisStatus(status);
        setProgress(status.progress);

        if (status.status !== 'running') {
          setAnalysisInProgress(false);
          clearInterval(interval);
          // Refresh data
          fetchBlacklistedChunks();
          fetchReingestionDocs();
          fetchAnalysisHistory();
        }
      } catch (error) {
        console.error('Error polling analysis status:', error);
        clearInterval(interval);
        setAnalysisInProgress(false);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [currentRunId, analysisInProgress]);

  const fetchBlacklistedChunks = async () => {
    setLoadingBlacklisted(true);
    try {
      const data = await api.getBlacklistedChunks();
      setBlacklistedChunks(data);
    } catch (error) {
      console.error('Error fetching blacklisted chunks:', error);
    } finally {
      setLoadingBlacklisted(false);
    }
  };

  const fetchReingestionDocs = async () => {
    setLoadingReingestion(true);
    try {
      const data = await api.getReingestionRecommendations();
      setReingestionDocs(data);
    } catch (error) {
      console.error('Error fetching reingestion docs:', error);
    } finally {
      setLoadingReingestion(false);
    }
  };

  const fetchAnalysisHistory = async () => {
    setLoadingHistory(true);
    try {
      const data = await api.getAnalysisHistory();
      setAnalysisHistory(data);
    } catch (error) {
      console.error('Error fetching analysis history:', error);
    } finally {
      setLoadingHistory(false);
    }
  };

  const fetchAuditLog = async () => {
    setLoadingAudit(true);
    try {
      const data = await api.getQualityAuditLog(50);
      setAuditLog(data);
    } catch (error) {
      console.error('Error fetching audit log:', error);
    } finally {
      setLoadingAudit(false);
    }
  };

  const handleUnblacklist = async (chunkId: string, reason: string) => {
    try {
      await api.unblacklistChunk(chunkId, reason);
      fetchBlacklistedChunks();
      setSelectedChunk(null);
    } catch (error) {
      console.error('Error unblacklisting chunk:', error);
      alert('Erreur lors du déblacklist');
    }
  };

  const handleWhitelist = async (chunkId: string, reason: string) => {
    try {
      await api.whitelistChunk(chunkId, reason);
      fetchBlacklistedChunks();
      setSelectedChunk(null);
    } catch (error) {
      console.error('Error whitelisting chunk:', error);
      alert('Erreur lors du whitelist');
    }
  };

  const handleIgnoreRecommendation = async (documentId: string, reason: string) => {
    try {
      await api.ignoreReingestionRecommendation(documentId, reason);
      fetchReingestionDocs();
      setSelectedDoc(null);
    } catch (error) {
      console.error('Error ignoring recommendation:', error);
      alert('Erreur lors de l\'ignorage de la recommandation');
    }
  };

  const openReingestionModal = (doc: ReingestionDoc) => {
    // Parse Chocolatine recommendations to pre-fill config
    const aiConfig = doc.last_ai_analysis?.reingestion_config || '';
    const configText = aiConfig.toLowerCase();

    // Smart parsing of Chocolatine recommendations
    const newConfig = {
      ocr_engine: (
        configText.includes('tesseract') ? 'tesseract' :
        configText.includes('easyocr') ? 'easyocr' :
        'rapidocr'
      ) as 'rapidocr' | 'easyocr' | 'tesseract',
      vlm_engine: (
        configText.includes('internvl') ? 'internvl' :
        configText.includes('vlm') || configText.includes('image') ? 'paddleocr-vl' :
        'paddleocr-vl'
      ) as 'paddleocr-vl' | 'internvl' | 'none',
      chunker_type: (
        configText.includes('parent') || configText.includes('child') ? 'parent_child' :
        'hybrid'
      ) as 'hybrid' | 'parent_child'
    };

    setSelectedDocForReingest(doc);
    setReingestionConfig(newConfig);
    setShowReingestionModal(true);
  };

  const handleConfirmReingest = async () => {
    if (!selectedDocForReingest) return;

    try {
      setReingesting(true);
      const response = await api.reingestDocument(selectedDocForReingest.document_id, reingestionConfig);
      console.log('✅ Reingestion started:', response);

      // Close modal and reload list
      setShowReingestionModal(false);
      setSelectedDocForReingest(null);

      // Show success message
      alert(`Réingestion lancée avec succès !\n\nJob ID: ${response.job_id}\n\n${response.message}`);

      // Reload docs list
      await fetchReingestionDocs();
    } catch (error: any) {
      console.error('❌ Error during reingestion:', error);
      const message = error.response?.data?.detail || error.message || 'Erreur inconnue';
      alert(`Erreur lors de la réingestion:\n\n${message}`);
    } finally {
      setReingesting(false);
    }
  };

  const handleTriggerAnalysis = async () => {
    try {
      setAnalysisInProgress(true);
      setProgress(0);
      const response = await api.triggerQualityAnalysis();
      setCurrentRunId(response.run_id);
    } catch (error) {
      console.error('Error triggering analysis:', error);
      alert('Erreur lors du déclenchement de l\'analyse');
      setAnalysisInProgress(false);
    }
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString('fr-FR');
  };

  const formatDuration = (seconds: number | null) => {
    if (!seconds) return 'N/A';
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}m ${secs}s`;
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <div className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate('/admin')}
              className="p-2 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
              title="Retour à l'administration"
            >
              <ArrowLeft className="w-6 h-6" />
            </button>
            <Shield className="w-8 h-8 text-blue-600 dark:text-blue-400" />
            <div>
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
                Gestion de la Qualité RAG
              </h1>
              <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                Intelligence Chocolatine pour l'amélioration continue
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Tabs Navigation */}
      <div className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
        <div className="max-w-7xl mx-auto px-4">
          <div className="flex gap-4">
            <button
              onClick={() => setActiveTab('blacklisted')}
              className={`px-4 py-3 border-b-2 font-medium text-sm ${
                activeTab === 'blacklisted'
                  ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                  : 'border-transparent text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
              }`}
            >
              <div className="flex items-center gap-2">
                <Ban className="w-4 h-4" />
                Chunks Blacklistés
              </div>
            </button>

            <button
              onClick={() => setActiveTab('reingestion')}
              className={`px-4 py-3 border-b-2 font-medium text-sm ${
                activeTab === 'reingestion'
                  ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                  : 'border-transparent text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
              }`}
            >
              <div className="flex items-center gap-2">
                <RefreshCw className="w-4 h-4" />
                Documents à Réingérer
              </div>
            </button>

            <button
              onClick={() => setActiveTab('trigger')}
              className={`px-4 py-3 border-b-2 font-medium text-sm ${
                activeTab === 'trigger'
                  ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                  : 'border-transparent text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
              }`}
            >
              <div className="flex items-center gap-2">
                <Brain className="w-4 h-4" />
                Analyse Manuelle
              </div>
            </button>

            <button
              onClick={() => setActiveTab('history')}
              className={`px-4 py-3 border-b-2 font-medium text-sm ${
                activeTab === 'history'
                  ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                  : 'border-transparent text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
              }`}
            >
              <div className="flex items-center gap-2">
                <History className="w-4 h-4" />
                Historique
              </div>
            </button>
          </div>
        </div>
      </div>

      {/* Tab Content */}
      <div className="max-w-7xl mx-auto px-4 py-6">
        {/* Tab 1: Blacklisted Chunks */}
        {activeTab === 'blacklisted' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                Chunks Blacklistés ({blacklistedChunks.length})
              </h2>
              <button
                onClick={fetchBlacklistedChunks}
                disabled={loadingBlacklisted}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
              >
                <RefreshCw className={`w-4 h-4 ${loadingBlacklisted ? 'animate-spin' : ''}`} />
                Actualiser
              </button>
            </div>

            {loadingBlacklisted ? (
              <div className="flex justify-center py-12">
                <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
              </div>
            ) : blacklistedChunks.length === 0 ? (
              <div className="bg-white dark:bg-gray-800 rounded-lg p-8 text-center">
                <CheckCircle className="w-12 h-12 text-green-500 mx-auto mb-3" />
                <p className="text-gray-600 dark:text-gray-400">
                  Aucun chunk blacklisté. Système en bonne santé !
                </p>
              </div>
            ) : (
              <div className="grid gap-4">
                {blacklistedChunks.map((chunk) => (
                  <div key={chunk.chunk_id} className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <FileText className="w-4 h-4 text-gray-400" />
                          <span className="font-medium text-gray-900 dark:text-white">
                            {chunk.document_title}
                          </span>
                          {chunk.is_whitelisted && (
                            <span className="px-2 py-1 bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200 text-xs rounded">
                              ⭐ Whitelisté
                            </span>
                          )}
                        </div>

                        <p className="text-sm text-gray-700 dark:text-gray-300 mb-2">
                          {chunk.content_preview}
                        </p>

                        {chunk.section && (
                          <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">
                            Section: {chunk.section}
                          </p>
                        )}

                        <div className="flex items-center gap-4 text-sm text-gray-600 dark:text-gray-400">
                          <span className="flex items-center gap-1">
                            <TrendingDown className="w-4 h-4 text-red-500" />
                            {chunk.thumbs_down_count} 👎
                          </span>
                          <span>
                            {chunk.thumbs_up_count} 👍
                          </span>
                          <span>
                            Satisfaction: {chunk.satisfaction_rate ? `${(chunk.satisfaction_rate * 100).toFixed(1)}%` : 'N/A'}
                          </span>
                        </div>

                        {chunk.blacklist_reason && (
                          <div className="mt-3 p-3 bg-red-50 dark:bg-red-900/20 rounded border border-red-200 dark:border-red-800">
                            <p className="text-sm text-red-800 dark:text-red-200">
                              <strong>Raison IA:</strong> {chunk.blacklist_reason}
                            </p>
                          </div>
                        )}
                      </div>

                      <div className="flex flex-col gap-2 ml-4">
                        <button
                          onClick={() => {
                            const reason = prompt('Raison du déblacklist:');
                            if (reason) handleUnblacklist(chunk.chunk_id, reason);
                          }}
                          className="px-3 py-2 bg-green-600 text-white rounded hover:bg-green-700 text-sm flex items-center gap-1"
                        >
                          <CheckCircle className="w-4 h-4" />
                          Déblacklister
                        </button>

                        {!chunk.is_whitelisted && (
                          <button
                            onClick={() => {
                              const reason = prompt('Raison du whitelist (protection):');
                              if (reason) handleWhitelist(chunk.chunk_id, reason);
                            }}
                            className="px-3 py-2 bg-yellow-600 text-white rounded hover:bg-yellow-700 text-sm flex items-center gap-1"
                          >
                            <Star className="w-4 h-4" />
                            Whitelister
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Tab 2: Reingestion Recommendations */}
        {activeTab === 'reingestion' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                Documents à Réingérer ({reingestionDocs.length})
              </h2>
              <button
                onClick={fetchReingestionDocs}
                disabled={loadingReingestion}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
              >
                <RefreshCw className={`w-4 h-4 ${loadingReingestion ? 'animate-spin' : ''}`} />
                Actualiser
              </button>
            </div>

            {loadingReingestion ? (
              <div className="flex justify-center py-12">
                <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
              </div>
            ) : reingestionDocs.length === 0 ? (
              <div className="bg-white dark:bg-gray-800 rounded-lg p-8 text-center">
                <CheckCircle className="w-12 h-12 text-green-500 mx-auto mb-3" />
                <p className="text-gray-600 dark:text-gray-400">
                  Aucun document à réingérer. Tous les documents sont en bonne qualité !
                </p>
              </div>
            ) : (
              <div className="grid gap-4">
                {reingestionDocs.map((doc) => (
                  <div key={doc.document_id} className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <FileText className="w-5 h-5 text-red-500" />
                          <span className="font-medium text-gray-900 dark:text-white text-lg">
                            {doc.title}
                          </span>
                        </div>

                        <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
                          Source: {doc.source}
                        </p>

                        <div className="flex items-center gap-4 text-sm text-gray-600 dark:text-gray-400 mb-3">
                          <span>
                            Satisfaction: <span className="text-red-600 dark:text-red-400 font-semibold">
                              {doc.satisfaction_rate ? `${(doc.satisfaction_rate * 100).toFixed(1)}%` : 'N/A'}
                            </span>
                          </span>
                          <span>
                            Chunks blacklistés: {doc.blacklisted_chunks_count}
                          </span>
                          <span>
                            Apparitions: {doc.total_appearances}
                          </span>
                        </div>

                        {doc.reingestion_reason && (
                          <div className="p-3 bg-orange-50 dark:bg-orange-900/20 rounded border border-orange-200 dark:border-orange-800">
                            <p className="text-sm text-orange-800 dark:text-orange-200">
                              <strong>Recommandation IA:</strong> {doc.reingestion_reason}
                            </p>

                            {doc.last_ai_analysis?.reingestion_config && (
                              <p className="text-xs text-orange-700 dark:text-orange-300 mt-2">
                                <strong>Config suggérée:</strong> {doc.last_ai_analysis.reingestion_config}
                              </p>
                            )}
                          </div>
                        )}
                      </div>

                      <div className="flex flex-col gap-2 ml-4">
                        <button
                          onClick={() => openReingestionModal(doc)}
                          className="px-3 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm flex items-center gap-1"
                        >
                          <RefreshCw className="w-4 h-4" />
                          Réingérer
                        </button>

                        <button
                          onClick={() => {
                            const reason = prompt('Raison d\'ignorer cette recommandation:');
                            if (reason) handleIgnoreRecommendation(doc.document_id, reason);
                          }}
                          className="px-3 py-2 bg-gray-600 text-white rounded hover:bg-gray-700 text-sm flex items-center gap-1"
                        >
                          <XCircle className="w-4 h-4" />
                          Ignorer
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Tab 3: Manual Trigger */}
        {activeTab === 'trigger' && (
          <div className="space-y-6">
            <div className="bg-white dark:bg-gray-800 rounded-lg p-6 border border-gray-200 dark:border-gray-700">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                Déclenchement Manuel de l'Analyse Qualité
              </h2>

              <div className="mb-6">
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                  Lancez une analyse complète de la qualité RAG avec Chocolatine. Cette analyse :
                </p>
                <ul className="list-disc list-inside text-sm text-gray-600 dark:text-gray-400 space-y-1 ml-4">
                  <li>Agrège les ratings utilisateurs</li>
                  <li>Analyse les chunks problématiques avec Chocolatine AI</li>
                  <li>Génère des recommandations de blacklist</li>
                  <li>Identifie les documents à réingérer</li>
                  <li>Respecte les chunks whitelistés (protégés)</li>
                </ul>
              </div>

              <button
                onClick={handleTriggerAnalysis}
                disabled={analysisInProgress}
                className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 text-lg font-medium"
              >
                {analysisInProgress ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    Analyse en cours... {progress}%
                  </>
                ) : (
                  <>
                    <Brain className="w-5 h-5" />
                    Lancer l'Analyse Maintenant
                  </>
                )}
              </button>

              {analysisInProgress && (
                <div className="mt-6">
                  <div className="mb-2 flex justify-between text-sm">
                    <span className="text-gray-600 dark:text-gray-400">Progression</span>
                    <span className="font-semibold text-gray-900 dark:text-white">{progress}%</span>
                  </div>
                  <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-3">
                    <div
                      className="bg-blue-600 h-3 rounded-full transition-all duration-300"
                      style={{ width: `${progress}%` }}
                    />
                  </div>

                  {analysisStatus && (
                    <div className="mt-4 p-4 bg-blue-50 dark:bg-blue-900/20 rounded border border-blue-200 dark:border-blue-800">
                      <div className="grid grid-cols-3 gap-4 text-sm">
                        <div>
                          <p className="text-gray-600 dark:text-gray-400">Chunks analysés</p>
                          <p className="text-lg font-semibold text-gray-900 dark:text-white">
                            {analysisStatus.chunks_analyzed || 0}
                          </p>
                        </div>
                        <div>
                          <p className="text-gray-600 dark:text-gray-400">Chunks blacklistés</p>
                          <p className="text-lg font-semibold text-red-600 dark:text-red-400">
                            {analysisStatus.chunks_blacklisted || 0}
                          </p>
                        </div>
                        <div>
                          <p className="text-gray-600 dark:text-gray-400">Documents flaggés</p>
                          <p className="text-lg font-semibold text-orange-600 dark:text-orange-400">
                            {analysisStatus.documents_flagged || 0}
                          </p>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {analysisStatus && analysisStatus.status === 'completed' && (
                <div className="mt-6 p-4 bg-green-50 dark:bg-green-900/20 rounded border border-green-200 dark:border-green-800">
                  <div className="flex items-center gap-2 mb-2">
                    <CheckCircle className="w-5 h-5 text-green-600 dark:text-green-400" />
                    <span className="font-semibold text-green-800 dark:text-green-200">
                      Analyse terminée avec succès !
                    </span>
                  </div>
                  <div className="text-sm text-green-700 dark:text-green-300">
                    <p>Durée: {formatDuration(analysisStatus.duration_seconds)}</p>
                    <p>Résultats: {analysisStatus.chunks_blacklisted} chunks blacklistés, {analysisStatus.documents_flagged} documents à réingérer</p>
                  </div>
                </div>
              )}

              {analysisStatus && analysisStatus.status === 'failed' && (
                <div className="mt-6 p-4 bg-red-50 dark:bg-red-900/20 rounded border border-red-200 dark:border-red-800">
                  <div className="flex items-center gap-2 mb-2">
                    <AlertCircle className="w-5 h-5 text-red-600 dark:text-red-400" />
                    <span className="font-semibold text-red-800 dark:text-red-200">
                      Analyse échouée
                    </span>
                  </div>
                  <p className="text-sm text-red-700 dark:text-red-300">
                    {analysisStatus.error_message}
                  </p>
                </div>
              )}
            </div>

            <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-4 border border-blue-200 dark:border-blue-800">
              <div className="flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-blue-600 dark:text-blue-400 mt-0.5" />
                <div className="text-sm">
                  <p className="font-medium text-blue-900 dark:text-blue-100 mb-1">
                    Note : Analyse automatique nocturne
                  </p>
                  <p className="text-blue-800 dark:text-blue-200">
                    Le système lance automatiquement une analyse complète tous les jours à 3h du matin.
                    Utilisez ce bouton uniquement si vous souhaitez une analyse immédiate.
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab 4: History */}
        {activeTab === 'history' && (
          <div className="space-y-6">
            {/* Analysis History */}
            <div className="bg-white dark:bg-gray-800 rounded-lg p-6 border border-gray-200 dark:border-gray-700">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                Historique des Analyses ({analysisHistory.length})
              </h2>

              {loadingHistory ? (
                <div className="flex justify-center py-8">
                  <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 dark:bg-gray-700">
                      <tr>
                        <th className="px-4 py-3 text-left text-gray-600 dark:text-gray-300">Date</th>
                        <th className="px-4 py-3 text-left text-gray-600 dark:text-gray-300">Type</th>
                        <th className="px-4 py-3 text-left text-gray-600 dark:text-gray-300">Durée</th>
                        <th className="px-4 py-3 text-left text-gray-600 dark:text-gray-300">Résultats</th>
                        <th className="px-4 py-3 text-left text-gray-600 dark:text-gray-300">Statut</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                      {analysisHistory.map((run) => (
                        <tr key={run.id} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                          <td className="px-4 py-3 text-gray-900 dark:text-white">
                            {formatDate(run.started_at)}
                          </td>
                          <td className="px-4 py-3">
                            <span className={`px-2 py-1 rounded text-xs ${
                              run.started_by === 'cron'
                                ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
                                : 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200'
                            }`}>
                              {run.run_type}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-gray-900 dark:text-white">
                            {formatDuration(run.duration_seconds)}
                          </td>
                          <td className="px-4 py-3 text-gray-900 dark:text-white">
                            <div className="text-xs">
                              <div>{run.chunks_analyzed} chunks analysés</div>
                              <div className="text-red-600 dark:text-red-400">
                                {run.chunks_blacklisted} blacklistés
                              </div>
                              <div className="text-orange-600 dark:text-orange-400">
                                {run.documents_flagged} docs flaggés
                              </div>
                            </div>
                          </td>
                          <td className="px-4 py-3">
                            <span className={`px-2 py-1 rounded text-xs ${
                              run.status === 'completed'
                                ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                                : run.status === 'failed'
                                ? 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
                                : 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200'
                            }`}>
                              {run.status_label}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Audit Log */}
            <div className="bg-white dark:bg-gray-800 rounded-lg p-6 border border-gray-200 dark:border-gray-700">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                Journal d'Audit ({auditLog.length})
              </h2>

              {loadingAudit ? (
                <div className="flex justify-center py-8">
                  <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
                </div>
              ) : (
                <div className="space-y-3 max-h-96 overflow-y-auto">
                  {auditLog.map((entry) => (
                    <div key={entry.id} className="p-3 bg-gray-50 dark:bg-gray-700 rounded text-sm">
                      <div className="flex items-center justify-between mb-2">
                        <span className={`px-2 py-1 rounded text-xs font-medium ${
                          entry.action === 'blacklist'
                            ? 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
                            : entry.action === 'unblacklist'
                            ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                            : entry.action === 'whitelist'
                            ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200'
                            : 'bg-gray-100 text-gray-800 dark:bg-gray-600 dark:text-gray-200'
                        }`}>
                          {entry.action}
                        </span>
                        <span className="text-xs text-gray-500 dark:text-gray-400">
                          {formatDate(entry.created_at)}
                        </span>
                      </div>

                      {entry.chunk_preview && (
                        <p className="text-xs text-gray-700 dark:text-gray-300 mb-1">
                          {entry.chunk_preview}...
                        </p>
                      )}

                      {entry.document_title && (
                        <p className="text-xs text-gray-700 dark:text-gray-300 mb-1">
                          Document: {entry.document_title}
                        </p>
                      )}

                      <p className="text-xs text-gray-600 dark:text-gray-400">
                        <strong>Raison:</strong> {entry.reason}
                      </p>

                      <p className="text-xs text-gray-500 dark:text-gray-500 mt-1">
                        Décidé par: {entry.decided_by === 'cron' ? '🤖 Worker automatique' : `👤 Admin (${entry.decided_by})`}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Reingestion Modal */}
      {showReingestionModal && selectedDocForReingest && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-2xl w-full mx-4 p-6">
            <h3 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">
              Réingérer le document
            </h3>

            {/* Document Info */}
            <div className="mb-4 p-3 bg-gray-50 dark:bg-gray-700 rounded">
              <p className="text-sm font-medium text-gray-900 dark:text-white">
                Document : {selectedDocForReingest.title}
              </p>
              <p className="text-xs text-gray-600 dark:text-gray-300 mt-1">
                Satisfaction : {selectedDocForReingest.satisfaction_rate !== null
                  ? `${(selectedDocForReingest.satisfaction_rate * 100).toFixed(1)}%`
                  : 'N/A'}
              </p>
            </div>

            {/* AI Recommendations */}
            {selectedDocForReingest.reingestion_reason && (
              <div className="mb-4 p-3 bg-blue-50 dark:bg-blue-900/20 rounded border border-blue-200 dark:border-blue-800">
                <p className="text-sm font-medium text-blue-900 dark:text-blue-200 mb-2">
                  🤖 Recommandation IA :
                </p>
                <p className="text-xs text-blue-800 dark:text-blue-300">
                  {selectedDocForReingest.reingestion_reason}
                </p>
                {selectedDocForReingest.last_ai_analysis?.reingestion_config && (
                  <p className="text-xs text-blue-700 dark:text-blue-400 mt-2">
                    <strong>Config suggérée :</strong> {selectedDocForReingest.last_ai_analysis.reingestion_config}
                  </p>
                )}
              </div>
            )}

            {/* Configuration Dropdowns */}
            <div className="space-y-4 mb-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Moteur OCR (Docling)
                </label>
                <select
                  value={reingestionConfig.ocr_engine}
                  onChange={(e) => setReingestionConfig({
                    ...reingestionConfig,
                    ocr_engine: e.target.value as any
                  })}
                  className="w-full px-3 py-2 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
                >
                  <option value="rapidocr">RapidOCR (Recommandé) - Rapide, multilingue</option>
                  <option value="easyocr">EasyOCR - Standard Docling</option>
                  <option value="tesseract">Tesseract - Haute qualité pour scans</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Moteur VLM (Images)
                </label>
                <select
                  value={reingestionConfig.vlm_engine}
                  onChange={(e) => setReingestionConfig({
                    ...reingestionConfig,
                    vlm_engine: e.target.value as any
                  })}
                  className="w-full px-3 py-2 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
                >
                  <option value="paddleocr-vl">PaddleOCR-VL - Local, rapide</option>
                  <option value="internvl">InternVL - API distant, descriptions riches</option>
                  <option value="none">Aucun - Pas d'extraction d'images</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Stratégie de découpage
                </label>
                <select
                  value={reingestionConfig.chunker_type}
                  onChange={(e) => setReingestionConfig({
                    ...reingestionConfig,
                    chunker_type: e.target.value as any
                  })}
                  className="w-full px-3 py-2 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
                >
                  <option value="hybrid">Hybrid (Recommandé) - Respecte structure</option>
                  <option value="parent_child">Parent-Child - Longs textes</option>
                </select>
              </div>
            </div>

            {/* Warning */}
            <div className="mb-6 p-3 bg-yellow-50 dark:bg-yellow-900/20 rounded border border-yellow-200 dark:border-yellow-800">
              <p className="text-sm text-yellow-800 dark:text-yellow-200">
                ⚠️ L'ancien document sera supprimé et remplacé par une nouvelle version.
                Tous les chunks, images et ratings associés seront perdus.
              </p>
            </div>

            {/* Action Buttons */}
            <div className="flex justify-end gap-3">
              <button
                onClick={() => {
                  setShowReingestionModal(false);
                  setSelectedDocForReingest(null);
                }}
                disabled={reingesting}
                className="px-4 py-2 text-gray-700 dark:text-gray-300 bg-gray-200 dark:bg-gray-700 rounded hover:bg-gray-300 dark:hover:bg-gray-600 disabled:opacity-50"
              >
                Annuler
              </button>
              <button
                onClick={handleConfirmReingest}
                disabled={reingesting}
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
              >
                {reingesting && <Loader2 className="w-4 h-4 animate-spin" />}
                {reingesting ? 'Réingestion en cours...' : 'Confirmer la réingestion'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default QualityManagementPage;
