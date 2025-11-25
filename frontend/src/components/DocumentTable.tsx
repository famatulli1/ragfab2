import { useState, useEffect, useCallback } from 'react';
import { Search, Trash2, Eye, ArrowUpDown, ArrowUp, ArrowDown, Loader2 } from 'lucide-react';
import type { DocumentStats, ProductUniverse, DocumentListParams, DocumentListResponse, UniverseDocumentCounts } from '../types';
import Pagination from './Pagination';
import DocumentUniverseTabs from './DocumentUniverseTabs';
import api from '../api/client';

interface DocumentTableProps {
  universes: ProductUniverse[];
  theme: 'light' | 'dark';
  onViewChunks: (doc: DocumentStats) => void;
  onDocumentDeleted: () => void;
}

type SortField = 'created_at' | 'title' | 'chunk_count' | 'universe_name';
type SortOrder = 'asc' | 'desc';

export default function DocumentTable({
  universes,
  theme,
  onViewChunks,
  onDocumentDeleted,
}: DocumentTableProps) {
  // Data state
  const [documents, setDocuments] = useState<DocumentStats[]>([]);
  const [totalItems, setTotalItems] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [counts, setCounts] = useState<UniverseDocumentCounts>({ counts: {}, total: 0, no_universe_count: 0 });
  const [isLoading, setIsLoading] = useState(true);

  // Filter state
  const [selectedUniverseId, setSelectedUniverseId] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');

  // Pagination state
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  // Sort state
  const [sortBy, setSortBy] = useState<SortField>('created_at');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchTerm);
      setCurrentPage(1); // Reset to first page on search
    }, 300);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  // Load counts
  const loadCounts = useCallback(async () => {
    try {
      const data = await api.getUniverseDocumentCounts();
      setCounts(data);
    } catch (error) {
      console.error('Error loading counts:', error);
    }
  }, []);

  // Load documents
  const loadDocuments = useCallback(async () => {
    setIsLoading(true);
    try {
      const params: DocumentListParams = {
        page: currentPage,
        page_size: pageSize,
        sort_by: sortBy,
        order: sortOrder,
      };

      if (selectedUniverseId === 'none') {
        params.no_universe = true;
      } else if (selectedUniverseId) {
        params.universe_id = selectedUniverseId;
      }

      if (debouncedSearch) {
        params.search = debouncedSearch;
      }

      const response: DocumentListResponse = await api.getDocuments(params);
      setDocuments(response.documents);
      setTotalItems(response.total);
      setTotalPages(response.total_pages);
    } catch (error) {
      console.error('Error loading documents:', error);
    } finally {
      setIsLoading(false);
    }
  }, [currentPage, pageSize, sortBy, sortOrder, selectedUniverseId, debouncedSearch]);

  // Initial load
  useEffect(() => {
    loadCounts();
  }, [loadCounts]);

  // Load documents when filters change
  useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);

  // Handle universe tab change
  const handleUniverseChange = (id: string | null) => {
    setSelectedUniverseId(id);
    setCurrentPage(1);
  };

  // Handle sort
  const handleSort = (field: SortField) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortOrder('desc');
    }
    setCurrentPage(1);
  };

  // Handle page change
  const handlePageChange = (page: number) => {
    setCurrentPage(page);
  };

  // Handle page size change
  const handlePageSizeChange = (size: number) => {
    setPageSize(size);
    setCurrentPage(1);
  };

  // Handle document universe change
  const handleUniverseAssignment = async (doc: DocumentStats, newUniverseId: string) => {
    try {
      if (newUniverseId) {
        await api.assignDocumentToUniverse(newUniverseId, doc.id);
      } else {
        await api.unassignDocumentFromUniverse(doc.id);
      }
      loadDocuments();
      loadCounts();
    } catch (error) {
      console.error('Error updating document universe:', error);
      alert('Erreur lors de la mise à jour de l\'univers');
    }
  };

  // Handle delete
  const handleDelete = async (doc: DocumentStats) => {
    if (!confirm(`Êtes-vous sûr de vouloir supprimer "${doc.title}" ?`)) return;

    try {
      await api.deleteDocument(doc.id);
      loadDocuments();
      loadCounts();
      onDocumentDeleted();
    } catch (error) {
      console.error('Error deleting document:', error);
      alert('Erreur lors de la suppression');
    }
  };

  // Sort icon component
  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortBy !== field) {
      return <ArrowUpDown size={14} className="text-gray-400" />;
    }
    return sortOrder === 'asc'
      ? <ArrowUp size={14} className="text-blue-500" />
      : <ArrowDown size={14} className="text-blue-500" />;
  };

  const headerClasses = `px-4 py-3 text-left text-xs font-medium uppercase tracking-wider cursor-pointer select-none transition-colors ${
    theme === 'dark'
      ? 'text-gray-400 hover:text-gray-200 hover:bg-gray-700'
      : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
  }`;

  return (
    <div className={`bg-white dark:bg-gray-800 rounded-lg border ${
      theme === 'dark' ? 'border-gray-700' : 'border-gray-200'
    }`}>
      {/* Universe Tabs */}
      <DocumentUniverseTabs
        universes={universes}
        counts={counts.counts}
        totalCount={counts.total}
        noUniverseCount={counts.no_universe_count}
        selectedUniverseId={selectedUniverseId}
        onSelectUniverse={handleUniverseChange}
        theme={theme}
      />

      {/* Search Bar */}
      <div className={`px-4 py-3 border-b ${theme === 'dark' ? 'border-gray-700' : 'border-gray-200'}`}>
        <div className="relative">
          <Search
            size={18}
            className={`absolute left-3 top-1/2 transform -translate-y-1/2 ${
              theme === 'dark' ? 'text-gray-500' : 'text-gray-400'
            }`}
          />
          <input
            type="text"
            placeholder="Rechercher par titre..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className={`w-full pl-10 pr-4 py-2 rounded-lg border ${
              theme === 'dark'
                ? 'bg-gray-700 border-gray-600 text-gray-200 placeholder-gray-500'
                : 'bg-white border-gray-300 text-gray-900 placeholder-gray-400'
            } focus:ring-2 focus:ring-blue-500 focus:border-transparent`}
          />
          {searchTerm && (
            <button
              onClick={() => setSearchTerm('')}
              className={`absolute right-3 top-1/2 transform -translate-y-1/2 ${
                theme === 'dark' ? 'text-gray-500 hover:text-gray-300' : 'text-gray-400 hover:text-gray-600'
              }`}
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
          <thead className={theme === 'dark' ? 'bg-gray-800' : 'bg-gray-50'}>
            <tr>
              <th
                onClick={() => handleSort('title')}
                className={headerClasses}
              >
                <div className="flex items-center gap-1">
                  Titre
                  <SortIcon field="title" />
                </div>
              </th>
              <th
                onClick={() => handleSort('chunk_count')}
                className={`${headerClasses} w-24 text-center`}
              >
                <div className="flex items-center justify-center gap-1">
                  Chunks
                  <SortIcon field="chunk_count" />
                </div>
              </th>
              <th
                onClick={() => handleSort('universe_name')}
                className={`${headerClasses} w-40`}
              >
                <div className="flex items-center gap-1">
                  Univers
                  <SortIcon field="universe_name" />
                </div>
              </th>
              <th
                onClick={() => handleSort('created_at')}
                className={`${headerClasses} w-32`}
              >
                <div className="flex items-center gap-1">
                  Date
                  <SortIcon field="created_at" />
                </div>
              </th>
              <th className={`${headerClasses} w-24 text-center cursor-default hover:bg-transparent`}>
                Actions
              </th>
            </tr>
          </thead>
          <tbody className={`divide-y ${theme === 'dark' ? 'divide-gray-700' : 'divide-gray-200'}`}>
            {isLoading ? (
              <tr>
                <td colSpan={5} className="px-4 py-12 text-center">
                  <Loader2 className={`w-8 h-8 mx-auto animate-spin ${
                    theme === 'dark' ? 'text-gray-500' : 'text-gray-400'
                  }`} />
                  <p className={`mt-2 text-sm ${theme === 'dark' ? 'text-gray-400' : 'text-gray-500'}`}>
                    Chargement...
                  </p>
                </td>
              </tr>
            ) : documents.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-12 text-center">
                  <p className={`text-sm ${theme === 'dark' ? 'text-gray-400' : 'text-gray-500'}`}>
                    {debouncedSearch
                      ? `Aucun document trouvé pour "${debouncedSearch}"`
                      : 'Aucun document'
                    }
                  </p>
                </td>
              </tr>
            ) : (
              documents.map((doc) => (
                <tr
                  key={doc.id}
                  className={`transition-colors ${
                    theme === 'dark' ? 'hover:bg-gray-700/50' : 'hover:bg-gray-50'
                  }`}
                >
                  <td className={`px-4 py-3 ${theme === 'dark' ? 'text-gray-200' : 'text-gray-900'}`}>
                    <span className="font-medium line-clamp-1" title={doc.title}>
                      {doc.title}
                    </span>
                  </td>
                  <td className={`px-4 py-3 text-center ${theme === 'dark' ? 'text-gray-400' : 'text-gray-500'}`}>
                    {doc.chunk_count || 0}
                  </td>
                  <td className="px-4 py-3">
                    <select
                      value={doc.universe_id || ''}
                      onChange={(e) => handleUniverseAssignment(doc, e.target.value)}
                      className={`w-full px-2 py-1 text-sm border rounded ${
                        theme === 'dark'
                          ? 'bg-gray-700 border-gray-600 text-gray-200'
                          : 'bg-white border-gray-300 text-gray-700'
                      }`}
                      style={doc.universe_color ? {
                        borderLeftWidth: '4px',
                        borderLeftColor: doc.universe_color
                      } : {}}
                    >
                      <option value="">Sans univers</option>
                      {universes.map((universe) => (
                        <option key={universe.id} value={universe.id}>
                          {universe.name}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className={`px-4 py-3 text-sm ${theme === 'dark' ? 'text-gray-400' : 'text-gray-500'}`}>
                    {new Date(doc.created_at).toLocaleDateString('fr-FR')}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-center gap-1">
                      <button
                        onClick={() => onViewChunks(doc)}
                        className={`p-1.5 rounded transition-colors ${
                          theme === 'dark'
                            ? 'text-blue-400 hover:bg-blue-900/20'
                            : 'text-blue-500 hover:bg-blue-50'
                        }`}
                        title="Voir les chunks"
                      >
                        <Eye size={16} />
                      </button>
                      <button
                        onClick={() => handleDelete(doc)}
                        className={`p-1.5 rounded transition-colors ${
                          theme === 'dark'
                            ? 'text-red-400 hover:bg-red-900/20'
                            : 'text-red-500 hover:bg-red-50'
                        }`}
                        title="Supprimer"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {!isLoading && totalPages > 0 && (
        <Pagination
          currentPage={currentPage}
          totalPages={totalPages}
          totalItems={totalItems}
          pageSize={pageSize}
          onPageChange={handlePageChange}
          onPageSizeChange={handlePageSizeChange}
          theme={theme}
        />
      )}
    </div>
  );
}
