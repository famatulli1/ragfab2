import { useState } from 'react';
import { Loader2 } from 'lucide-react';
import { api } from '../api/client';

interface ResponseTemplate {
  id: string;
  name: string;
  display_name: string;
  icon: string;
  description?: string;
}

interface ResponseTemplatesProps {
  originalResponse: string;
  conversationId?: string;
  messageId?: string;
  templates: ResponseTemplate[];
  onFormatted?: (formattedResponse: string, templateName: string) => void;
}

export default function ResponseTemplates({
  originalResponse,
  conversationId,
  messageId,
  templates,
  onFormatted
}: ResponseTemplatesProps) {
  const [loading, setLoading] = useState<string | null>(null);

  const handleApplyTemplate = async (templateId: string, templateName: string) => {
    setLoading(templateId);

    try {
      const result = await api.applyResponseTemplate(templateId, {
        original_response: originalResponse,
        conversation_id: conversationId,
        message_id: messageId
      });

      // Appeler le callback parent pour recharger la version sauvegardée
      if (onFormatted) {
        onFormatted(result.formatted_response, templateName);
      }
    } catch (error) {
      console.error('Error applying template:', error);
      alert('Erreur lors de l\'application du template');
    } finally {
      setLoading(null);
    }
  };

  if (templates.length === 0) return null;

  return (
    <div className="mt-4 space-y-3">
      {/* Boutons de templates */}
      <div className="flex flex-wrap gap-2 items-center">
        <span className="text-sm text-gray-600 font-medium">Formater pour ITOP:</span>
        {templates.map(template => (
          <button
            key={template.id}
            onClick={() => handleApplyTemplate(template.id, template.display_name)}
            disabled={loading !== null}
            className={`
              inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium
              transition-all duration-200
              ${loading === template.id
                ? 'bg-blue-500 text-white cursor-wait'
                : 'bg-blue-50 text-blue-700 hover:bg-blue-100 hover:shadow-sm'
              }
              ${loading && loading !== template.id ? 'opacity-50 cursor-not-allowed' : ''}
              disabled:opacity-50 disabled:cursor-not-allowed
            `}
            title={template.description}
          >
            {loading === template.id ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <span>{template.icon}</span>
            )}
            <span>{template.display_name}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
