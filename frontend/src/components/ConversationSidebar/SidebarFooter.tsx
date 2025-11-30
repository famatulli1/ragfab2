import type { ConversationStats, WarningLevel } from '../../types';

interface SidebarFooterProps {
  stats: ConversationStats | null;
  username?: string;
}

function getWarningColor(level: WarningLevel): string {
  switch (level) {
    case 'exceeded':
      return 'text-red-400';
    case 'approaching':
      return 'text-amber-400';
    default:
      return 'text-gray-400';
  }
}

function getWarningBg(level: WarningLevel): string {
  switch (level) {
    case 'exceeded':
      return 'bg-red-500/10';
    case 'approaching':
      return 'bg-amber-500/10';
    default:
      return '';
  }
}

export default function SidebarFooter({ stats, username }: SidebarFooterProps) {
  const activeCount = stats?.active_count || 0;
  const warningLevel = stats?.warning_level || 'none';

  return (
    <div className="p-4 border-t border-gray-700">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-full bg-gray-700 flex items-center justify-center text-sm font-medium">
            {username?.charAt(0).toUpperCase() || '?'}
          </div>
          <span className="text-sm text-gray-300 truncate max-w-[120px]">
            {username}
          </span>
        </div>

        <div
          className={`px-2 py-1 rounded text-xs font-medium ${getWarningBg(warningLevel)} ${getWarningColor(warningLevel)}`}
          title={
            warningLevel === 'exceeded'
              ? 'Limite atteinte ! Les anciennes conversations seront archivées automatiquement.'
              : warningLevel === 'approaching'
              ? 'Vous approchez de la limite de 50 conversations actives.'
              : 'Conversations actives'
          }
        >
          {activeCount}/50
        </div>
      </div>

      {warningLevel === 'exceeded' && (
        <div className="mt-2 text-xs text-red-400 flex items-center gap-1">
          <span className="w-1.5 h-1.5 rounded-full bg-red-400 animate-pulse" />
          Limite atteinte - archivage automatique actif
        </div>
      )}
      {warningLevel === 'approaching' && (
        <div className="mt-2 text-xs text-amber-400 flex items-center gap-1">
          <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
          Pensez à archiver vos anciennes conversations
        </div>
      )}
    </div>
  );
}
