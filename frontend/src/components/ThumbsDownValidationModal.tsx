import React, { useState } from 'react';
import { X, ThumbsDown, MessageSquare, FileText, AlertCircle, CheckCircle, User } from 'lucide-react';
import type {
  ThumbsDownValidation,
  ThumbsDownClassification,
  AdminAction,
  ValidationUpdate,
} from '../types/thumbsDown';
import { api } from '../api/client';

interface ThumbsDownValidationModalProps {
  validation: ThumbsDownValidation;
  isOpen: boolean;
  onClose: () => void;
  onValidated: (validationId: string) => void;
}

const CLASSIFICATION_LABELS: Record<ThumbsDownClassification, { label: string; color: string; icon: string }> = {
  bad_question: {
    label: 'Question mal formulée',
    color: 'bg-yellow-100 text-yellow-800 border-yellow-300',
    icon: '❓'
  },
  bad_answer: {
    label: 'Réponse incorrecte',
    color: 'bg-red-100 text-red-800 border-red-300',
    icon: '❌'
  },
  missing_sources: {
    label: 'Sources manquantes',
    color: 'bg-orange-100 text-orange-800 border-orange-300',
    icon: '📚'
  },
  unrealistic_expectations: {
    label: 'Attentes hors scope',
    color: 'bg-purple-100 text-purple-800 border-purple-300',
    icon: '🎯'
  }
};

const ACTION_LABELS: Record<AdminAction, { label: string; description: string }> = {
  contact_user: {
    label: 'Accompagner utilisateur',
    description: 'Créer notification pédagogique pour améliorer ses questions'
  },
  mark_for_reingestion: {
    label: 'Marquer pour réingestion',
    description: 'Document contient sources manquantes ou incorrectes'
  },
  ignore: {
    label: 'Ignorer',
    description: 'Thumbs down illégitime ou hors contexte'
  },
  pending: {
    label: 'En attente',
    description: 'Pas d\'action pour le moment'
  }
};

export const ThumbsDownValidationModal: React.FC<ThumbsDownValidationModalProps> = ({
  validation,
  isOpen,
  onClose,
  onValidated
}) => {
  const [adminOverride, setAdminOverride] = useState<ThumbsDownClassification | null>(
    validation.admin_override
  );
  const [adminNotes, setAdminNotes] = useState(validation.admin_notes || '');
  const [adminAction, setAdminAction] = useState<AdminAction>(validation.admin_action);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const finalClassification = adminOverride || validation.ai_classification;
  const classificationInfo = CLASSIFICATION_LABELS[finalClassification];

  const handleValidate = async () => {
    setIsSubmitting(true);
    setError(null);

    try {
      const update: ValidationUpdate = {
        admin_override: adminOverride || undefined,
        admin_notes: adminNotes.trim() || undefined,
        admin_action: adminAction
      };

      await api.validateThumbsDown(validation.id, update);
      onValidated(validation.id);
      onClose();
    } catch (err: any) {
      console.error('Validation error:', err);
      setError(err.response?.data?.detail || 'Erreur lors de la validation');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleClose = () => {
    if (!isSubmitting) {
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-red-100 rounded-lg">
              <ThumbsDown className="w-6 h-6 text-red-600" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-gray-900">
                Validation Thumbs Down
              </h2>
              <p className="text-sm text-gray-500">
                Créé le {new Date(validation.created_at).toLocaleString('fr-FR')}
              </p>
            </div>
          </div>
          <button
            onClick={handleClose}
            disabled={isSubmitting}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Error Display */}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-start space-x-3">
              <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-red-800">Erreur de validation</p>
                <p className="text-sm text-red-600 mt-1">{error}</p>
              </div>
            </div>
          )}

          {/* User Info */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <div className="flex items-center space-x-2 mb-2">
              <User className="w-5 h-5 text-blue-600" />
              <h3 className="font-semibold text-blue-900">Utilisateur</h3>
            </div>
            <div className="space-y-1 text-sm">
              <p>
                <span className="font-medium text-gray-700">Nom :</span>{' '}
                {validation.first_name && validation.last_name
                  ? `${validation.first_name} ${validation.last_name}`
                  : 'N/A'}
              </p>
              <p>
                <span className="font-medium text-gray-700">Email :</span>{' '}
                {validation.user_email}
              </p>
              <p>
                <span className="font-medium text-gray-700">Username :</span>{' '}
                {validation.username}
              </p>
            </div>
          </div>

          {/* Question & Answer */}
          <div className="space-y-4">
            {/* Question */}
            <div className="border border-gray-200 rounded-lg p-4">
              <div className="flex items-center space-x-2 mb-3">
                <MessageSquare className="w-5 h-5 text-gray-600" />
                <h3 className="font-semibold text-gray-900">Question de l'utilisateur</h3>
              </div>
              <p className="text-sm text-gray-700 whitespace-pre-wrap bg-gray-50 p-3 rounded">
                {validation.user_question}
              </p>
            </div>

            {/* Answer */}
            <div className="border border-gray-200 rounded-lg p-4">
              <div className="flex items-center space-x-2 mb-3">
                <FileText className="w-5 h-5 text-gray-600" />
                <h3 className="font-semibold text-gray-900">Réponse de l'assistant</h3>
              </div>
              <p className="text-sm text-gray-700 whitespace-pre-wrap bg-gray-50 p-3 rounded max-h-40 overflow-y-auto">
                {validation.assistant_response}
              </p>
            </div>

            {/* User Feedback */}
            {validation.user_feedback && (
              <div className="border border-orange-200 rounded-lg p-4 bg-orange-50">
                <div className="flex items-center space-x-2 mb-3">
                  <AlertCircle className="w-5 h-5 text-orange-600" />
                  <h3 className="font-semibold text-orange-900">Feedback utilisateur</h3>
                </div>
                <p className="text-sm text-orange-800 italic">"{validation.user_feedback}"</p>
              </div>
            )}

            {/* Sources Used */}
            {validation.sources_used && validation.sources_used.length > 0 && (
              <div className="border border-gray-200 rounded-lg p-4">
                <h3 className="font-semibold text-gray-900 mb-2">
                  Sources utilisées ({validation.sources_used.length})
                </h3>
                <div className="space-y-2">
                  {validation.sources_used.slice(0, 3).map((source: any, idx: number) => (
                    <div key={idx} className="text-xs bg-gray-50 p-2 rounded">
                      <p className="font-medium text-gray-700">{source.title || 'Sans titre'}</p>
                      {source.similarity && (
                        <p className="text-gray-500">Similarité: {(source.similarity * 100).toFixed(1)}%</p>
                      )}
                    </div>
                  ))}
                  {validation.sources_used.length > 3 && (
                    <p className="text-xs text-gray-500 italic">
                      +{validation.sources_used.length - 3} autres sources...
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* AI Analysis */}
          <div className="border-2 border-gray-300 rounded-lg p-4 bg-gray-50">
            <h3 className="font-semibold text-gray-900 mb-4">Analyse IA</h3>

            {/* AI Classification */}
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Classification IA
              </label>
              <div className="flex items-center space-x-3">
                <span className={`px-3 py-1 rounded-full text-sm font-medium border ${classificationInfo.color}`}>
                  {classificationInfo.icon} {classificationInfo.label}
                </span>
                <span className="text-sm text-gray-600">
                  Confiance: <span className="font-semibold">{(validation.ai_confidence * 100).toFixed(0)}%</span>
                </span>
                {validation.needs_admin_review && (
                  <span className="px-2 py-1 bg-yellow-100 text-yellow-800 text-xs rounded-full font-medium">
                    Révision requise
                  </span>
                )}
              </div>
            </div>

            {/* AI Reasoning */}
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Raisonnement de l'IA
              </label>
              <p className="text-sm text-gray-700 bg-white p-3 rounded border border-gray-200">
                {validation.ai_reasoning}
              </p>
            </div>

            {/* Suggested Reformulation */}
            {validation.suggested_reformulation && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Reformulation suggérée
                </label>
                <p className="text-sm text-green-700 bg-green-50 p-3 rounded border border-green-200">
                  💡 {validation.suggested_reformulation}
                </p>
              </div>
            )}
          </div>

          {/* Admin Validation Section */}
          <div className="border-2 border-blue-300 rounded-lg p-4 bg-blue-50">
            <h3 className="font-semibold text-blue-900 mb-4">Validation Admin</h3>

            {/* Admin Override Classification */}
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Override classification (optionnel)
              </label>
              <select
                value={adminOverride || ''}
                onChange={(e) => setAdminOverride(e.target.value ? e.target.value as ThumbsDownClassification : null)}
                disabled={isSubmitting}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="">Utiliser la classification IA</option>
                {Object.entries(CLASSIFICATION_LABELS).map(([key, info]) => (
                  <option key={key} value={key}>
                    {info.icon} {info.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Admin Action */}
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Action admin <span className="text-red-500">*</span>
              </label>
              <select
                value={adminAction}
                onChange={(e) => setAdminAction(e.target.value as AdminAction)}
                disabled={isSubmitting}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                {Object.entries(ACTION_LABELS).map(([key, info]) => (
                  <option key={key} value={key}>
                    {info.label}
                  </option>
                ))}
              </select>
              <p className="text-xs text-gray-500 mt-1">
                {ACTION_LABELS[adminAction].description}
              </p>
            </div>

            {/* Admin Notes */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Notes admin (optionnel)
              </label>
              <textarea
                value={adminNotes}
                onChange={(e) => setAdminNotes(e.target.value)}
                disabled={isSubmitting}
                rows={3}
                placeholder="Commentaires, observations, raisons de l'override..."
                className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
              />
            </div>
          </div>

          {/* Already Validated Notice */}
          {validation.validated_at && (
            <div className="bg-green-50 border border-green-200 rounded-lg p-4 flex items-start space-x-3">
              <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-green-800">
                  Déjà validé le {new Date(validation.validated_at).toLocaleString('fr-FR')}
                </p>
                {validation.validated_by_username && (
                  <p className="text-sm text-green-600">
                    Par: {validation.validated_by_username}
                  </p>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="sticky bottom-0 bg-gray-50 border-t border-gray-200 px-6 py-4 flex items-center justify-end space-x-3">
          <button
            onClick={handleClose}
            disabled={isSubmitting}
            className="px-4 py-2 text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Annuler
          </button>
          <button
            onClick={handleValidate}
            disabled={isSubmitting}
            className="px-4 py-2 text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
          >
            {isSubmitting ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent"></div>
                <span>Validation...</span>
              </>
            ) : (
              <>
                <CheckCircle className="w-4 h-4" />
                <span>Valider</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
