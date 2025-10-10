import { useState } from 'react';

interface RerankingToggleProps {
  initialValue?: boolean | null;
  onUpdate?: (value: boolean) => void;
}

/**
 * Simple ON/OFF toggle for reranking control
 *
 * Two states:
 * - true (ON): Reranking enabled
 * - false (OFF): Reranking disabled
 */
export default function RerankingToggle({ initialValue = false, onUpdate }: RerankingToggleProps) {
  // Convert null to false for simple toggle
  const [rerankingEnabled, setRerankingEnabled] = useState<boolean>(initialValue === true);
  const [isLoading, setIsLoading] = useState(false);

  const handleToggle = async () => {
    setIsLoading(true);
    const newValue = !rerankingEnabled;

    try {
      setRerankingEnabled(newValue);
      onUpdate?.(newValue);
    } catch (error) {
      console.error('Error updating reranking setting:', error);
      // Revert on error
      setRerankingEnabled(!newValue);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex items-center gap-3">
      <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
        Recherche approfondie
      </span>
      <button
        onClick={handleToggle}
        disabled={isLoading}
        className={`
          relative inline-flex h-6 w-11 items-center rounded-full
          transition-colors duration-200 ease-in-out
          focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
          ${isLoading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
          ${rerankingEnabled
            ? 'bg-green-500 dark:bg-green-600'
            : 'bg-gray-300 dark:bg-gray-600'
          }
        `}
        role="switch"
        aria-checked={rerankingEnabled}
        aria-label={rerankingEnabled ? 'Recherche approfondie activée' : 'Recherche approfondie désactivée'}
        title={rerankingEnabled ? 'Recherche approfondie activée (cliquez pour désactiver)' : 'Recherche approfondie désactivée (cliquez pour activer)'}
      >
        <span
          className={`
            inline-block h-4 w-4 transform rounded-full bg-white
            transition-transform duration-200 ease-in-out
            ${rerankingEnabled ? 'translate-x-6' : 'translate-x-1'}
          `}
        />
      </button>
    </div>
  );
}
