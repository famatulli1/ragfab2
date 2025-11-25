import React, { useState, useRef, useEffect } from 'react';
import { Check, Edit2 } from 'lucide-react';
import type { ProductUniverse } from '../types';

interface UniverseAccessPopoverProps {
  userId: string;
  universes: ProductUniverse[];
  userAccessIds: string[];
  loadingUniverses: Record<string, boolean>;
  onToggleAccess: (userId: string, universeId: string, hasAccess: boolean) => void;
  theme: 'light' | 'dark';
  maxVisible?: number;
}

export const UniverseAccessPopover: React.FC<UniverseAccessPopoverProps> = ({
  userId,
  universes,
  userAccessIds,
  loadingUniverses,
  onToggleAccess,
  theme,
  maxVisible = 2
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const popoverRef = useRef<HTMLDivElement>(null);

  // Click-outside handler
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isOpen]);

  // Escape key handler
  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      return () => document.removeEventListener('keydown', handleEscape);
    }
  }, [isOpen]);

  // Separate universes with access for display
  const universesWithAccess = universes.filter(u => userAccessIds.includes(u.id));
  const visibleUniverses = universesWithAccess.slice(0, maxVisible);
  const overflowCount = Math.max(0, universesWithAccess.length - maxVisible);
  const totalCount = userAccessIds.length;

  return (
    <div className="relative" ref={popoverRef}>
      {/* Condensed Display - Trigger */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`flex items-center gap-2 px-2 py-1.5 rounded-lg transition-colors w-full text-left ${
          theme === 'dark'
            ? 'hover:bg-gray-700'
            : 'hover:bg-gray-100'
        }`}
      >
        <div className="flex flex-wrap gap-1 flex-1 min-w-0">
          {visibleUniverses.map((universe) => (
            <span
              key={universe.id}
              className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-full"
              style={{
                backgroundColor: `${universe.color}30`,
                color: universe.color
              }}
            >
              <Check className="h-2.5 w-2.5" />
              <span className="truncate max-w-[80px]">{universe.name}</span>
            </span>
          ))}

          {overflowCount > 0 && (
            <span className={`inline-flex items-center px-2 py-0.5 text-xs rounded-full font-medium ${
              theme === 'dark'
                ? 'bg-gray-700 text-gray-300'
                : 'bg-gray-200 text-gray-600'
            }`}>
              +{overflowCount}
            </span>
          )}

          {totalCount === 0 && (
            <span className={`text-xs italic ${
              theme === 'dark' ? 'text-gray-500' : 'text-gray-400'
            }`}>
              Aucun univers
            </span>
          )}
        </div>

        <Edit2 className={`h-3.5 w-3.5 flex-shrink-0 ${
          theme === 'dark' ? 'text-gray-500' : 'text-gray-400'
        }`} />
      </button>

      {/* Popover Panel */}
      {isOpen && (
        <div
          className={`absolute top-full left-0 mt-1 w-64 rounded-lg shadow-lg border z-50 animate-fadeSlideIn ${
            theme === 'dark'
              ? 'bg-gray-800 border-gray-700'
              : 'bg-white border-gray-200'
          }`}
        >
          {/* Header */}
          <div className={`px-3 py-2 border-b ${
            theme === 'dark' ? 'border-gray-700' : 'border-gray-200'
          }`}>
            <h4 className={`text-sm font-medium ${
              theme === 'dark' ? 'text-white' : 'text-gray-900'
            }`}>
              Accès aux univers
            </h4>
          </div>

          {/* Checkbox list */}
          <div className="max-h-60 overflow-y-auto py-1">
            {universes.length === 0 ? (
              <p className={`px-3 py-4 text-sm text-center ${
                theme === 'dark' ? 'text-gray-400' : 'text-gray-500'
              }`}>
                Aucun univers disponible
              </p>
            ) : (
              universes.map((universe) => {
                const hasAccess = userAccessIds.includes(universe.id);
                const isLoading = loadingUniverses[`${userId}-${universe.id}`];

                return (
                  <label
                    key={universe.id}
                    className={`flex items-center gap-3 px-3 py-2.5 cursor-pointer transition-colors ${
                      theme === 'dark'
                        ? 'hover:bg-gray-700'
                        : 'hover:bg-gray-50'
                    } ${isLoading ? 'opacity-60 cursor-wait' : ''}`}
                  >
                    {/* Custom checkbox */}
                    <div
                      className={`w-4 h-4 border-2 rounded flex items-center justify-center transition-all flex-shrink-0 ${
                        hasAccess
                          ? 'border-transparent'
                          : theme === 'dark'
                            ? 'border-gray-600'
                            : 'border-gray-300'
                      }`}
                      style={{
                        backgroundColor: hasAccess ? universe.color : 'transparent'
                      }}
                    >
                      {hasAccess && <Check className="h-3 w-3 text-white" />}
                    </div>

                    {/* Color dot */}
                    <span
                      className="w-3 h-3 rounded-full flex-shrink-0"
                      style={{ backgroundColor: universe.color }}
                    />

                    {/* Universe name */}
                    <span className={`text-sm flex-1 truncate ${
                      theme === 'dark' ? 'text-gray-200' : 'text-gray-700'
                    }`}>
                      {universe.name}
                    </span>

                    {/* Loading spinner */}
                    {isLoading && (
                      <div
                        className="w-4 h-4 border-2 border-t-transparent rounded-full animate-spin flex-shrink-0"
                        style={{
                          borderColor: universe.color,
                          borderTopColor: 'transparent'
                        }}
                      />
                    )}

                    {/* Hidden native checkbox for accessibility */}
                    <input
                      type="checkbox"
                      checked={hasAccess}
                      onChange={() => !isLoading && onToggleAccess(userId, universe.id, hasAccess)}
                      disabled={isLoading}
                      className="sr-only"
                      aria-label={`${hasAccess ? 'Retirer' : 'Donner'} accès à ${universe.name}`}
                    />
                  </label>
                );
              })
            )}
          </div>

          {/* Footer with count */}
          <div className={`px-3 py-2 border-t text-xs ${
            theme === 'dark'
              ? 'border-gray-700 text-gray-500'
              : 'border-gray-200 text-gray-400'
          }`}>
            {totalCount} univers sélectionné{totalCount !== 1 ? 's' : ''}
          </div>
        </div>
      )}
    </div>
  );
};

export default UniverseAccessPopover;
