import { useState, useEffect, useCallback } from 'react';
import { Upload, Trash2, Eye, LogOut, Moon, Sun } from 'lucide-react';
import { useTheme } from '../App';
import { useDropzone } from 'react-dropzone';
import api from '../api/client';
import type { DocumentStats, Chunk, IngestionJob } from '../types';

export default function AdminPage() {
  const { theme, toggleTheme } = useTheme();
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [documents, setDocuments] = useState<DocumentStats[]>([]);
  const [selectedDocument, setSelectedDocument] = useState<DocumentStats | null>(null);
  const [chunks, setChunks] = useState<Chunk[]>([]);
  const [uploadingFiles, setUploadingFiles] = useState<Map<string, IngestionJob>>(new Map());
  const [showChunks, setShowChunks] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (token) {
      setIsAuthenticated(true);
      loadDocuments();
    }
  }, []);

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

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.login({ username, password });
      setIsAuthenticated(true);
      loadDocuments();
    } catch (error) {
      alert('Erreur de connexion. Vérifiez vos identifiants.');
    }
  };

  const handleLogout = async () => {
    await api.logout();
    setIsAuthenticated(false);
    setDocuments([]);
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
        const result = await api.uploadDocument(file);
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
  }, []);

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

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center">
        <div className="card p-8 w-full max-w-md">
          <h1 className="text-2xl font-bold mb-6 text-center">Administration RAGFab</h1>
          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">Nom d'utilisateur</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="input"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Mot de passe</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input"
                required
              />
            </div>
            <button type="submit" className="btn-primary w-full">
              Se connecter
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <div className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-6 py-4">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold">Administration RAGFab</h1>
          <div className="flex items-center gap-2">
            <button onClick={toggleTheme} className="btn-ghost">
              {theme === 'light' ? <Moon size={20} /> : <Sun size={20} />}
            </button>
            <button onClick={handleLogout} className="btn-secondary flex items-center gap-2">
              <LogOut size={18} />
              Déconnexion
            </button>
          </div>
        </div>
      </div>

      <div className="container mx-auto p-6">
        {/* Upload Area */}
        <div className="card p-6 mb-6">
          <h2 className="text-xl font-semibold mb-4">Upload de documents</h2>
          <div
            {...getRootProps()}
            className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
              isDragActive
                ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/20'
                : 'border-gray-300 dark:border-gray-600 hover:border-primary-400'
            }`}
          >
            <input {...getInputProps()} />
            <Upload size={48} className="mx-auto mb-4 text-gray-400" />
            <p className="text-lg mb-2">
              {isDragActive
                ? 'Déposez les fichiers ici...'
                : 'Glissez-déposez des fichiers ici, ou cliquez pour sélectionner'}
            </p>
            <p className="text-sm text-gray-500">
              Formats supportés : PDF, DOCX, MD, TXT
            </p>
          </div>

          {/* Upload Progress */}
          {uploadingFiles.size > 0 && (
            <div className="mt-4 space-y-2">
              {Array.from(uploadingFiles.values()).map(job => (
                <div key={job.id} className="p-3 bg-gray-100 dark:bg-gray-800 rounded">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-medium">{job.filename}</span>
                    <span className="text-sm text-gray-600 dark:text-gray-400">
                      {job.status === 'completed' ? '✓ Terminé' :
                       job.status === 'failed' ? '✗ Échoué' :
                       job.status === 'processing' ? `${job.progress}%` : 'En attente...'}
                    </span>
                  </div>
                  {job.status === 'processing' && (
                    <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                      <div
                        className="bg-primary-500 h-2 rounded-full transition-all"
                        style={{ width: `${job.progress}%` }}
                      />
                    </div>
                  )}
                  {job.status === 'completed' && (
                    <p className="text-sm text-green-600 dark:text-green-400">
                      {job.chunks_created} chunks créés
                    </p>
                  )}
                  {job.error_message && (
                    <p className="text-sm text-red-600 dark:text-red-400">{job.error_message}</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Documents List */}
        <div className="card p-6">
          <h2 className="text-xl font-semibold mb-4">Documents ({documents.length})</h2>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-200 dark:border-gray-700">
                  <th className="text-left py-3 px-4">Titre</th>
                  <th className="text-left py-3 px-4">Source</th>
                  <th className="text-right py-3 px-4">Chunks</th>
                  <th className="text-right py-3 px-4">Date</th>
                  <th className="text-right py-3 px-4">Actions</th>
                </tr>
              </thead>
              <tbody>
                {documents.map(doc => (
                  <tr key={doc.id} className="border-b border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50">
                    <td className="py-3 px-4 font-medium">{doc.title}</td>
                    <td className="py-3 px-4 text-sm text-gray-600 dark:text-gray-400">{doc.source}</td>
                    <td className="py-3 px-4 text-right">{doc.chunk_count}</td>
                    <td className="py-3 px-4 text-right text-sm text-gray-600 dark:text-gray-400">
                      {new Date(doc.created_at).toLocaleDateString()}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => viewChunks(doc)}
                          className="btn-ghost p-1"
                          title="Voir les chunks"
                        >
                          <Eye size={18} />
                        </button>
                        <button
                          onClick={() => deleteDocument(doc.id)}
                          className="btn-ghost p-1 text-red-500 hover:text-red-600"
                          title="Supprimer"
                        >
                          <Trash2 size={18} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Chunks Modal */}
      {showChunks && selectedDocument && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="card p-6 max-w-4xl w-full max-h-[80vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold">
                Chunks de : {selectedDocument.title}
              </h2>
              <button
                onClick={() => setShowChunks(false)}
                className="btn-secondary"
              >
                Fermer
              </button>
            </div>

            <div className="space-y-4">
              {chunks.map((chunk) => (
                <div key={chunk.id} className="p-4 bg-gray-50 dark:bg-gray-800 rounded">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium">Chunk #{chunk.chunk_index}</span>
                    <span className="text-sm text-gray-600 dark:text-gray-400">
                      {chunk.token_count} tokens
                    </span>
                  </div>
                  <p className="text-sm whitespace-pre-wrap">{chunk.content}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
