import React, { useEffect, useState } from 'react';
import { X, Download, Loader2 } from 'lucide-react';

interface PdfViewerModalProps {
  documentId: string;
  chunkId: string;
  documentTitle: string;
  onClose: () => void;
}

const PdfViewerModal: React.FC<PdfViewerModalProps> = ({
  documentId,
  chunkId,
  documentTitle,
  onClose,
}) => {
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadPdf = async () => {
      try {
        setLoading(true);
        setError(null);

        // Récupérer le token JWT depuis localStorage
        const token = localStorage.getItem('access_token');
        if (!token) {
          throw new Error('Non authentifié. Veuillez vous reconnecter.');
        }

        // Fetch le PDF avec authentification
        const response = await fetch(
          `/api/documents/${documentId}/annotated-pdf?chunk_ids=${chunkId}`,
          {
            headers: {
              'Authorization': `Bearer ${token}`,
            },
          }
        );

        if (!response.ok) {
          // Essayer de récupérer le message d'erreur du backend
          let errorMessage = response.statusText;
          try {
            const errorData = await response.json();
            errorMessage = errorData.detail || errorData.message || errorMessage;
          } catch {
            // Si la réponse n'est pas du JSON, utiliser statusText
          }

          if (response.status === 401 || response.status === 403) {
            throw new Error('Session expirée. Veuillez vous reconnecter.');
          }
          throw new Error(`Erreur ${response.status}: ${errorMessage}`);
        }

        // Créer un blob URL depuis la réponse
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        setPdfUrl(url);
        setLoading(false);
      } catch (err) {
        console.error('Error loading PDF:', err);
        const errorMessage = err instanceof Error ? err.message : 'Erreur inconnue';
        console.error('Full error details:', {
          message: errorMessage,
          documentId,
          chunkId,
          error: err
        });
        setError(errorMessage);
        setLoading(false);
      }
    };

    loadPdf();

    // Cleanup: révoquer le blob URL quand le composant est démonté
    return () => {
      if (pdfUrl) {
        URL.revokeObjectURL(pdfUrl);
      }
    };
  }, [documentId, chunkId]);

  const handleDownload = () => {
    if (pdfUrl) {
      const link = document.createElement('a');
      link.href = pdfUrl;
      link.download = `${documentTitle}_annotated.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-2xl w-full max-w-6xl max-h-[95vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
          <div className="flex-1">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
              PDF Annoté - {documentTitle}
            </h2>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
              Chunks sources surlignés en jaune
            </p>
          </div>

          <div className="flex items-center gap-2">
            {pdfUrl && (
              <button
                onClick={handleDownload}
                className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors text-sm font-medium"
                title="Télécharger le PDF annoté"
              >
                <Download size={18} />
                <span className="hidden sm:inline">Télécharger</span>
              </button>
            )}

            <button
              onClick={onClose}
              className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
            >
              <X size={24} className="text-gray-500 dark:text-gray-400" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-hidden p-4">
          {loading && (
            <div className="flex items-center justify-center h-full">
              <div className="text-center">
                <Loader2 className="animate-spin h-12 w-12 text-blue-600 mx-auto mb-4" />
                <p className="text-gray-600 dark:text-gray-400">Chargement du PDF annoté...</p>
              </div>
            </div>
          )}

          {error && (
            <div className="flex items-center justify-center h-full">
              <div className="text-center bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-8 max-w-md">
                <div className="text-red-600 dark:text-red-400 text-4xl mb-4">⚠️</div>
                <h3 className="text-lg font-semibold text-red-800 dark:text-red-300 mb-2">
                  Erreur de chargement
                </h3>
                <p className="text-red-600 dark:text-red-400">{error}</p>
                {error.includes('authentifié') && (
                  <button
                    onClick={() => window.location.href = '/login'}
                    className="mt-4 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
                  >
                    Se reconnecter
                  </button>
                )}
              </div>
            </div>
          )}

          {pdfUrl && !loading && !error && (
            <iframe
              src={pdfUrl}
              className="w-full h-full border-0 rounded-lg"
              title="PDF Annoté"
            />
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-4 border-t border-gray-200 dark:border-gray-700">
          <p className="text-sm text-gray-500 dark:text-gray-400">
            💡 Les chunks utilisés pour générer la réponse sont surlignés en jaune dans le PDF
          </p>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            Fermer
          </button>
        </div>
      </div>
    </div>
  );
};

export default PdfViewerModal;
