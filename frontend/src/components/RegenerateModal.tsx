import React, { useState, useMemo } from 'react';
import { X, RefreshCw, BookOpen, ChevronLeft, AlertCircle } from 'lucide-react';
import type { Source } from '../types';

interface RegenerateModalProps {
  isOpen: boolean;
  onClose: () => void;
  onRegenerateClassic: () => void;
  onRegenerateDeep: (documentIds: string[]) => void;
  sources: Source[];
  isLoading: boolean;
}

interface DocumentInfo {
  id: string;
  title: string;
  estimatedTokens: number;
  chunkCount: number;
}

const MAX_TOKENS = 32000;
const RESERVED_TOKENS = 3000; // Pour prompt + réponse

export const RegenerateModal: React.FC<RegenerateModalProps> = ({
  isOpen,
  onClose,
  onRegenerateClassic,
  onRegenerateDeep,
  sources,
  isLoading
}) => {
  const [view, setView] = useState<'choice' | 'documents'>('choice');
  const [selectedDocIds, setSelectedDocIds] = useState<Set<string>>(new Set());

  // Extraire les documents uniques des sources avec estimation des tokens
  const documents = useMemo<DocumentInfo[]>(() => {
    const docMap = new Map<string, DocumentInfo>();

    sources.forEach(source => {
      if (source.document_id && source.document_title) {
        const existing = docMap.get(source.document_id);
        // Estimation: ~4 caractères par token en moyenne
        const estimatedTokens = Math.ceil((source.content?.length || 500) / 4);

        if (existing) {
          existing.chunkCount += 1;
          existing.estimatedTokens += estimatedTokens;
        } else {
          docMap.set(source.document_id, {
            id: source.document_id,
            title: source.document_title,
            estimatedTokens: estimatedTokens,
            chunkCount: 1
          });
        }
      }
    });

    // Multiplier par un facteur pour estimer le document complet
    // (on ne voit que quelques chunks, le doc complet est plus grand)
    return Array.from(docMap.values()).map(doc => ({
      ...doc,
      estimatedTokens: doc.estimatedTokens * Math.max(3, doc.chunkCount * 2)
    }));
  }, [sources]);

  // Calculer les tokens totaux sélectionnés
  const selectedTokens = useMemo(() => {
    return documents
      .filter(doc => selectedDocIds.has(doc.id))
      .reduce((sum, doc) => sum + doc.estimatedTokens, 0);
  }, [documents, selectedDocIds]);

  const availableTokens = MAX_TOKENS - RESERVED_TOKENS;
  const usagePercent = Math.min(100, (selectedTokens / availableTokens) * 100);
  const canProceed = selectedDocIds.size > 0 && selectedTokens <= availableTokens;

  // Auto-sélectionner les documents qui rentrent
  const handleOpenDocuments = () => {
    const newSelected = new Set<string>();
    let tokens = 0;

    for (const doc of documents) {
      if (tokens + doc.estimatedTokens <= availableTokens) {
        newSelected.add(doc.id);
        tokens += doc.estimatedTokens;
      }
    }

    setSelectedDocIds(newSelected);
    setView('documents');
  };

  const toggleDocument = (docId: string) => {
    const newSelected = new Set(selectedDocIds);
    if (newSelected.has(docId)) {
      newSelected.delete(docId);
    } else {
      newSelected.add(docId);
    }
    setSelectedDocIds(newSelected);
  };

  const handleDeepRegenerate = () => {
    onRegenerateDeep(Array.from(selectedDocIds));
  };

  const formatTokens = (tokens: number) => {
    if (tokens >= 1000) {
      return `~${Math.round(tokens / 1000)}K`;
    }
    return `~${tokens}`;
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
          {view === 'documents' ? (
            <button
              onClick={() => setView('choice')}
              className="flex items-center gap-2 text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white"
            >
              <ChevronLeft size={20} />
              <span className="font-semibold">Approfondir avec documents</span>
            </button>
          ) : (
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              Régénérer la réponse
            </h2>
          )}
          <button
            onClick={onClose}
            className="p-1 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700"
          >
            <X size={20} className="text-gray-500" />
          </button>
        </div>

        {/* Content */}
        <div className="p-4">
          {view === 'choice' ? (
            <div className="space-y-3">
              {/* Option 1: Relancer la recherche */}
              <button
                onClick={() => {
                  onRegenerateClassic();
                  onClose();
                }}
                disabled={isLoading}
                className="w-full p-4 text-left rounded-lg border-2 border-gray-200 dark:border-gray-600 hover:border-blue-400 dark:hover:border-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors disabled:opacity-50"
              >
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
                    <RefreshCw size={20} className="text-blue-600 dark:text-blue-400" />
                  </div>
                  <div>
                    <div className="font-medium text-gray-900 dark:text-white">
                      Relancer la recherche
                    </div>
                    <div className="text-sm text-gray-500 dark:text-gray-400">
                      Effectue une nouvelle recherche RAG
                    </div>
                  </div>
                </div>
              </button>

              {/* Option 2: Approfondir avec documents */}
              <button
                onClick={handleOpenDocuments}
                disabled={isLoading || documents.length === 0}
                className="w-full p-4 text-left rounded-lg border-2 border-gray-200 dark:border-gray-600 hover:border-purple-400 dark:hover:border-purple-500 hover:bg-purple-50 dark:hover:bg-purple-900/20 transition-colors disabled:opacity-50"
              >
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-purple-100 dark:bg-purple-900/30 rounded-lg">
                    <BookOpen size={20} className="text-purple-600 dark:text-purple-400" />
                  </div>
                  <div>
                    <div className="font-medium text-gray-900 dark:text-white">
                      Approfondir avec documents complets
                    </div>
                    <div className="text-sm text-gray-500 dark:text-gray-400">
                      Analyse les documents sources en entier
                    </div>
                  </div>
                </div>
              </button>

              {documents.length === 0 && (
                <p className="text-sm text-gray-500 dark:text-gray-400 text-center mt-2">
                  Aucun document source disponible pour l'approfondissement
                </p>
              )}
            </div>
          ) : (
            <div className="space-y-4">
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Sélectionnez les documents à analyser en entier :
              </p>

              {/* Liste des documents */}
              <div className="space-y-2 max-h-60 overflow-y-auto">
                {documents.map(doc => {
                  const isSelected = selectedDocIds.has(doc.id);
                  const wouldExceed = !isSelected &&
                    (selectedTokens + doc.estimatedTokens) > availableTokens;

                  return (
                    <label
                      key={doc.id}
                      className={`flex items-start gap-3 p-3 rounded-lg border-2 cursor-pointer transition-colors ${
                        isSelected
                          ? 'border-purple-400 bg-purple-50 dark:bg-purple-900/20'
                          : wouldExceed
                            ? 'border-gray-200 dark:border-gray-700 opacity-50 cursor-not-allowed'
                            : 'border-gray-200 dark:border-gray-700 hover:border-purple-300'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => !wouldExceed && toggleDocument(doc.id)}
                        disabled={wouldExceed && !isSelected}
                        className="mt-1 h-4 w-4 text-purple-600 rounded border-gray-300 focus:ring-purple-500"
                      />
                      <div className="flex-1 min-w-0">
                        <div className="font-medium text-gray-900 dark:text-white truncate">
                          {doc.title}
                        </div>
                        <div className="text-xs text-gray-500 dark:text-gray-400">
                          {formatTokens(doc.estimatedTokens)} tokens
                          {wouldExceed && !isSelected && (
                            <span className="ml-2 text-amber-600 dark:text-amber-400">
                              (dépasserait la limite)
                            </span>
                          )}
                        </div>
                      </div>
                    </label>
                  );
                })}
              </div>

              {/* Barre de progression des tokens */}
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600 dark:text-gray-400">Contexte utilisé</span>
                  <span className={`font-medium ${
                    usagePercent > 90 ? 'text-red-600' :
                    usagePercent > 70 ? 'text-amber-600' :
                    'text-gray-900 dark:text-white'
                  }`}>
                    {formatTokens(selectedTokens)} / {formatTokens(availableTokens)}
                  </span>
                </div>
                <div className="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                  <div
                    className={`h-full transition-all duration-300 ${
                      usagePercent > 90 ? 'bg-red-500' :
                      usagePercent > 70 ? 'bg-amber-500' :
                      'bg-purple-500'
                    }`}
                    style={{ width: `${usagePercent}%` }}
                  />
                </div>
              </div>

              {selectedTokens > availableTokens && (
                <div className="flex items-center gap-2 p-3 bg-red-50 dark:bg-red-900/20 rounded-lg text-red-700 dark:text-red-400 text-sm">
                  <AlertCircle size={16} />
                  <span>Limite de contexte dépassée. Désélectionnez des documents.</span>
                </div>
              )}

              {/* Bouton d'action */}
              <button
                onClick={handleDeepRegenerate}
                disabled={!canProceed || isLoading}
                className="w-full py-3 px-4 bg-purple-600 hover:bg-purple-700 disabled:bg-gray-400 text-white font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
              >
                {isLoading ? (
                  <>
                    <RefreshCw size={18} className="animate-spin" />
                    Lecture approfondie en cours...
                  </>
                ) : (
                  <>
                    <BookOpen size={18} />
                    Approfondir la réponse
                  </>
                )}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default RegenerateModal;
