import React, { useEffect, useState } from 'react';
import { X, Download, Loader2, ZoomIn, ZoomOut, Maximize2, ChevronLeft, ChevronRight } from 'lucide-react';
import { Document, Page, pdfjs } from 'react-pdf';

// Configure PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

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
  const [numPages, setNumPages] = useState<number>(0);
  const [pageNumber, setPageNumber] = useState<number>(1);
  const [scale, setScale] = useState<number>(1.0);
  const [containerWidth, setContainerWidth] = useState<number>(0);
  const [chunkBbox, setChunkBbox] = useState<any>(null);
  const [targetPageNumber, setTargetPageNumber] = useState<number>(1);
  const [pageHeight, setPageHeight] = useState<number>(0);

  // Ref for container to calculate responsive scale
  const containerRef = React.useRef<HTMLDivElement>(null);

  // Update container width on mount and resize
  useEffect(() => {
    const updateWidth = () => {
      if (containerRef.current) {
        setContainerWidth(containerRef.current.offsetWidth - 40); // Subtract padding
      }
    };

    updateWidth();
    window.addEventListener('resize', updateWidth);
    return () => window.removeEventListener('resize', updateWidth);
  }, []);

  useEffect(() => {
    const loadPdfWithMetadata = async () => {
      try {
        setLoading(true);
        setError(null);

        // Récupérer le token JWT depuis localStorage
        const token = localStorage.getItem('access_token');
        if (!token) {
          throw new Error('Non authentifié. Veuillez vous reconnecter.');
        }

        // Étape 1: Fetch metadata du chunk (page_number, bbox)
        console.log('📍 Fetching chunk metadata...');
        const metadataResponse = await fetch(
          `/api/documents/${documentId}/chunks/${chunkId}/metadata`,
          {
            headers: {
              'Authorization': `Bearer ${token}`,
            },
          }
        );

        if (metadataResponse.ok) {
          const metadata = await metadataResponse.json();
          console.log('✅ Chunk metadata:', metadata);

          // Stocker le numéro de page cible et le bbox
          setTargetPageNumber(metadata.page_number || 1);
          setChunkBbox(metadata.bbox);
        } else {
          console.warn('⚠️ Could not fetch chunk metadata, using default page 1');
        }

        // Étape 2: Fetch le PDF avec authentification
        console.log('📄 Fetching annotated PDF...');
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

    loadPdfWithMetadata();

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

  const onDocumentLoadSuccess = ({ numPages }: { numPages: number }) => {
    setNumPages(numPages);
    // Navigate directly to the chunk's page
    setPageNumber(Math.min(targetPageNumber, numPages));
    console.log(`📍 Navigated to page ${targetPageNumber} (total: ${numPages})`);
  };

  const onDocumentLoadError = (error: Error) => {
    console.error('PDF.js load error:', error);
    setError('Erreur lors du chargement du PDF. Le fichier est peut-être corrompu.');
  };

  const handleZoomIn = () => {
    setScale(prev => Math.min(prev + 0.2, 3.0));
  };

  const handleZoomOut = () => {
    setScale(prev => Math.max(prev - 0.2, 0.5));
  };

  const handleFitToWidth = () => {
    // Calculate scale to fit page width to container
    if (containerWidth > 0) {
      // Default PDF page width is ~612 points (8.5 inches at 72 DPI)
      const defaultPageWidth = 612;
      const newScale = containerWidth / defaultPageWidth;
      setScale(Math.min(Math.max(newScale, 0.5), 3.0));
    } else {
      setScale(1.0);
    }
  };

  const handlePreviousPage = () => {
    setPageNumber(prev => Math.max(prev - 1, 1));
  };

  const handleNextPage = () => {
    setPageNumber(prev => Math.min(prev + 1, numPages));
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-90 flex items-center justify-center z-[60] p-4">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-2xl w-full max-w-6xl max-h-[95vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700 flex-shrink-0">
          <div className="flex-1">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
              PDF Annoté - {documentTitle}
            </h2>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
              Chunks sources surlignés en jaune
            </p>
          </div>

          <div className="flex items-center gap-2">
            {pdfUrl && !error && (
              <>
                {/* Zoom Controls */}
                <div className="flex items-center gap-1 bg-gray-100 dark:bg-gray-700 rounded-lg p-1">
                  <button
                    onClick={handleZoomOut}
                    className="p-1.5 hover:bg-gray-200 dark:hover:bg-gray-600 rounded transition-colors"
                    title="Zoom arrière"
                    disabled={scale <= 0.5}
                  >
                    <ZoomOut size={16} className="text-gray-700 dark:text-gray-300" />
                  </button>
                  <button
                    onClick={handleFitToWidth}
                    className="px-2 py-1.5 hover:bg-gray-200 dark:hover:bg-gray-600 rounded transition-colors"
                    title="Ajuster à la largeur"
                  >
                    <Maximize2 size={16} className="text-gray-700 dark:text-gray-300" />
                  </button>
                  <button
                    onClick={handleZoomIn}
                    className="p-1.5 hover:bg-gray-200 dark:hover:bg-gray-600 rounded transition-colors"
                    title="Zoom avant"
                    disabled={scale >= 3.0}
                  >
                    <ZoomIn size={16} className="text-gray-700 dark:text-gray-300" />
                  </button>
                  <span className="px-2 text-sm text-gray-600 dark:text-gray-400 min-w-[60px] text-center">
                    {Math.round(scale * 100)}%
                  </span>
                </div>

                {/* Download Button */}
                <button
                  onClick={handleDownload}
                  className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors text-sm font-medium"
                  title="Télécharger le PDF annoté"
                >
                  <Download size={18} />
                  <span className="hidden sm:inline">Télécharger</span>
                </button>
              </>
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
        <div
          ref={containerRef}
          className="flex-1 overflow-auto p-4 custom-scrollbar bg-gray-50 dark:bg-gray-900"
        >
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
              <div className="text-center bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-8 max-w-2xl">
                <div className="text-yellow-600 dark:text-yellow-400 text-4xl mb-4">📄</div>
                <h3 className="text-lg font-semibold text-yellow-800 dark:text-yellow-300 mb-2">
                  PDF original non disponible
                </h3>
                <p className="text-yellow-600 dark:text-yellow-400 mb-4">
                  Le fichier PDF source n'est pas disponible sur le serveur.
                  Cela peut arriver pour des documents anciens ingérés avant la mise à jour.
                </p>

                {error.includes('404') ? (
                  <div className="bg-white dark:bg-gray-800 rounded-lg p-6 mt-4">
                    <h4 className="font-semibold text-gray-900 dark:text-white mb-2">💡 Solutions :</h4>
                    <ul className="text-left text-sm text-gray-700 dark:text-gray-300 space-y-2">
                      <li>• <strong>Option 1</strong> : Demandez à un administrateur de réuploader le document via l'interface admin</li>
                      <li>• <strong>Option 2</strong> : Le contenu textuel est toujours disponible dans la vue document (fermer cette modale)</li>
                      <li>• <strong>Pour info</strong> : Les nouveaux documents uploadés auront le PDF disponible automatiquement</li>
                    </ul>
                  </div>
                ) : error.includes('authentifié') ? (
                  <button
                    onClick={() => window.location.href = '/login'}
                    className="mt-4 px-4 py-2 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700 transition-colors"
                  >
                    Se reconnecter
                  </button>
                ) : (
                  <p className="text-sm text-gray-600 dark:text-gray-400 mt-2">
                    Détails : {error}
                  </p>
                )}
              </div>
            </div>
          )}

          {pdfUrl && !loading && !error && (
            <div className="flex flex-col items-center">
              <Document
                file={pdfUrl}
                onLoadSuccess={onDocumentLoadSuccess}
                onLoadError={onDocumentLoadError}
                loading={
                  <div className="flex items-center justify-center py-12">
                    <Loader2 className="animate-spin h-8 w-8 text-blue-600" />
                  </div>
                }
              >
                {/* Wrapper pour positionner l'overlay */}
                <div className="relative inline-block">
                  <Page
                    pageNumber={pageNumber}
                    scale={scale}
                    renderTextLayer={true}
                    renderAnnotationLayer={true}
                    loading={
                      <div className="flex items-center justify-center py-12">
                        <Loader2 className="animate-spin h-8 w-8 text-blue-600" />
                      </div>
                    }
                    className="shadow-lg"
                    onLoadSuccess={(page) => {
                      // Store page height for bbox conversion
                      setPageHeight(page.height);
                    }}
                  />

                  {/* Overlay de highlighting (si bbox disponible sur cette page) */}
                  {chunkBbox && targetPageNumber === pageNumber && (
                    <div
                      className="absolute pointer-events-none border-2 border-yellow-400 bg-yellow-300 bg-opacity-30"
                      style={{
                        // Docling bbox: origin bottom-left (l, t, r, b)
                        // Convert to top-left origin for CSS
                        left: `${chunkBbox.l * scale}px`,
                        top: `${(pageHeight - chunkBbox.t) * scale}px`,
                        width: `${(chunkBbox.r - chunkBbox.l) * scale}px`,
                        height: `${(chunkBbox.t - chunkBbox.b) * scale}px`,
                      }}
                      title="Chunk source surligné"
                    />
                  )}
                </div>
              </Document>

              {/* Page Navigation */}
              {numPages > 1 && (
                <div className="flex items-center gap-4 mt-4 bg-white dark:bg-gray-800 rounded-lg shadow-md px-4 py-2">
                  <button
                    onClick={handlePreviousPage}
                    disabled={pageNumber <= 1}
                    className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    title="Page précédente"
                  >
                    <ChevronLeft size={20} className="text-gray-700 dark:text-gray-300" />
                  </button>

                  <span className="text-sm text-gray-700 dark:text-gray-300 min-w-[100px] text-center">
                    Page {pageNumber} / {numPages}
                  </span>

                  <button
                    onClick={handleNextPage}
                    disabled={pageNumber >= numPages}
                    className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    title="Page suivante"
                  >
                    <ChevronRight size={20} className="text-gray-700 dark:text-gray-300" />
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-4 border-t border-gray-200 dark:border-gray-700 flex-shrink-0">
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
