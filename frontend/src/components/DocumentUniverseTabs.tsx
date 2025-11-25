import { ProductUniverse } from '../types';

interface DocumentUniverseTabsProps {
  universes: ProductUniverse[];
  counts: Record<string, number>;
  totalCount: number;
  noUniverseCount: number;
  selectedUniverseId: string | null;  // null = tous, 'none' = sans univers
  onSelectUniverse: (id: string | null) => void;
  theme: 'light' | 'dark';
}

export default function DocumentUniverseTabs({
  universes,
  counts,
  totalCount,
  noUniverseCount,
  selectedUniverseId,
  onSelectUniverse,
  theme,
}: DocumentUniverseTabsProps) {
  const activeUniverses = universes.filter(u => u.is_active);

  const getTabClasses = (isSelected: boolean) => {
    const base = 'px-3 py-2 text-sm font-medium rounded-t-lg border-b-2 transition-colors whitespace-nowrap flex items-center gap-2';

    if (isSelected) {
      return `${base} ${
        theme === 'dark'
          ? 'border-blue-500 text-blue-400 bg-gray-800'
          : 'border-blue-500 text-blue-600 bg-blue-50'
      }`;
    }

    return `${base} border-transparent ${
      theme === 'dark'
        ? 'text-gray-400 hover:text-gray-200 hover:bg-gray-800'
        : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
    }`;
  };

  const getBadgeClasses = (isSelected: boolean, color?: string) => {
    if (color && isSelected) {
      return 'px-1.5 py-0.5 text-xs rounded-full text-white';
    }

    return `px-1.5 py-0.5 text-xs rounded-full ${
      isSelected
        ? theme === 'dark'
          ? 'bg-blue-500/20 text-blue-400'
          : 'bg-blue-100 text-blue-700'
        : theme === 'dark'
          ? 'bg-gray-700 text-gray-400'
          : 'bg-gray-200 text-gray-600'
    }`;
  };

  return (
    <div className={`border-b ${theme === 'dark' ? 'border-gray-700' : 'border-gray-200'}`}>
      <div className="flex overflow-x-auto scrollbar-hide -mb-px">
        {/* Tab "Tous" */}
        <button
          onClick={() => onSelectUniverse(null)}
          className={getTabClasses(selectedUniverseId === null)}
        >
          <span>Tous</span>
          <span className={getBadgeClasses(selectedUniverseId === null)}>
            {totalCount}
          </span>
        </button>

        {/* Tabs par univers */}
        {activeUniverses.map((universe) => {
          const count = counts[universe.id] || 0;
          const isSelected = selectedUniverseId === universe.id;

          return (
            <button
              key={universe.id}
              onClick={() => onSelectUniverse(universe.id)}
              className={getTabClasses(isSelected)}
            >
              <span
                className="w-2 h-2 rounded-full flex-shrink-0"
                style={{ backgroundColor: universe.color }}
              />
              <span className="truncate max-w-[120px]">{universe.name}</span>
              <span
                className={getBadgeClasses(isSelected, universe.color)}
                style={isSelected ? { backgroundColor: universe.color } : undefined}
              >
                {count}
              </span>
            </button>
          );
        })}

        {/* Tab "Sans univers" */}
        {noUniverseCount > 0 && (
          <button
            onClick={() => onSelectUniverse('none')}
            className={getTabClasses(selectedUniverseId === 'none')}
          >
            <span className={`w-2 h-2 rounded-full flex-shrink-0 ${
              theme === 'dark' ? 'bg-gray-600' : 'bg-gray-400'
            }`} />
            <span>Sans univers</span>
            <span className={getBadgeClasses(selectedUniverseId === 'none')}>
              {noUniverseCount}
            </span>
          </button>
        )}
      </div>
    </div>
  );
}
