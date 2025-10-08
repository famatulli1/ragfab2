import { useState } from 'react';
import { Sparkles } from 'lucide-react';
import api from '../api/client';

interface RerankingToggleProps {
  conversationId: string;
  initialValue?: boolean | null;
  onUpdate?: (value: boolean | null) => void;
}

/**
 * Toggle component for per-conversation reranking control
 *
 * Three states:
 * - null (grey): Use global environment variable
 * - true (green): Force enable reranking
 * - false (red): Force disable reranking
 */
export default function RerankingToggle({ conversationId, initialValue = null, onUpdate }: RerankingToggleProps) {
  const [rerankingEnabled, setRerankingEnabled] = useState<boolean | null>(initialValue);
  const [isLoading, setIsLoading] = useState(false);

  const handleToggle = async () => {
    setIsLoading(true);
    try {
      // Cycle through states: null → true → false → null
      let newValue: boolean | null;
      if (rerankingEnabled === null) {
        newValue = true;
      } else if (rerankingEnabled === true) {
        newValue = false;
      } else {
        newValue = null;
      }

      await api.updateConversation(conversationId, { reranking_enabled: newValue });
      setRerankingEnabled(newValue);
      onUpdate?.(newValue);
    } catch (error) {
      console.error('Error updating reranking setting:', error);
    } finally {
      setIsLoading(false);
    }
  };

  // Determine button appearance based on state
  const getButtonState = () => {
    if (rerankingEnabled === null) {
      return {
        bgColor: 'bg-gray-400 dark:bg-gray-600',
        label: 'Reranking: Global',
        title: 'Using global environment variable (click to force enable)',
      };
    } else if (rerankingEnabled === true) {
      return {
        bgColor: 'bg-green-500 dark:bg-green-600',
        label: 'Reranking: ON',
        title: 'Reranking enabled for this conversation (click to disable)',
      };
    } else {
      return {
        bgColor: 'bg-red-500 dark:bg-red-600',
        label: 'Reranking: OFF',
        title: 'Reranking disabled for this conversation (click to use global)',
      };
    }
  };

  const state = getButtonState();

  return (
    <button
      onClick={handleToggle}
      disabled={isLoading}
      title={state.title}
      className={`
        flex items-center gap-2 px-3 py-1.5 rounded-lg text-white text-sm font-medium
        transition-all duration-200
        ${state.bgColor}
        ${isLoading ? 'opacity-50 cursor-not-allowed' : 'hover:opacity-90 cursor-pointer'}
      `}
    >
      <Sparkles className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
      <span>{state.label}</span>
    </button>
  );
}
