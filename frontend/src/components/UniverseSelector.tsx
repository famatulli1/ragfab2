import React, { useState, useEffect, useRef } from 'react';
import { Globe, ChevronDown, Check, X, HelpCircle } from 'lucide-react';
import api from '../api/client';
import type { UserUniverseAccess } from '../types';

interface UniverseSelectorProps {
  selectedUniverseIds?: string[];
  searchAllUniverses?: boolean;
  onChange?: (universeIds: string[], searchAll: boolean) => void;
  compact?: boolean;
}

/**
 * Composant pour selectionner les univers dans lesquels effectuer la recherche RAG.
 *
 * Par defaut, utilise l'univers par defaut de l'utilisateur.
 * Permet de selectionner un ou plusieurs univers, ou de chercher dans tous.
 */
export const UniverseSelector: React.FC<UniverseSelectorProps> = ({
  selectedUniverseIds = [],
  searchAllUniverses = false,
  onChange,
  compact = false
}) => {
  const [universes, setUniverses] = useState<UserUniverseAccess[]>([]);
  const [defaultUniverse, setDefaultUniverse] = useState<UserUniverseAccess | null>(null);
  const [selected, setSelected] = useState<string[]>(selectedUniverseIds);
  const [searchAll, setSearchAll] = useState(searchAllUniverses);
  const [isOpen, setIsOpen] = useState(false);
  const [showHelp, setShowHelp] = useState(false);
  const [loading, setLoading] = useState(true);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Charger les univers de l'utilisateur au montage
  useEffect(() => {
    const loadUniverses = async () => {
      try {
        setLoading(true);
        const [accessList, defaultResponse] = await Promise.all([
          api.getMyUniverseAccess(),
          api.getMyDefaultUniverse()
        ]);

        setUniverses(accessList);
        setDefaultUniverse(defaultResponse.default_universe);

        // Si aucun univers selectionne et pas de searchAll, utiliser le defaut
        if (selected.length === 0 && !searchAll && defaultResponse.default_universe) {
          const defaultId = defaultResponse.default_universe.universe_id;
          setSelected([defaultId]);
          if (onChange) {
            onChange([defaultId], false);
          }
        }
      } catch (err) {
        console.error('Erreur chargement univers:', err);
      } finally {
        setLoading(false);
      }
    };

    loadUniverses();
  }, []);

  // Fermer le dropdown en cliquant a l'exterieur
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleToggleUniverse = (universeId: string) => {
    let newSelected: string[];

    if (selected.includes(universeId)) {
      // Ne pas permettre de deselectioner le dernier univers (sauf si searchAll)
      if (selected.length === 1 && !searchAll) {
        return;
      }
      newSelected = selected.filter(id => id !== universeId);
    } else {
      newSelected = [...selected, universeId];
    }

    setSelected(newSelected);
    setSearchAll(false);

    if (onChange) {
      onChange(newSelected, false);
    }
  };

  const handleSearchAll = () => {
    const newSearchAll = !searchAll;
    setSearchAll(newSearchAll);

    if (newSearchAll) {
      // Selectionner tous les univers
      const allIds = universes.map(u => u.universe_id);
      setSelected(allIds);
      if (onChange) {
        onChange(allIds, true);
      }
    } else {
      // Revenir au defaut
      if (defaultUniverse) {
        setSelected([defaultUniverse.universe_id]);
        if (onChange) {
          onChange([defaultUniverse.universe_id], false);
        }
      }
    }
  };

  const handleResetToDefault = () => {
    if (defaultUniverse) {
      setSelected([defaultUniverse.universe_id]);
      setSearchAll(false);
      if (onChange) {
        onChange([defaultUniverse.universe_id], false);
      }
    }
    setIsOpen(false);
  };

  const getSelectedLabel = (): string => {
    if (searchAll) {
      return 'Tous les univers';
    }

    if (selected.length === 0) {
      return 'Aucun univers';
    }

    if (selected.length === 1) {
      const universe = universes.find(u => u.universe_id === selected[0]);
      return universe?.universe_name || 'Univers';
    }

    return `${selected.length} univers`;
  };

  const getSelectedColor = (): string => {
    if (searchAll || selected.length !== 1) {
      return '#6366f1'; // Indigo par defaut
    }

    const universe = universes.find(u => u.universe_id === selected[0]);
    return universe?.universe_color || '#6366f1';
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 px-3 py-2 bg-gray-100 rounded-lg animate-pulse">
        <Globe size={16} className="text-gray-400" />
        <span className="text-sm text-gray-400">Chargement...</span>
      </div>
    );
  }

  // Si l'utilisateur n'a acces a aucun univers, afficher un message
  if (universes.length === 0) {
    return (
      <div className="flex items-center gap-2 px-3 py-2 bg-yellow-50 border border-yellow-200 rounded-lg text-yellow-700 text-sm">
        <Globe size={16} />
        <span>Aucun univers accessible</span>
      </div>
    );
  }

  // Si un seul univers disponible, afficher en mode simplifie
  if (universes.length === 1) {
    const universe = universes[0];
    return (
      <div
        className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm"
        style={{ backgroundColor: `${universe.universe_color}20`, borderColor: universe.universe_color, borderWidth: 1 }}
      >
        <div
          className="w-3 h-3 rounded-full"
          style={{ backgroundColor: universe.universe_color }}
        />
        <span style={{ color: universe.universe_color }} className="font-medium">
          {universe.universe_name}
        </span>
      </div>
    );
  }

  // Mode compact pour integration dans la barre de chat
  if (compact) {
    return (
      <div className="relative" ref={dropdownRef}>
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="flex items-center gap-2 px-3 py-2 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors text-sm"
        >
          <div
            className="w-3 h-3 rounded-full"
            style={{ backgroundColor: getSelectedColor() }}
          />
          <span className="text-gray-700 font-medium">{getSelectedLabel()}</span>
          <ChevronDown size={14} className={`text-gray-400 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
        </button>

        {isOpen && (
          <div className="absolute top-full left-0 mt-1 w-64 bg-white border border-gray-200 rounded-lg shadow-lg z-50">
            {/* Option tous les univers */}
            <div
              className={`flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-gray-50 border-b border-gray-100 ${searchAll ? 'bg-indigo-50' : ''}`}
              onClick={handleSearchAll}
            >
              <div className={`w-5 h-5 border-2 rounded flex items-center justify-center ${searchAll ? 'bg-indigo-600 border-indigo-600' : 'border-gray-300'}`}>
                {searchAll && <Check size={12} className="text-white" />}
              </div>
              <Globe size={16} className="text-indigo-600" />
              <span className="text-sm font-medium text-gray-700">Tous les univers</span>
            </div>

            {/* Liste des univers */}
            <div className="max-h-48 overflow-y-auto">
              {universes.map(universe => (
                <div
                  key={universe.universe_id}
                  className={`flex items-center gap-3 px-4 py-2 cursor-pointer hover:bg-gray-50 ${selected.includes(universe.universe_id) && !searchAll ? 'bg-gray-50' : ''}`}
                  onClick={() => handleToggleUniverse(universe.universe_id)}
                >
                  <div
                    className={`w-5 h-5 border-2 rounded flex items-center justify-center ${selected.includes(universe.universe_id) ? 'border-transparent' : 'border-gray-300'}`}
                    style={{ backgroundColor: selected.includes(universe.universe_id) ? universe.universe_color : 'transparent' }}
                  >
                    {selected.includes(universe.universe_id) && <Check size={12} className="text-white" />}
                  </div>
                  <div
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: universe.universe_color }}
                  />
                  <span className="text-sm text-gray-700">{universe.universe_name}</span>
                  {universe.is_default && (
                    <span className="text-xs text-gray-400 ml-auto">(defaut)</span>
                  )}
                </div>
              ))}
            </div>

            {/* Bouton reset */}
            {defaultUniverse && (selected.length !== 1 || selected[0] !== defaultUniverse.universe_id || searchAll) && (
              <div className="border-t border-gray-100 p-2">
                <button
                  onClick={handleResetToDefault}
                  className="w-full text-xs text-gray-500 hover:text-gray-700 py-1"
                >
                  Revenir a l'univers par defaut
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    );
  }

  // Mode complet avec aide
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <label className="text-sm font-medium text-gray-700">Univers de recherche</label>
        <button
          onClick={() => setShowHelp(!showHelp)}
          className="p-1 text-gray-400 hover:text-gray-600 transition-colors"
          title="En savoir plus"
        >
          <HelpCircle size={14} />
        </button>
      </div>

      {showHelp && (
        <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg text-xs animate-fadeIn">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-start gap-2 flex-1">
              <HelpCircle size={14} className="text-blue-600 mt-0.5 flex-shrink-0" />
              <div className="text-blue-800 space-y-1">
                <p className="font-semibold text-blue-900">Univers = Gamme de produits</p>
                <p>
                  Selectionnez l'univers correspondant a votre question pour des reponses plus precises.
                  Chaque univers contient des documents specifiques a une gamme de produits.
                </p>
              </div>
            </div>
            <button
              onClick={() => setShowHelp(false)}
              className="p-1 text-blue-400 hover:text-blue-600 hover:bg-blue-100 rounded transition-colors flex-shrink-0"
              title="Fermer l'aide"
            >
              <X size={14} />
            </button>
          </div>
        </div>
      )}

      <div className="relative" ref={dropdownRef}>
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="w-full flex items-center justify-between gap-2 px-4 py-3 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
        >
          <div className="flex items-center gap-3">
            <div
              className="w-4 h-4 rounded-full"
              style={{ backgroundColor: getSelectedColor() }}
            />
            <span className="text-gray-700 font-medium">{getSelectedLabel()}</span>
          </div>
          <ChevronDown size={16} className={`text-gray-400 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
        </button>

        {isOpen && (
          <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-50">
            {/* Option tous les univers */}
            <div
              className={`flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-gray-50 border-b border-gray-100 ${searchAll ? 'bg-indigo-50' : ''}`}
              onClick={handleSearchAll}
            >
              <div className={`w-5 h-5 border-2 rounded flex items-center justify-center ${searchAll ? 'bg-indigo-600 border-indigo-600' : 'border-gray-300'}`}>
                {searchAll && <Check size={12} className="text-white" />}
              </div>
              <Globe size={16} className="text-indigo-600" />
              <span className="text-sm font-medium text-gray-700">Rechercher dans tous les univers</span>
            </div>

            {/* Liste des univers */}
            <div className="max-h-64 overflow-y-auto">
              {universes.map(universe => (
                <div
                  key={universe.universe_id}
                  className={`flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-gray-50 ${selected.includes(universe.universe_id) && !searchAll ? 'bg-gray-50' : ''}`}
                  onClick={() => handleToggleUniverse(universe.universe_id)}
                >
                  <div
                    className={`w-5 h-5 border-2 rounded flex items-center justify-center ${selected.includes(universe.universe_id) ? 'border-transparent' : 'border-gray-300'}`}
                    style={{ backgroundColor: selected.includes(universe.universe_id) ? universe.universe_color : 'transparent' }}
                  >
                    {selected.includes(universe.universe_id) && <Check size={12} className="text-white" />}
                  </div>
                  <div
                    className="w-4 h-4 rounded-full"
                    style={{ backgroundColor: universe.universe_color }}
                  />
                  <div className="flex-1">
                    <span className="text-sm text-gray-700">{universe.universe_name}</span>
                    {universe.is_default && (
                      <span className="ml-2 text-xs text-gray-400">(defaut)</span>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {/* Bouton reset */}
            {defaultUniverse && (selected.length !== 1 || selected[0] !== defaultUniverse.universe_id || searchAll) && (
              <div className="border-t border-gray-100 p-3">
                <button
                  onClick={handleResetToDefault}
                  className="w-full text-sm text-indigo-600 hover:text-indigo-800 py-2 hover:bg-indigo-50 rounded transition-colors"
                >
                  Revenir a l'univers par defaut ({defaultUniverse.universe_name})
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Indicateur de selection */}
      {!isOpen && (
        <div className="flex flex-wrap gap-2">
          {selected.map(id => {
            const universe = universes.find(u => u.universe_id === id);
            if (!universe) return null;
            return (
              <span
                key={id}
                className="inline-flex items-center gap-1 px-2 py-1 text-xs rounded-full"
                style={{
                  backgroundColor: `${universe.universe_color}20`,
                  color: universe.universe_color
                }}
              >
                <div
                  className="w-2 h-2 rounded-full"
                  style={{ backgroundColor: universe.universe_color }}
                />
                {universe.universe_name}
              </span>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default UniverseSelector;
