import type { ConversationTab } from '../../types';

interface FilterTabsProps {
  activeTab: ConversationTab;
  onTabChange: (tab: ConversationTab) => void;
  archivedCount?: number;
  favoritesCount?: number;
}

export default function FilterTabs({
  activeTab,
  onTabChange,
  archivedCount = 0,
  favoritesCount = 0,
}: FilterTabsProps) {
  const tabs: { id: ConversationTab; label: string; badge?: number; icon?: React.ReactNode }[] = [
    { id: 'all', label: 'Tout' },
    { id: 'universes', label: 'Univers' },
    {
      id: 'favorites',
      label: 'Favoris',
      badge: favoritesCount,
      icon: (
        <svg
          className="w-3.5 h-3.5"
          fill="currentColor"
          viewBox="0 0 20 20"
        >
          <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
        </svg>
      ),
    },
    { id: 'archive', label: 'Archives', badge: archivedCount },
  ];

  return (
    <div className="px-4 py-2">
      <div className="flex bg-gray-800 rounded-lg p-1">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => onTabChange(tab.id)}
            className={`flex-1 px-3 py-1.5 text-xs font-medium rounded-md transition-colors flex items-center justify-center gap-1 ${
              activeTab === tab.id
                ? 'bg-gray-700 text-white'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            {tab.icon && <span className={activeTab === tab.id ? 'text-yellow-400' : ''}>{tab.icon}</span>}
            {tab.label}
            {tab.badge !== undefined && tab.badge > 0 && (
              <span
                className={`ml-1 px-1.5 py-0.5 text-xs rounded-full ${
                  activeTab === tab.id
                    ? 'bg-gray-600 text-gray-200'
                    : 'bg-gray-700 text-gray-400'
                }`}
              >
                {tab.badge}
              </span>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}
