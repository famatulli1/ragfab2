import { useState, useEffect, useRef } from 'react';
import { Menu, Send, Plus, Moon, Sun, Download, ThumbsUp, ThumbsDown, Copy, RotateCw, Settings, Trash2, Edit2, MoreVertical } from 'lucide-react';
import { useTheme } from '../App';
import api from '../api/client';
import type { Conversation, Message, Provider } from '../types';
import ReactMarkdown from 'react-markdown';
import DocumentViewModal from '../components/DocumentViewModal';
import RerankingToggle from '../components/RerankingToggle';

export default function ChatPage() {
  const { theme, toggleTheme } = useTheme();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentConversation, setCurrentConversation] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [showSettings, setShowSettings] = useState(false);
  const [provider, setProvider] = useState<Provider>('mistral');
  const [useTools, setUseTools] = useState(true);
  const [selectedDocument, setSelectedDocument] = useState<{ documentId: string; chunkId: string } | null>(null);
  const [editingConversation, setEditingConversation] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [menuOpen, setMenuOpen] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Charger les conversations
  useEffect(() => {
    loadConversations();
  }, []);

  // Charger les messages de la conversation courante
  useEffect(() => {
    if (currentConversation) {
      loadMessages(currentConversation.id);
    }
  }, [currentConversation]);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Fermer le menu contextuel quand on clique ailleurs
  useEffect(() => {
    const handleClickOutside = () => setMenuOpen(null);
    if (menuOpen) {
      document.addEventListener('click', handleClickOutside);
      return () => document.removeEventListener('click', handleClickOutside);
    }
  }, [menuOpen]);

  const loadConversations = async () => {
    try {
      const convs = await api.getConversations();
      setConversations(convs);
      if (convs.length > 0 && !currentConversation) {
        setCurrentConversation(convs[0]);
      } else if (convs.length === 0) {
        // Créer automatiquement une conversation si aucune n'existe
        await createNewConversation();
      }
    } catch (error) {
      console.error('Error loading conversations:', error);
    }
  };

  const loadMessages = async (conversationId: string) => {
    try {
      const msgs = await api.getConversationMessages(conversationId);
      setMessages(msgs);
    } catch (error) {
      console.error('Error loading messages:', error);
    }
  };

  const createNewConversation = async () => {
    try {
      const conv = await api.createConversation('Nouvelle conversation', provider, useTools);
      setConversations([conv, ...conversations]);
      setCurrentConversation(conv);
      setMessages([]);
    } catch (error) {
      console.error('Error creating conversation:', error);
    }
  };

  const sendMessage = async () => {
    if (!inputMessage.trim() || !currentConversation || isLoading) return;

    const userMessage = inputMessage;
    setInputMessage('');
    setIsLoading(true);

    try {
      const response = await api.sendMessage({
        conversation_id: currentConversation.id,
        message: userMessage,
        provider,
        use_tools: useTools,
      });

      setMessages([...messages, response.user_message, response.assistant_message]);

      // Mettre à jour la conversation dans la liste
      setConversations(convs =>
        convs.map(c => c.id === currentConversation.id ? response.conversation : c)
      );
    } catch (error) {
      console.error('Error sending message:', error);
      alert('Erreur lors de l\'envoi du message');
    } finally {
      setIsLoading(false);
    }
  };

  const regenerateMessage = async (messageId: string) => {
    setIsLoading(true);
    try {
      const newMessage = await api.regenerateMessage(messageId);
      setMessages([...messages, newMessage]);
    } catch (error) {
      console.error('Error regenerating message:', error);
      alert('Erreur lors de la régénération');
    } finally {
      setIsLoading(false);
    }
  };

  const rateMessage = async (messageId: string, rating: 1 | -1) => {
    try {
      await api.rateMessage(messageId, { rating });
      setMessages(msgs =>
        msgs.map(m => m.id === messageId ? { ...m, rating } : m)
      );
    } catch (error) {
      console.error('Error rating message:', error);
    }
  };

  const copyMessage = (content: string) => {
    navigator.clipboard.writeText(content);
  };

  const exportConversation = async (format: 'markdown' | 'pdf') => {
    if (!currentConversation) return;

    try {
      const blob = await api.exportConversation(currentConversation.id, format);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `conversation_${currentConversation.id}.${format === 'markdown' ? 'md' : 'pdf'}`;
      a.click();
    } catch (error) {
      console.error('Error exporting conversation:', error);
    }
  };

  const handleRenameConversation = async (id: string, newTitle: string) => {
    if (!newTitle.trim()) {
      setEditingConversation(null);
      return;
    }

    try {
      const updated = await api.updateConversation(id, { title: newTitle });
      setConversations(convs =>
        convs.map(c => c.id === id ? { ...c, title: updated.title } : c)
      );
      if (currentConversation?.id === id) {
        setCurrentConversation({ ...currentConversation, title: updated.title });
      }
      setEditingConversation(null);
    } catch (error) {
      console.error('Error renaming conversation:', error);
      alert('Erreur lors du renommage');
    }
  };

  const handleDeleteConversation = async (id: string) => {
    if (!confirm('Êtes-vous sûr de vouloir supprimer cette conversation ?')) {
      return;
    }

    try {
      await api.deleteConversation(id);
      setConversations(convs => convs.filter(c => c.id !== id));

      // Si c'est la conversation active, sélectionner une autre ou créer une nouvelle
      if (currentConversation?.id === id) {
        const remaining = conversations.filter(c => c.id !== id);
        if (remaining.length > 0) {
          setCurrentConversation(remaining[0]);
        } else {
          await createNewConversation();
        }
      }
      setMenuOpen(null);
    } catch (error) {
      console.error('Error deleting conversation:', error);
      alert('Erreur lors de la suppression');
    }
  };

  return (
    <div className="flex h-screen bg-gray-50 dark:bg-gray-900">
      {/* Sidebar */}
      <div
        className={`${
          sidebarOpen ? 'w-64' : 'w-0'
        } transition-all duration-300 bg-gray-900 text-white flex flex-col overflow-hidden`}
      >
        <div className="p-4 border-b border-gray-700">
          <button
            onClick={createNewConversation}
            className="w-full flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg transition-colors"
          >
            <Plus size={20} />
            <span>Nouvelle conversation</span>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto custom-scrollbar p-2">
          {conversations.map(conv => (
            <div
              key={conv.id}
              className={`relative group rounded-lg mb-1 transition-colors ${
                currentConversation?.id === conv.id
                  ? 'bg-gray-700'
                  : 'hover:bg-gray-800'
              }`}
            >
              <button
                onClick={() => setCurrentConversation(conv)}
                className="w-full text-left px-3 py-2"
              >
                {editingConversation === conv.id ? (
                  <input
                    type="text"
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    onBlur={() => handleRenameConversation(conv.id, editTitle)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        handleRenameConversation(conv.id, editTitle);
                      } else if (e.key === 'Escape') {
                        setEditingConversation(null);
                      }
                    }}
                    autoFocus
                    className="w-full bg-gray-600 text-sm font-medium px-2 py-1 rounded border border-gray-500 focus:outline-none focus:border-blue-500"
                    onClick={(e) => e.stopPropagation()}
                  />
                ) : (
                  <>
                    <div className="text-sm font-medium truncate pr-8">{conv.title}</div>
                    <div className="text-xs text-gray-400">
                      {conv.message_count} messages
                    </div>
                  </>
                )}
              </button>

              {/* Menu contextuel */}
              {editingConversation !== conv.id && (
                <div className="absolute right-2 top-2 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setMenuOpen(menuOpen === conv.id ? null : conv.id);
                    }}
                    className="p-1 hover:bg-gray-600 rounded"
                  >
                    <MoreVertical size={16} />
                  </button>

                  {menuOpen === conv.id && (
                    <div className="absolute right-0 top-8 bg-gray-800 border border-gray-700 rounded-lg shadow-lg py-1 z-10 w-40">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setEditTitle(conv.title);
                          setEditingConversation(conv.id);
                          setMenuOpen(null);
                        }}
                        className="w-full text-left px-3 py-2 hover:bg-gray-700 flex items-center gap-2 text-sm"
                      >
                        <Edit2 size={14} />
                        Renommer
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteConversation(conv.id);
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
          ))}
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="h-14 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between px-4 bg-white dark:bg-gray-800">
          <div className="flex items-center gap-4">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="btn-ghost"
            >
              <Menu size={20} />
            </button>
            <h1 className="font-semibold text-lg">
              {currentConversation?.title || 'RAGFab'}
            </h1>
            {currentConversation && (
              <RerankingToggle
                conversationId={currentConversation.id}
                initialValue={currentConversation.reranking_enabled}
                onUpdate={(value) => {
                  // Update local conversation state
                  if (currentConversation) {
                    setCurrentConversation({
                      ...currentConversation,
                      reranking_enabled: value,
                    });
                    // Update in conversations list
                    setConversations(convs =>
                      convs.map(c =>
                        c.id === currentConversation.id
                          ? { ...c, reranking_enabled: value }
                          : c
                      )
                    );
                  }
                }}
              />
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowSettings(!showSettings)}
              className="btn-ghost"
              title="Paramètres"
            >
              <Settings size={20} />
            </button>
            {currentConversation && (
              <button
                onClick={() => exportConversation('markdown')}
                className="btn-ghost"
                title="Exporter en Markdown"
              >
                <Download size={20} />
              </button>
            )}
            <button
              onClick={toggleTheme}
              className="btn-ghost"
              title={theme === 'light' ? 'Mode sombre' : 'Mode clair'}
            >
              {theme === 'light' ? <Moon size={20} /> : <Sun size={20} />}
            </button>
          </div>
        </div>

        {/* Settings Panel */}
        {showSettings && (
          <div className="p-4 bg-yellow-50 dark:bg-yellow-900/20 border-b border-yellow-200 dark:border-yellow-800">
            <div className="flex gap-4">
              <div>
                <label className="block text-sm font-medium mb-1">Provider</label>
                <select
                  value={provider}
                  onChange={(e) => setProvider(e.target.value as Provider)}
                  className="input"
                >
                  <option value="mistral">Mistral (avec tools)</option>
                  <option value="chocolatine">Chocolatine (avec tools)</option>
                </select>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={useTools}
                  onChange={(e) => setUseTools(e.target.checked)}
                  id="use-tools"
                  className="w-4 h-4"
                />
                <label htmlFor="use-tools" className="text-sm">
                  Utiliser les tools (RAG)
                </label>
              </div>
            </div>
          </div>
        )}

        {/* Messages */}
        <div className="flex-1 overflow-y-auto custom-scrollbar">
          <div className="max-w-3xl mx-auto p-4">
            {messages.map((message) => (
              <div
                key={message.id}
                className={`mb-6 ${
                  message.role === 'user' ? 'ml-auto max-w-[80%]' : ''
                }`}
              >
                <div className="flex items-start gap-3">
                  <div
                    className={`w-8 h-8 rounded-full flex items-center justify-center text-white text-sm font-bold ${
                      message.role === 'user'
                        ? 'bg-blue-500'
                        : 'bg-green-500'
                    }`}
                  >
                    {message.role === 'user' ? 'U' : 'AI'}
                  </div>
                  <div className="flex-1">
                    <div className="markdown-content">
                      <ReactMarkdown>{message.content}</ReactMarkdown>
                    </div>

                    {/* Sources */}
                    {message.sources && message.sources.length > 0 && (
                      <div className="mt-3 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
                        <div className="font-semibold text-blue-800 dark:text-blue-300 mb-2 flex items-center gap-2">
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                          </svg>
                          Sources ({message.sources.length})
                        </div>
                        <div className="space-y-2">
                          {message.sources.map((source: any, i: number) => (
                            <div
                              key={i}
                              onClick={() => setSelectedDocument({ documentId: source.document_id, chunkId: source.chunk_id })}
                              className="text-sm text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 p-2 rounded border border-gray-200 dark:border-gray-700 cursor-pointer hover:border-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-all"
                            >
                              <div className="font-medium text-blue-600 dark:text-blue-400 flex items-center gap-2">
                                📄 {source.document_title}
                                <span className="text-xs text-gray-400">→ Voir le document</span>
                              </div>
                              <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                                Chunk #{source.chunk_index} • Similarité: {(source.similarity * 100).toFixed(1)}%
                              </div>
                              <div className="text-xs text-gray-600 dark:text-gray-400 mt-1 italic">
                                "{source.content}"
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Actions (pour messages assistant) */}
                    {message.role === 'assistant' && (
                      <div className="flex items-center gap-2 mt-2">
                        <button
                          onClick={() => copyMessage(message.content)}
                          className="btn-ghost p-1"
                          title="Copier"
                        >
                          <Copy size={16} />
                        </button>
                        <button
                          onClick={() => regenerateMessage(message.id)}
                          className="btn-ghost p-1"
                          title="Régénérer"
                          disabled={isLoading}
                        >
                          <RotateCw size={16} />
                        </button>
                        <button
                          onClick={() => rateMessage(message.id, 1)}
                          className={`btn-ghost p-1 ${
                            message.rating === 1 ? 'text-green-500' : ''
                          }`}
                          title="Bon"
                        >
                          <ThumbsUp size={16} />
                        </button>
                        <button
                          onClick={() => rateMessage(message.id, -1)}
                          className={`btn-ghost p-1 ${
                            message.rating === -1 ? 'text-red-500' : ''
                          }`}
                          title="Mauvais"
                        >
                          <ThumbsDown size={16} />
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}

            {/* Typing indicator */}
            {isLoading && (
              <div className="flex items-start gap-3 mb-6">
                <div className="w-8 h-8 rounded-full bg-green-500 flex items-center justify-center text-white text-sm font-bold">
                  AI
                </div>
                <div className="typing-indicator">
                  <div className="typing-dot"></div>
                  <div className="typing-dot"></div>
                  <div className="typing-dot"></div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Input */}
        <div className="border-t border-gray-200 dark:border-gray-700 p-4 bg-white dark:bg-gray-800">
          <div className="max-w-3xl mx-auto flex gap-2">
            <input
              type="text"
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
              placeholder="Posez votre question..."
              className="input flex-1"
              disabled={isLoading || !currentConversation}
            />
            <button
              onClick={sendMessage}
              disabled={!inputMessage.trim() || isLoading || !currentConversation}
              className="btn-primary"
            >
              <Send size={20} />
            </button>
          </div>
        </div>
      </div>

      {/* Document View Modal */}
      {selectedDocument && (
        <DocumentViewModal
          documentId={selectedDocument.documentId}
          chunkId={selectedDocument.chunkId}
          onClose={() => setSelectedDocument(null)}
        />
      )}
    </div>
  );
}
