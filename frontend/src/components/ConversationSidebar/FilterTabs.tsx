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
  const tabs: { id: ConversationTab; tooltip: string; badge?: number; icon: React.ReactNode }[] = [
    {
      id: 'all',
      tooltip: 'Tout',
      icon: (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M4 6h16M4 10h16M4 14h16M4 18h16" />
        </svg>
      ),
    },
    {
      id: 'universes',
      tooltip: 'Univers',
      icon: (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
        </svg>
      ),
    },
    {
      id: 'archive',
      tooltip: 'Archives',
      badge: archivedCount,
      icon: (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4" />
        </svg>
      ),
    },
    {
      id: 'favorites',
      tooltip: 'Favoris',
      badge: favoritesCount,
      icon: (
        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
          <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
        </svg>
      ),
    },
  ];

  return (
    <div className="px-4 py-2">
      <div className="flex bg-gray-800 rounded-lg p-1">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            title={tab.tooltip}
            onClick={() => onTabChange(tab.id)}
            className={`flex-1 px-3 py-1.5 text-xs font-medium rounded-md transition-colors flex items-center justify-center gap-1 ${
              activeTab === tab.id
                ? 'bg-gray-700 text-white'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            <span className={tab.id === 'favorites' && activeTab === tab.id ? 'text-yellow-400' : ''}>
              {tab.icon}
            </span>
            {tab.badge !== undefined && tab.badge > 0 && (
              <span
                className={`px-1.5 py-0.5 text-xs rounded-full ${
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
