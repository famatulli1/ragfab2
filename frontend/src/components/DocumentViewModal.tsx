import React, { useEffect, useRef, useState } from 'react';
import { X } from 'lucide-react';
import api from '../api/client';

interface DocumentViewModalProps {
  documentId: string;
  chunkId: string;
  onClose: () => void;
}

const DocumentViewModal: React.FC<DocumentViewModalProps> = ({ documentId, chunkId, onClose }) => {
  const [document, setDocument] = useState<any>(null);
  const [chunks, setChunks] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const chunkRefs = useRef<{ [key: string]: HTMLDivElement | null }>({});

  useEffect(() => {
    const loadDocument = async () => {
      try {
        const data = await api.getDocumentView(documentId);
        setDocument(data.document);
        setChunks(data.chunks);
        setLoading(false);

        // Scroll vers le chunk après un court délai pour laisser le DOM se mettre à jour
        setTimeout(() => {
          const targetChunk = chunkRefs.current[chunkId];
          if (targetChunk) {
            targetChunk.scrollIntoView({ behavior: 'smooth', block: 'center' });
          }
        }, 100);
      } catch (error) {
        console.error('Error loading document:', error);
        setLoading(false);
      }
    };

    loadDocument();
  }, [documentId, chunkId]);

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div className="bg-white dark:bg-gray-800 rounded-lg p-8">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600 dark:text-gray-400">Chargement du document...</p>
        </div>
      </div>
    );
  }

  if (!document) {
    return null;
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
          <div className="flex-1">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
              {document.title}
            </h2>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
              Source: {document.source}
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
          >
            <X size={24} className="text-gray-500 dark:text-gray-400" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 custom-scrollbar">
          <div className="prose dark:prose-invert max-w-none">
            {chunks.map((chunk) => (
              <div
                key={chunk.id}
                ref={(el) => (chunkRefs.current[chunk.id] = el)}
                className={`mb-4 p-3 rounded-lg transition-all duration-300 ${
                  chunk.id === chunkId
                    ? 'bg-yellow-100 dark:bg-yellow-900/30 border-2 border-yellow-500 shadow-lg'
                    : 'bg-transparent'
                }`}
              >
                <div className="text-sm text-gray-900 dark:text-gray-100 whitespace-pre-wrap">
                  {chunk.content}
                </div>
                {chunk.id === chunkId && (
                  <div className="mt-2 text-xs font-semibold text-yellow-700 dark:text-yellow-400 flex items-center gap-2">
                    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                    </svg>
                    Chunk utilisé pour générer la réponse
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-4 border-t border-gray-200 dark:border-gray-700">
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {chunks.length} chunk{chunks.length > 1 ? 's' : ''} au total
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

export default DocumentViewModal;
