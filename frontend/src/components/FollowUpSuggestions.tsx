import React from 'react';
import { Lightbulb, ChevronRight } from 'lucide-react';
import type { FollowUpSuggestion } from '../types';

interface FollowUpSuggestionsProps {
  suggestions: FollowUpSuggestion[];
  onSuggestionClick: (text: string) => void;
}

export const FollowUpSuggestions: React.FC<FollowUpSuggestionsProps> = ({
  suggestions,
  onSuggestionClick
}) => {
  if (!suggestions || suggestions.length === 0) return null;

  return (
    <div className="mt-3 p-3 bg-purple-50 dark:bg-purple-900/20 rounded-lg border border-purple-200 dark:border-purple-800">
      <div className="font-semibold text-purple-800 dark:text-purple-300 mb-2 flex items-center gap-2">
        <Lightbulb size={16} />
        Questions pour approfondir
      </div>
      <div className="space-y-2">
        {suggestions.map((suggestion, index) => (
          <button
            key={index}
            onClick={() => onSuggestionClick(suggestion.text)}
            className="w-full text-left p-2 rounded-lg bg-white dark:bg-gray-800 hover:bg-purple-100 dark:hover:bg-purple-900/40 border border-purple-100 dark:border-purple-800 transition-colors group"
          >
            <div className="flex items-center gap-2">
              <ChevronRight
                size={16}
                className="text-purple-500 group-hover:translate-x-0.5 transition-transform"
              />
              <span className="text-sm text-gray-700 dark:text-gray-300 group-hover:text-purple-700 dark:group-hover:text-purple-300">
                {suggestion.text}
              </span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
};

export default FollowUpSuggestions;
