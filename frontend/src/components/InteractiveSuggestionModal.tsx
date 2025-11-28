import { useState } from 'react';
import { Lightbulb, ArrowRight, Send, X, Edit3, AlertTriangle } from 'lucide-react';
import type { PreAnalyzeResponse, QuestionSuggestion, QuestionClassification } from '../types';

interface InteractiveSuggestionModalProps {
  preAnalysis: PreAnalyzeResponse;
  onUseSuggestion: (question: string) => void;
  onSendAnyway: () => void;
  onCancel: () => void;
  isLoading?: boolean;
}

/**
 * Modal interactif affiche avant l'envoi de la question.
 *
 * Apparait quand pre-analyze detecte une question problematique
 * et que l'utilisateur est en mode "interactive".
 */
export default function InteractiveSuggestionModal({
  preAnalysis,
  onUseSuggestion,
  onSendAnyway,
  onCancel,
  isLoading = false
}: InteractiveSuggestionModalProps) {
  const [editedQuestion, setEditedQuestion] = useState(preAnalysis.original_question);
  const [isEditing, setIsEditing] = useState(false);

  // Message selon la classification
  const getClassificationMessage = (classification?: QuestionClassification): { title: string; description: string } => {
    switch (classification) {
      case 'too_vague':
        return {
          title: 'Question un peu vague',
          description: 'Votre question pourrait beneficier de plus de precision pour obtenir une reponse pertinente.'
        };
      case 'wrong_vocabulary':
        return {
          title: 'Vocabulaire a ajuster',
          description: 'Des termes metier specifiques pourraient ameliorer la recherche dans notre base.'
        };
      case 'missing_context':
        return {
          title: 'Contexte manquant',
          description: 'Un peu plus de contexte aiderait a mieux comprendre votre besoin.'
        };
      case 'out_of_scope':
        return {
          title: 'Question hors perimetre',
          description: 'Cette question semble sortir du perimetre de notre base documentaire.'
        };
      default:
        return {
          title: 'Suggestion d\'amelioration',
          description: 'Nous avons des suggestions pour ameliorer votre question.'
        };
    }
  };

  // Icone selon le type de suggestion
  const getSuggestionIcon = (type: QuestionSuggestion['type']) => {
    switch (type) {
      case 'domain_term':
        return <span className="text-blue-600">📚</span>;
      case 'vocabulary':
        return <span className="text-blue-600">🔍</span>;
      case 'clarification':
        return <span className="text-blue-600">❓</span>;
      default:
        return <ArrowRight className="w-4 h-4 text-blue-600" />;
    }
  };

  const { title, description } = getClassificationMessage(preAnalysis.classification);

  const handleSuggestionClick = (suggestion: QuestionSuggestion) => {
    if (isEditing) {
      setEditedQuestion(suggestion.text);
    } else {
      onUseSuggestion(suggestion.text);
    }
  };

  const handleSendEdited = () => {
    if (editedQuestion.trim()) {
      onUseSuggestion(editedQuestion.trim());
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="p-5 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2.5 bg-amber-100 dark:bg-amber-900/30 rounded-full">
                <Lightbulb className="w-5 h-5 text-amber-600 dark:text-amber-400" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                  {title}
                </h2>
                <p className="text-sm text-gray-600 dark:text-gray-400 mt-0.5">
                  {description}
                </p>
              </div>
            </div>
            <button
              onClick={onCancel}
              className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 p-1 rounded transition-colors"
              title="Fermer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {/* Question originale */}
          <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">
                Votre question
              </span>
              <button
                onClick={() => setIsEditing(!isEditing)}
                className={`
                  flex items-center gap-1.5 text-xs px-2 py-1 rounded-md transition-colors
                  ${isEditing
                    ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
                    : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-gray-200 dark:hover:bg-gray-600'}
                `}
              >
                <Edit3 className="w-3 h-3" />
                {isEditing ? 'Mode edition' : 'Modifier'}
              </button>
            </div>
            {isEditing ? (
              <textarea
                value={editedQuestion}
                onChange={(e) => setEditedQuestion(e.target.value)}
                className="w-full px-3 py-2 text-sm bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
                rows={3}
                autoFocus
              />
            ) : (
              <p className="text-gray-800 dark:text-gray-200 text-sm">
                "{preAnalysis.original_question}"
              </p>
            )}
          </div>

          {/* Intent detecte */}
          {preAnalysis.detected_intent && (
            <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
              <span className="font-medium">Intention detectee:</span>
              <span className="px-2 py-0.5 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 rounded text-xs">
                {preAnalysis.detected_intent}
              </span>
            </div>
          )}

          {/* Suggestions */}
          {preAnalysis.suggestions.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
                Suggestions de reformulation
              </h3>
              <div className="space-y-2">
                {preAnalysis.suggestions.map((suggestion, index) => (
                  <button
                    key={index}
                    onClick={() => handleSuggestionClick(suggestion)}
                    disabled={isLoading}
                    className="
                      w-full flex items-start gap-3 p-3
                      bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg
                      text-left text-sm text-gray-800 dark:text-gray-200
                      hover:bg-blue-50 dark:hover:bg-blue-900/20 hover:border-blue-300 dark:hover:border-blue-700
                      transition-all duration-200
                      group disabled:opacity-50 disabled:cursor-not-allowed
                    "
                  >
                    <span className="flex-shrink-0 mt-0.5">
                      {getSuggestionIcon(suggestion.type)}
                    </span>
                    <div className="flex-grow min-w-0">
                      <p className="font-medium group-hover:text-blue-700 dark:group-hover:text-blue-400">
                        {suggestion.text}
                      </p>
                      {suggestion.reason && (
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                          {suggestion.reason}
                        </p>
                      )}
                      {suggestion.source_document && (
                        <p className="text-xs text-blue-600 dark:text-blue-400 mt-1 italic">
                          Source: {suggestion.source_document}
                        </p>
                      )}
                    </div>
                    <span className="flex-shrink-0 text-xs text-blue-600 dark:text-blue-400 opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
                      {isEditing ? 'Copier' : 'Utiliser'}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Termes extraits */}
          {preAnalysis.extracted_terms.length > 0 && (
            <div className="pt-3 border-t border-gray-200 dark:border-gray-700">
              <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">
                Termes metier detectes dans la base :
              </p>
              <div className="flex flex-wrap gap-2">
                {preAnalysis.extracted_terms.map((term, index) => (
                  <span
                    key={index}
                    className="px-2 py-1 text-xs font-medium bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-400 rounded-full border border-green-200 dark:border-green-800"
                  >
                    {term}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer avec actions */}
        <div className="p-5 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
          <div className="flex items-center justify-between gap-3">
            {/* Info de confiance */}
            {preAnalysis.confidence !== undefined && (
              <div className="flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400">
                <AlertTriangle className="w-3.5 h-3.5" />
                <span>Confiance: {Math.round(preAnalysis.confidence * 100)}%</span>
              </div>
            )}

            <div className="flex items-center gap-3 ml-auto">
              {/* Bouton annuler */}
              <button
                onClick={onCancel}
                disabled={isLoading}
                className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-600 transition-colors disabled:opacity-50"
              >
                Annuler
              </button>

              {/* Bouton envoyer quand meme */}
              <button
                onClick={onSendAnyway}
                disabled={isLoading}
                className="px-4 py-2 text-sm font-medium text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg hover:bg-amber-100 dark:hover:bg-amber-900/30 transition-colors disabled:opacity-50"
              >
                Envoyer quand meme
              </button>

              {/* Bouton envoyer modifie (si en mode edition) */}
              {isEditing && (
                <button
                  onClick={handleSendEdited}
                  disabled={isLoading || !editedQuestion.trim()}
                  className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Send className="w-4 h-4" />
                  Envoyer la version modifiee
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
