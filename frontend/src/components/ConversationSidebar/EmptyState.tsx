import { MessageSquare, Search, Archive, FolderOpen } from 'lucide-react';
import type { ConversationTab } from '../../types';

interface EmptyStateProps {
  tab: ConversationTab;
  searchQuery?: string;
  onNewConversation?: () => void;
}

export default function EmptyState({
  tab,
  searchQuery,
  onNewConversation,
}: EmptyStateProps) {
  // Search with no results
  if (searchQuery) {
    return (
      <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
        <div className="w-12 h-12 rounded-full bg-gray-800 flex items-center justify-center mb-4">
          <Search size={24} className="text-gray-500" />
        </div>
        <h3 className="text-sm font-medium text-gray-300 mb-2">
          Aucun résultat
        </h3>
        <p className="text-xs text-gray-500 max-w-[200px]">
          Aucune conversation ne correspond à "{searchQuery}"
        </p>
      </div>
    );
  }

  // Archive tab empty
  if (tab === 'archive') {
    return (
      <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
        <div className="w-12 h-12 rounded-full bg-gray-800 flex items-center justify-center mb-4">
          <Archive size={24} className="text-gray-500" />
        </div>
        <h3 className="text-sm font-medium text-gray-300 mb-2">
          Pas d'archives
        </h3>
        <p className="text-xs text-gray-500 max-w-[200px]">
          Vos conversations archivées apparaîtront ici
        </p>
      </div>
    );
  }

  // Universes tab empty
  if (tab === 'universes') {
    return (
      <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
        <div className="w-12 h-12 rounded-full bg-gray-800 flex items-center justify-center mb-4">
          <FolderOpen size={24} className="text-gray-500" />
        </div>
        <h3 className="text-sm font-medium text-gray-300 mb-2">
          Pas de conversations
        </h3>
        <p className="text-xs text-gray-500 max-w-[200px]">
          Créez une conversation pour commencer
        </p>
        {onNewConversation && (
          <button
            onClick={onNewConversation}
            className="mt-4 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-lg transition-colors"
          >
            Nouvelle conversation
          </button>
        )}
      </div>
    );
  }

  // Default empty state (all tab)
  return (
    <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
      <div className="w-12 h-12 rounded-full bg-gray-800 flex items-center justify-center mb-4">
        <MessageSquare size={24} className="text-gray-500" />
      </div>
      <h3 className="text-sm font-medium text-gray-300 mb-2">
        Pas de conversations
      </h3>
      <p className="text-xs text-gray-500 max-w-[200px]">
        Démarrez une nouvelle conversation pour commencer
      </p>
      {onNewConversation && (
        <button
          onClick={onNewConversation}
          className="mt-4 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-lg transition-colors"
        >
          Nouvelle conversation
        </button>
      )}
    </div>
  );
}
