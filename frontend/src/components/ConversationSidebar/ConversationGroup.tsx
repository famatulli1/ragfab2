import { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import type { ConversationWithStats, ProductUniverse, TimeGroup } from '../../types';
import ConversationItem from './ConversationItem';
import { getTimeGroupLabel } from './utils';

interface ConversationGroupProps {
  title: string;
  conversations: ConversationWithStats[];
  currentConversationId?: string;
  editingConversation: string | null;
  editTitle: string;
  onSelectConversation: (conv: ConversationWithStats) => void;
  onRenameConversation: (id: string, newTitle: string) => void;
  onDeleteConversation: (id: string) => void;
  onArchiveConversation?: (id: string) => void;
  onUnarchiveConversation?: (id: string) => void;
  onMoveToUniverse?: (id: string, universeId: string | null) => void;
  onEditStart: (id: string, currentTitle: string) => void;
  onEditChange: (title: string) => void;
  onEditCancel: () => void;
  universes?: ProductUniverse[];
  showUniverseDot?: boolean;
  collapsible?: boolean;
  defaultExpanded?: boolean;
  color?: string;
}

export default function ConversationGroup({
  title,
  conversations,
  currentConversationId,
  editingConversation,
  editTitle,
  onSelectConversation,
  onRenameConversation,
  onDeleteConversation,
  onArchiveConversation,
  onUnarchiveConversation,
  onMoveToUniverse,
  onEditStart,
  onEditChange,
  onEditCancel,
  universes = [],
  showUniverseDot = true,
  collapsible = true,
  defaultExpanded = true,
  color,
}: ConversationGroupProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  if (conversations.length === 0) {
    return null;
  }

  return (
    <div className="mb-2">
      <button
        onClick={() => collapsible && setIsExpanded(!isExpanded)}
        className={`w-full flex items-center gap-2 px-3 py-1.5 text-xs font-semibold text-gray-400 uppercase tracking-wider ${
          collapsible ? 'hover:text-gray-300 cursor-pointer' : ''
        }`}
      >
        {collapsible && (
          isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />
        )}
        {color && (
          <span
            className="w-2 h-2 rounded-full"
            style={{ backgroundColor: color }}
          />
        )}
        <span className="truncate">{title}</span>
        <span className="ml-auto text-gray-500">({conversations.length})</span>
      </button>

      {isExpanded && (
        <div className="space-y-0.5 mt-1">
          {conversations.map((conv) => (
            <ConversationItem
              key={conv.id}
              conversation={conv}
              isActive={currentConversationId === conv.id}
              isEditing={editingConversation === conv.id}
              editTitle={editingConversation === conv.id ? editTitle : conv.title}
              onSelect={() => onSelectConversation(conv)}
              onRename={(newTitle) => onRenameConversation(conv.id, newTitle)}
              onDelete={() => onDeleteConversation(conv.id)}
              onArchive={onArchiveConversation ? () => onArchiveConversation(conv.id) : undefined}
              onUnarchive={onUnarchiveConversation ? () => onUnarchiveConversation(conv.id) : undefined}
              onMoveToUniverse={onMoveToUniverse ? (universeId) => onMoveToUniverse(conv.id, universeId) : undefined}
              onEditStart={() => onEditStart(conv.id, conv.title)}
              onEditChange={onEditChange}
              onEditCancel={onEditCancel}
              universes={universes}
              showUniverseDot={showUniverseDot && !color}
            />
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * Render time-based groups
 */
interface TimeGroupedListProps extends Omit<ConversationGroupProps, 'title' | 'conversations' | 'color'> {
  groups: Record<TimeGroup, ConversationWithStats[]>;
}

export function TimeGroupedList({
  groups,
  ...props
}: TimeGroupedListProps) {
  const timeGroups: TimeGroup[] = ['today', 'yesterday', 'last7days', 'last30days', 'older'];

  return (
    <>
      {timeGroups.map((group) => (
        <ConversationGroup
          key={group}
          title={getTimeGroupLabel(group)}
          conversations={groups[group] || []}
          collapsible={false}
          {...props}
        />
      ))}
    </>
  );
}
