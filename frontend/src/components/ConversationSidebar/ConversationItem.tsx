import { useState } from 'react';
import { MoreVertical, Edit2, Trash2, Archive, FolderInput, Undo2 } from 'lucide-react';
import type { ConversationWithStats, ProductUniverse } from '../../types';
import { formatRelativeDate } from './utils';

interface ConversationItemProps {
  conversation: ConversationWithStats;
  isActive: boolean;
  isEditing: boolean;
  editTitle: string;
  onSelect: () => void;
  onRename: (newTitle: string) => void;
  onDelete: () => void;
  onArchive?: () => void;
  onUnarchive?: () => void;
  onMoveToUniverse?: (universeId: string | null) => void;
  onEditStart: () => void;
  onEditChange: (title: string) => void;
  onEditCancel: () => void;
  universes?: ProductUniverse[];
  showUniverseDot?: boolean;
}

export default function ConversationItem({
  conversation,
  isActive,
  isEditing,
  editTitle,
  onSelect,
  onRename,
  onDelete,
  onArchive,
  onUnarchive,
  onMoveToUniverse,
  onEditStart,
  onEditChange,
  onEditCancel,
  universes = [],
  showUniverseDot = true,
}: ConversationItemProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [moveMenuOpen, setMoveMenuOpen] = useState(false);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      onRename(editTitle);
    } else if (e.key === 'Escape') {
      onEditCancel();
    }
  };

  return (
    <div
      className={`relative group rounded-lg mb-1 transition-colors ${
        isActive ? 'bg-gray-700' : 'hover:bg-gray-800'
      }`}
    >
      <button onClick={onSelect} className="w-full text-left px-3 py-2">
        {isEditing ? (
          <input
            type="text"
            value={editTitle}
            onChange={(e) => onEditChange(e.target.value)}
            onBlur={() => onRename(editTitle)}
            onKeyDown={handleKeyDown}
            autoFocus
            className="w-full bg-gray-600 text-sm font-medium px-2 py-1 rounded border border-gray-500 focus:outline-none focus:border-blue-500"
            onClick={(e) => e.stopPropagation()}
          />
        ) : (
          <>
            <div className="flex items-center gap-2">
              {showUniverseDot && conversation.universe_color && (
                <span
                  className="w-2 h-2 rounded-full flex-shrink-0"
                  style={{ backgroundColor: conversation.universe_color }}
                  title={conversation.universe_name || 'Univers'}
                />
              )}
              <span className="text-sm font-medium truncate pr-8 flex-1">
                {conversation.title}
              </span>
            </div>
            <div className="flex items-center gap-2 mt-1 text-xs text-gray-400">
              <span>{conversation.message_count} messages</span>
              <span>•</span>
              <span>{formatRelativeDate(conversation.updated_at)}</span>
              {conversation.is_archived && (
                <>
                  <span>•</span>
                  <span className="text-amber-400">Archivée</span>
                </>
              )}
            </div>
          </>
        )}
      </button>

      {/* Context menu */}
      {!isEditing && (
        <div className="absolute right-2 top-2 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            onClick={(e) => {
              e.stopPropagation();
              setMenuOpen(!menuOpen);
              setMoveMenuOpen(false);
            }}
            className="p-1 hover:bg-gray-600 rounded"
          >
            <MoreVertical size={16} />
          </button>

          {menuOpen && (
            <div className="absolute right-0 top-8 bg-gray-800 border border-gray-700 rounded-lg shadow-lg py-1 z-20 w-48">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onEditStart();
                  setMenuOpen(false);
                }}
                className="w-full text-left px-3 py-2 hover:bg-gray-700 flex items-center gap-2 text-sm"
              >
                <Edit2 size={14} />
                Renommer
              </button>

              {onMoveToUniverse && (
                <div className="relative">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setMoveMenuOpen(!moveMenuOpen);
                    }}
                    className="w-full text-left px-3 py-2 hover:bg-gray-700 flex items-center gap-2 text-sm"
                  >
                    <FolderInput size={14} />
                    Déplacer vers...
                  </button>
                  {moveMenuOpen && (
                    <div className="absolute left-full top-0 ml-1 bg-gray-800 border border-gray-700 rounded-lg shadow-lg py-1 z-30 w-44">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onMoveToUniverse(null);
                          setMenuOpen(false);
                          setMoveMenuOpen(false);
                        }}
                        className="w-full text-left px-3 py-2 hover:bg-gray-700 text-sm text-gray-400"
                      >
                        Sans univers
                      </button>
                      {universes.map((universe) => (
                        <button
                          key={universe.id}
                          onClick={(e) => {
                            e.stopPropagation();
                            onMoveToUniverse(universe.id);
                            setMenuOpen(false);
                            setMoveMenuOpen(false);
                          }}
                          className="w-full text-left px-3 py-2 hover:bg-gray-700 flex items-center gap-2 text-sm"
                        >
                          <span
                            className="w-2 h-2 rounded-full"
                            style={{ backgroundColor: universe.color }}
                          />
                          {universe.name}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {conversation.is_archived ? (
                onUnarchive && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onUnarchive();
                      setMenuOpen(false);
                    }}
                    className="w-full text-left px-3 py-2 hover:bg-gray-700 flex items-center gap-2 text-sm text-blue-400"
                  >
                    <Undo2 size={14} />
                    Désarchiver
                  </button>
                )
              ) : (
                onArchive && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onArchive();
                      setMenuOpen(false);
                    }}
                    className="w-full text-left px-3 py-2 hover:bg-gray-700 flex items-center gap-2 text-sm text-amber-400"
                  >
                    <Archive size={14} />
                    Archiver
                  </button>
                )
              )}

              <div className="border-t border-gray-700 my-1" />
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete();
                  setMenuOpen(false);
                }}
                className="w-full text-left px-3 py-2 hover:bg-gray-700 flex items-center gap-2 text-sm text-red-400"
              >
                <Trash2 size={14} />
                Supprimer
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
