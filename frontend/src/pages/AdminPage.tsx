import { useState, useEffect, useCallback } from 'react';
import { Upload, Trash2, Eye, Moon, Sun, FileText, Users as UsersIcon } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useTheme } from '../App';
import { useDropzone } from 'react-dropzone';
import api from '../api/client';
import UserManagement from '../components/UserManagement';
import UserMenu from '../components/UserMenu';
import type { DocumentStats, Chunk, IngestionJob, User } from '../types';

type TabType = 'documents' | 'users';

type OcrEngine = 'rapidocr' | 'easyocr' | 'tesseract';
type VlmEngine = 'paddleocr-vl' | 'internvl' | 'none';

export default function AdminPage() {
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [activeTab, setActiveTab] = useState<TabType>('documents');
  const [documents, setDocuments] = useState<DocumentStats[]>([]);
  const [selectedDocument, setSelectedDocument] = useState<DocumentStats | null>(null);
  const [chunks, setChunks] = useState<Chunk[]>([]);
  const [uploadingFiles, setUploadingFiles] = useState<Map<string, IngestionJob>>(new Map());
  const [showChunks, setShowChunks] = useState(false);
  const [selectedOcrEngine, setSelectedOcrEngine] = useState<OcrEngine>('rapidocr');
  const [selectedVlmEngine, setSelectedVlmEngine] = useState<VlmEngine>('paddleocr-vl');

  useEffect(() => {
    loadCurrentUser();
    loadDocuments();
  }, []);

  const loadCurrentUser = async () => {
    try {
      const user = await api.getCurrentUser();
      setCurrentUser(user);
    } catch (error) {
      console.error('Error loading current user:', error);
      navigate('/login');
    }
  };

  // Poll les jobs d'ingestion
  useEffect(() => {
    const interval = setInterval(() => {
      uploadingFiles.forEach(async (job, jobId) => {
        if (job.status === 'processing' || job.status === 'pending') {
          try {
            const updatedJob = await api.getIngestionJob(jobId);
            setUploadingFiles(prev => new Map(prev).set(jobId, updatedJob));

            if (updatedJob.status === 'completed') {
              loadDocuments();
            }
          } catch (error) {
            console.error('Error polling job:', error);
          }
        }
      });
    }, 2000);

    return () => clearInterval(interval);
  }, [uploadingFiles]);

  const handleLogout = async () => {
    await api.logout();
    navigate('/login');
  };

  const loadDocuments = async () => {
    try {
      const docs = await api.getDocuments();
      setDocuments(docs);
    } catch (error) {
      console.error('Error loading documents:', error);
    }
  };

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    for (const file of acceptedFiles) {
      try {
        const result = await api.uploadDocument(file, selectedOcrEngine, selectedVlmEngine);
        const job: IngestionJob = {
          id: result.job_id,
          filename: result.filename,
          status: result.status as any,
          progress: 0,
          chunks_created: 0,
          created_at: new Date().toISOString(),
        };
        setUploadingFiles(prev => new Map(prev).set(result.job_id, job));
      } catch (error) {
        console.error('Error uploading file:', error);
        alert(`Erreur lors de l'upload de ${file.name}`);
      }
    }
  }, [selectedOcrEngine, selectedVlmEngine]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'text/markdown': ['.md'],
      'text/plain': ['.txt'],
    },
  });

  const deleteDocument = async (id: string) => {
    if (!confirm('Êtes-vous sûr de vouloir supprimer ce document ?')) return;

    try {
      await api.deleteDocument(id);
      setDocuments(docs => docs.filter(d => d.id !== id));
      if (selectedDocument?.id === id) {
        setSelectedDocument(null);
        setShowChunks(false);
      }
    } catch (error) {
      console.error('Error deleting document:', error);
      alert('Erreur lors de la suppression');
    }
  };

  const viewChunks = async (doc: DocumentStats) => {
    try {
      const chunksData = await api.getDocumentChunks(doc.id);
      setChunks(chunksData);
      setSelectedDocument(doc);
      setShowChunks(true);
    } catch (error) {
      console.error('Error loading chunks:', error);
      alert('Erreur lors du chargement des chunks');
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <div className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-6 py-4">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Administration RAGFab</h1>
          <div className="flex items-center gap-2">
            <button
              onClick={() => navigate('/')}
              className="px-4 py-2 text-sm text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white"
            >
              ← Retour au chat
            </button>
            <button
              onClick={toggleTheme}
              className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700"
            >
              {theme === 'light' ? <Moon size={20} /> : <Sun size={20} />}
            </button>
            {currentUser && (
              <>
                <div className="h-6 w-px bg-gray-300 dark:bg-gray-600 mx-1"></div>
                <UserMenu user={currentUser} onLogout={handleLogout} />
              </>
            )}
          </div>
        </div>
      </div>

      <div className="container mx-auto p-6">
        {/* Tabs */}
        <div className="mb-6">
          <div className="border-b border-gray-200 dark:border-gray-700">
            <nav className="-mb-px flex gap-4">
              <button
                onClick={() => setActiveTab('documents')}
                className={`flex items-center gap-2 px-4 py-3 border-b-2 font-medium text-sm transition ${
                  activeTab === 'documents'
                    ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-300'
                }`}
              >
                <FileText className="h-5 w-5" />
                Documents
              </button>
              <button
                onClick={() => setActiveTab('users')}
                className={`flex items-center gap-2 px-4 py-3 border-b-2 font-medium text-sm transition ${
                  activeTab === 'users'
                    ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-300'
                }`}
              >
                <UsersIcon className="h-5 w-5" />
                Utilisateurs
              </button>
            </nav>
          </div>
        </div>

        {/* Content - Documents Tab */}
        {activeTab === 'documents' && (
          <div className="space-y-6">
            {/* Upload Area */}
            <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
              <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Upload de documents</h2>

              {/* OCR and VLM Engine Selectors */}
              <div className="mb-6 p-4 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                <h3 className="text-sm font-medium mb-3 text-gray-900 dark:text-white">
                  Configuration de l'ingestion
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* OCR Engine Dropdown */}
                  <div>
                    <label htmlFor="ocr-engine" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Moteur OCR (Docling)
                    </label>
                    <select
                      id="ocr-engine"
                      value={selectedOcrEngine}
                      onChange={(e) => setSelectedOcrEngine(e.target.value as OcrEngine)}
                      className="w-full px-3 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    >
                      <option value="rapidocr">RapidOCR (Recommandé) - Rapide, multilingue</option>
                      <option value="easyocr">EasyOCR - Standard Docling</option>
                      <option value="tesseract">Tesseract - Haute qualité pour scans</option>
                    </select>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      Pour extraire le texte des PDFs et images
                    </p>
                  </div>

                  {/* VLM Engine Dropdown */}
                  <div>
                    <label htmlFor="vlm-engine" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Moteur VLM (Images)
                    </label>
                    <select
                      id="vlm-engine"
                      value={selectedVlmEngine}
                      onChange={(e) => setSelectedVlmEngine(e.target.value as VlmEngine)}
                      className="w-full px-3 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    >
                      <option value="paddleocr-vl">PaddleOCR-VL (Recommandé) - Local, rapide</option>
                      <option value="internvl">InternVL - API distant, descriptions riches</option>
                      <option value="none">Aucun - Pas d'extraction d'images</option>
                    </select>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      Pour analyser et décrire les images
                    </p>
                  </div>
                </div>
              </div>

              {/* Dropzone */}
              <div
                {...getRootProps()}
                className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
                  isDragActive
                    ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                    : 'border-gray-300 dark:border-gray-600 hover:border-blue-400'
                }`}
              >
                <input {...getInputProps()} />
                <Upload size={48} className="mx-auto mb-4 text-gray-400" />
                <p className="text-lg mb-2 text-gray-700 dark:text-gray-300">
                  {isDragActive ? 'Déposez les fichiers ici' : 'Glissez-déposez des fichiers ou cliquez pour sélectionner'}
                </p>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  Formats supportés: PDF, DOCX, MD, TXT
                </p>
              </div>

              {/* Uploading Files */}
              {uploadingFiles.size > 0 && (
                <div className="mt-4 space-y-2">
                  <h3 className="font-medium text-gray-900 dark:text-white">Fichiers en cours de traitement</h3>
                  {Array.from(uploadingFiles.values()).map((job) => (
                    <div key={job.id} className="p-3 bg-gray-50 dark:bg-gray-700 rounded">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-sm font-medium text-gray-900 dark:text-white">{job.filename}</span>
                        <span className={`text-xs px-2 py-1 rounded ${
                          job.status === 'completed'
                            ? 'bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-200'
                            : job.status === 'failed'
                            ? 'bg-red-100 text-red-800 dark:bg-red-900/20 dark:text-red-200'
                            : 'bg-blue-100 text-blue-800 dark:bg-blue-900/20 dark:text-blue-200'
                        }`}>
                          {job.status}
                        </span>
                      </div>
                      <div className="w-full bg-gray-200 dark:bg-gray-600 rounded-full h-2">
                        <div
                          className="bg-blue-500 h-2 rounded-full transition-all"
                          style={{ width: `${job.progress}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Documents List */}
            <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
              <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">
                Documents ({documents.length})
              </h2>
              <div className="space-y-2">
                {documents.map((doc) => (
                  <div
                    key={doc.id}
                    className="flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-700 rounded-lg"
                  >
                    <div className="flex-1">
                      <h3 className="font-medium text-gray-900 dark:text-white">{doc.title}</h3>
                      <p className="text-sm text-gray-500 dark:text-gray-400">
                        {doc.chunk_count} chunks • {new Date(doc.created_at).toLocaleDateString('fr-FR')}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => viewChunks(doc)}
                        className="p-2 text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded"
                        title="Voir les chunks"
                      >
                        <Eye size={18} />
                      </button>
                      <button
                        onClick={() => deleteDocument(doc.id)}
                        className="p-2 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded"
                        title="Supprimer"
                      >
                        <Trash2 size={18} />
                      </button>
                    </div>
                  </div>
                ))}
                {documents.length === 0 && (
                  <p className="text-center text-gray-500 dark:text-gray-400 py-8">
                    Aucun document pour le moment
                  </p>
                )}
              </div>
            </div>

            {/* Chunks Modal */}
            {showChunks && selectedDocument && (
              <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
                <div className="bg-white dark:bg-gray-800 rounded-lg max-w-4xl w-full max-h-[80vh] overflow-hidden flex flex-col">
                  <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                    <div className="flex items-center justify-between">
                      <h3 className="text-xl font-bold text-gray-900 dark:text-white">
                        Chunks: {selectedDocument.title}
                      </h3>
                      <button
                        onClick={() => {
                          setShowChunks(false);
                          setSelectedDocument(null);
                        }}
                        className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
                      >
                        ✕
                      </button>
                    </div>
                  </div>
                  <div className="p-6 overflow-y-auto flex-1">
                    <div className="space-y-4">
                      {chunks.map((chunk, idx) => (
                        <div key={chunk.id} className="p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
                          <div className="flex items-center gap-2 mb-2">
                            <span className="text-xs font-medium px-2 py-1 bg-blue-100 text-blue-800 dark:bg-blue-900/20 dark:text-blue-200 rounded">
                              Chunk {idx + 1}
                            </span>
                            {chunk.token_count && (
                              <span className="text-xs text-gray-500 dark:text-gray-400">
                                {chunk.token_count} tokens
                              </span>
                            )}
                          </div>
                          <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">
                            {chunk.content}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Content - Users Tab */}
        {activeTab === 'users' && <UserManagement />}
      </div>
    </div>
  );
}
