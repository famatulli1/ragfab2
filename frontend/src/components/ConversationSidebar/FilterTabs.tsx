import type { ConversationTab } from '../../types';

interface FilterTabsProps {
  activeTab: ConversationTab;
  onTabChange: (tab: ConversationTab) => void;
  archivedCount?: number;
}

export default function FilterTabs({
  activeTab,
  onTabChange,
  archivedCount = 0,
}: FilterTabsProps) {
  const tabs: { id: ConversationTab; label: string; badge?: number }[] = [
    { id: 'all', label: 'Tout' },
    { id: 'universes', label: 'Univers' },
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
