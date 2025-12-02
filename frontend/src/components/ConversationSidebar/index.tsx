import { useState, useEffect, useCallback } from 'react';
import type {
  ConversationWithStats,
  ConversationTab,
  ConversationStats,
  ProductUniverse,
  ConversationSearchResult,
  SharedFavorite,
} from '../../types';
import api from '../../api/client';
import SidebarHeader from './SidebarHeader';
import SearchBar from './SearchBar';
import FilterTabs from './FilterTabs';
import ConversationGroup, { TimeGroupedList } from './ConversationGroup';
import SidebarFooter from './SidebarFooter';
import EmptyState from './EmptyState';
import FavoritesList from './FavoritesList';
import FavoriteDetailModal from './FavoriteDetailModal';
import { groupConversationsByTime, groupConversationsByUniverse } from './utils';

interface ConversationSidebarProps {
  isOpen: boolean;
  conversations: ConversationWithStats[];
  currentConversation: ConversationWithStats | null;
  onSelectConversation: (conv: ConversationWithStats) => void;
  onNewConversation: () => void;
  onRenameConversation: (id: string, newTitle: string) => Promise<void>;
  onDeleteConversation: (id: string) => Promise<void>;
  onArchiveConversation: (id: string) => Promise<void>;
  onUnarchiveConversation: (id: string) => Promise<void>;
  onOpenSettings: () => void;
  onRefreshConversations: () => void;
  onReloadConversations?: () => Promise<void>;
  username?: string;
  universes?: ProductUniverse[];
  currentUniverseId?: string;
}

export default function ConversationSidebar({
  isOpen,
  conversations,
  currentConversation,
  onSelectConversation,
  onNewConversation,
  onRenameConversation,
  onDeleteConversation,
  onArchiveConversation,
  onUnarchiveConversation,
  onOpenSettings,
  onRefreshConversations: _onRefreshConversations,
  onReloadConversations,
  username,
  universes = [],
  currentUniverseId,
}: ConversationSidebarProps) {
  // Local state
  const [activeTab, setActiveTab] = useState<ConversationTab>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<ConversationSearchResult[] | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [stats, setStats] = useState<ConversationStats | null>(null);
  const [editingConversation, setEditingConversation] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');

  // Favorites state
  const [favoritesCount, setFavoritesCount] = useState(0);
  const [selectedFavorite, setSelectedFavorite] = useState<SharedFavorite | null>(null);

  // Load conversation stats - refresh when conversations array changes or archive status changes
  const archivedCount = conversations.filter(c => c.is_archived).length;
  const activeCount = conversations.filter(c => !c.is_archived).length;

  useEffect(() => {
    const loadStats = async () => {
      try {
        const data = await api.getConversationStats();
        setStats(data);
      } catch (error) {
        console.error('Failed to load conversation stats:', error);
      }
    };
    loadStats();
  }, [conversations.length, archivedCount, activeCount]);

  // Load favorites count - filtered by currently selected universe
  useEffect(() => {
    const loadFavoritesCount = async () => {
      try {
        // Si pas d'univers sélectionné, afficher 0
        if (!currentUniverseId) {
          setFavoritesCount(0);
          return;
        }
        const response = await api.getFavoritesCount([currentUniverseId]);
        setFavoritesCount(response.total);
      } catch (error) {
        console.error('Failed to load favorites count:', error);
        setFavoritesCount(0);
      }
    };
    loadFavoritesCount();
  }, [currentUniverseId]); // Reload when selected universe changes

  // Handle search
  const handleSearch = useCallback(async (query: string) => {
    setSearchQuery(query);

    if (!query.trim()) {
      setSearchResults(null);
      return;
    }

    setIsSearching(true);
    try {
      const results = await api.searchConversations(query, {
        includeArchived: activeTab === 'archive',
        searchMessages: true,
      });
      setSearchResults(results);
    } catch (error) {
      console.error('Search failed:', error);
      setSearchResults([]);
    } finally {
      setIsSearching(false);
    }
  }, [activeTab]);

  // Handle tab change
  const handleTabChange = (tab: ConversationTab) => {
    setActiveTab(tab);
    setSearchQuery('');
    setSearchResults(null);
  };

  // Filter conversations based on tab
  const filteredConversations = conversations.filter((conv) => {
    if (activeTab === 'archive') {
      return conv.is_archived;
    }
    return !conv.is_archived;
  });

  // Get display conversations (search results or filtered)
  const displayConversations = searchResults
    ? filteredConversations.filter((conv) =>
        searchResults.some((r) => r.conversation_id === conv.id)
      )
    : filteredConversations;

  // Handle edit actions
  const handleEditStart = (id: string, currentTitle: string) => {
    setEditingConversation(id);
    setEditTitle(currentTitle);
  };

  const handleEditChange = (title: string) => {
    setEditTitle(title);
  };

  const handleEditCancel = () => {
    setEditingConversation(null);
    setEditTitle('');
  };

  const handleRename = async (id: string, newTitle: string) => {
    // Find original title from conversations array (editTitle == newTitle at this point)
    const originalConv = conversations.find(c => c.id === id);
    const originalTitle = originalConv?.title || '';

    if (newTitle.trim() && newTitle !== originalTitle) {
      await onRenameConversation(id, newTitle);
    }
    handleEditCancel();
  };

  // Handle favorites
  const handleSelectFavorite = (favorite: SharedFavorite) => {
    setSelectedFavorite(favorite);
  };

  const handleCopyFavorite = async (favoriteId: string) => {
    try {
      const response = await api.copyFavoriteToConversation(favoriteId);
      // Get the new conversation and select it
      const newConv = await api.getConversation(response.conversation_id);
      onSelectConversation(newConv as ConversationWithStats);
      // Switch back to 'all' tab to see the new conversation
      setActiveTab('all');
      setSelectedFavorite(null);
      // Reload conversations list to display the new conversation with correct message_count
      if (onReloadConversations) {
        await onReloadConversations();
      }
    } catch (error) {
      console.error('Failed to copy favorite:', error);
      throw error;
    }
  };

  const handleProposeFavorite = async (conversationId: string) => {
    try {
      await api.proposeFavorite(conversationId);
      // Show success notification (could be improved with toast)
      alert('Conversation proposee comme favori. Elle sera examinee par un administrateur.');
    } catch (error) {
      console.error('Failed to propose favorite:', error);
      alert('Erreur lors de la proposition du favori.');
    }
  };

  // Render conversation list based on active tab
  const renderConversationList = () => {
    if (displayConversations.length === 0) {
      return (
        <EmptyState
          tab={activeTab}
          searchQuery={searchQuery}
          onNewConversation={onNewConversation}
        />
      );
    }

    const commonProps = {
      currentConversationId: currentConversation?.id,
      editingConversation,
      editTitle,
      onSelectConversation,
      onRenameConversation: handleRename,
      onDeleteConversation,
      onArchiveConversation,
      onUnarchiveConversation,
      onProposeFavorite: handleProposeFavorite,
      onEditStart: handleEditStart,
      onEditChange: handleEditChange,
      onEditCancel: handleEditCancel,
    };

    if (activeTab === 'universes') {
      // Group by universe
      const grouped = groupConversationsByUniverse(displayConversations);
      const universeOrder = ['no-universe', ...universes.map((u) => u.id)];

      return (
        <>
          {universeOrder.map((universeId) => {
            const convs = grouped[universeId];
            if (!convs || convs.length === 0) return null;

            const universe = universes.find((u) => u.id === universeId);
            return (
              <ConversationGroup
                key={universeId}
                title={universe?.name || 'Sans univers'}
                color={universe?.color}
                conversations={convs}
                showUniverseDot={false}
                defaultExpanded={universeId === currentUniverseId || universeId === 'no-universe'}
                {...commonProps}
              />
            );
          })}
        </>
      );
    }

    // Default: group by time
    const timeGroups = groupConversationsByTime(displayConversations);
    return (
      <TimeGroupedList
        groups={timeGroups}
        showUniverseDot={true}
        {...commonProps}
      />
    );
  };

  return (
    <div
      className={`${
        isOpen ? 'w-72' : 'w-0'
      } transition-all duration-300 bg-gray-900 text-white flex flex-col overflow-hidden`}
    >
      <SidebarHeader
        onNewConversation={onNewConversation}
        onOpenSettings={onOpenSettings}
      />

      <SearchBar key={activeTab} onSearch={handleSearch} placeholder="Rechercher..." />

      <FilterTabs
        activeTab={activeTab}
        onTabChange={handleTabChange}
        archivedCount={stats?.archived_count || 0}
        favoritesCount={favoritesCount}
      />

      <div className="flex-1 overflow-y-auto custom-scrollbar p-2">
        {isSearching ? (
          <div className="flex items-center justify-center py-8">
            <div className="animate-spin w-5 h-5 border-2 border-gray-500 border-t-white rounded-full" />
          </div>
        ) : activeTab === 'favorites' ? (
          <FavoritesList
            universes={universes}
            currentUniverseId={currentUniverseId}
            searchQuery={searchQuery}
            onSelectFavorite={handleSelectFavorite}
            onCopyFavorite={handleCopyFavorite}
          />
        ) : (
          renderConversationList()
        )}
      </div>

      <SidebarFooter stats={stats} username={username} />

      {/* Favorite Detail Modal */}
      {selectedFavorite && (
        <FavoriteDetailModal
          favorite={selectedFavorite}
          onClose={() => setSelectedFavorite(null)}
          onCopy={handleCopyFavorite}
        />
      )}
    </div>
  );
}

// Re-export sub-components for potential individual use
export { default as SidebarHeader } from './SidebarHeader';
export { default as SearchBar } from './SearchBar';
export { default as FilterTabs } from './FilterTabs';
export { default as ConversationItem } from './ConversationItem';
export { default as ConversationGroup, TimeGroupedList } from './ConversationGroup';
export { default as SidebarFooter } from './SidebarFooter';
export { default as EmptyState } from './EmptyState';
export { default as FavoritesList } from './FavoritesList';
export { default as FavoriteDetailModal } from './FavoriteDetailModal';
