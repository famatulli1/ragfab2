import { Lightbulb, ArrowRight, X } from 'lucide-react';
import { QualityAnalysis, QuestionSuggestion } from '../types';

interface QuestionSuggestionsProps {
  qualityAnalysis: QualityAnalysis;
  onSuggestionClick: (suggestion: string) => void;
  onDismiss?: () => void;
}

/**
 * Composant affichant des suggestions de reformulation pour les questions vagues.
 *
 * Affiché sous la réponse de l'assistant quand l'analyse de qualité
 * détecte une question problématique (too_vague, wrong_vocabulary, etc.)
 *
 * Suit le pattern de ResponseTemplates.tsx avec styling ambre pour différencier.
 */
export default function QuestionSuggestions({
  qualityAnalysis,
  onSuggestionClick,
  onDismiss
}: QuestionSuggestionsProps) {
  // Ne rien afficher si pas de suggestions
  if (!qualityAnalysis.suggestions || qualityAnalysis.suggestions.length === 0) {
    return null;
  }

  // Message d'en-tête selon la classification
  const getHeaderMessage = (): string => {
    switch (qualityAnalysis.classification) {
      case 'too_vague':
        return 'Pour des resultats plus precis, essayez :';
      case 'wrong_vocabulary':
        return 'Vocabulaire metier suggere :';
      case 'missing_context':
        return 'Question avec plus de contexte :';
      case 'out_of_scope':
        return 'Reformulations dans le perimetre :';
      default:
        return 'Suggestions de reformulation :';
    }
  };

  // Icone selon le type de suggestion
  const getSuggestionIcon = (type: QuestionSuggestion['type']) => {
    switch (type) {
      case 'domain_term':
        return <span className="text-amber-600">📚</span>;
      case 'vocabulary':
        return <span className="text-amber-600">🔍</span>;
      case 'clarification':
        return <span className="text-amber-600">❓</span>;
      default:
        return <ArrowRight className="w-4 h-4 text-amber-600" />;
    }
  };

  return (
    <div className="mt-4 p-4 bg-amber-50 border border-amber-200 rounded-lg">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2 text-amber-800">
          <Lightbulb className="w-5 h-5" />
          <span className="font-medium text-sm">{getHeaderMessage()}</span>
        </div>
        {onDismiss && (
          <button
            onClick={onDismiss}
            className="text-amber-600 hover:text-amber-800 p-1 rounded transition-colors"
            title="Fermer les suggestions"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Suggestions */}
      <div className="space-y-2">
        {qualityAnalysis.suggestions.map((suggestion, index) => (
          <button
            key={index}
            onClick={() => onSuggestionClick(suggestion.text)}
            className="
              w-full flex items-start gap-3 p-3
              bg-white border border-amber-200 rounded-lg
              text-left text-sm text-gray-800
              hover:bg-amber-100 hover:border-amber-300
              transition-all duration-200
              group
            "
          >
            {/* Icon */}
            <span className="flex-shrink-0 mt-0.5">
              {getSuggestionIcon(suggestion.type)}
            </span>

            {/* Content */}
            <div className="flex-grow">
              <p className="font-medium text-gray-900 group-hover:text-amber-900">
                {suggestion.text}
              </p>
              {suggestion.reason && (
                <p className="text-xs text-gray-500 mt-1">
                  {suggestion.reason}
                </p>
              )}
              {suggestion.source_document && (
                <p className="text-xs text-amber-600 mt-1 italic">
                  Source: {suggestion.source_document}
                </p>
              )}
            </div>

            {/* Action hint */}
            <span className="flex-shrink-0 text-xs text-amber-600 opacity-0 group-hover:opacity-100 transition-opacity">
              Cliquer pour utiliser
            </span>
          </button>
        ))}
      </div>

      {/* Termes suggeres (si vocabulaire incorrect) */}
      {qualityAnalysis.suggested_terms.length > 0 && (
        <div className="mt-3 pt-3 border-t border-amber-200">
          <p className="text-xs text-amber-700 mb-2">
            Termes metier recommandes :
          </p>
          <div className="flex flex-wrap gap-2">
            {qualityAnalysis.suggested_terms.map((term, index) => (
              <span
                key={index}
                className="
                  px-2 py-1 text-xs font-medium
                  bg-amber-100 text-amber-800 rounded-full
                  border border-amber-300
                "
              >
                {term}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Footer hint */}
      <p className="mt-3 text-xs text-amber-600 text-center">
        Cliquez sur une suggestion pour la copier dans le champ de saisie
      </p>
    </div>
  );
}
