import { useState, useEffect, useRef } from 'react';
import { Menu, Send, Moon, Sun, ThumbsUp, ThumbsDown, Copy, RotateCw, Bot, User as UserIcon, Search, Zap } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useTheme } from '../App';
import api from '../api/client';
import type { ConversationWithStats, Message, Provider, User, QualityAnalysis, PreAnalyzeResponse, ProductUniverse, FavoriteSearchResult, SharedFavorite } from '../types';
import ReactMarkdown from 'react-markdown';
import DocumentViewModal from '../components/DocumentViewModal';
import RerankingToggle from '../components/RerankingToggle';
import HybridSearchToggle from '../components/HybridSearchToggle';
import ImageViewer from '../components/ImageViewer';
import ChangePasswordModal from '../components/ChangePasswordModal';
import UserMenu from '../components/UserMenu';
import ResponseTemplates from '../components/ResponseTemplates';
import UniverseSelector from '../components/UniverseSelector';
import QuestionSuggestions from '../components/QuestionSuggestions';
import InteractiveSuggestionModal from '../components/InteractiveSuggestionModal';
import ConversationSidebar from '../components/ConversationSidebar';
import ConversationSettings from '../components/ConversationSettings';
import FavoriteSuggestionBanner from '../components/Chat/FavoriteSuggestionBanner';
import { FavoriteDetailModal } from '../components/ConversationSidebar';

export default function ChatPage() {
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [mustChangePassword, setMustChangePassword] = useState(false);
  const [conversations, setConversations] = useState<ConversationWithStats[]>([]);
  const [currentConversation, setCurrentConversation] = useState<ConversationWithStats | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [showConversationSettings, setShowConversationSettings] = useState(false);
  const [provider] = useState<Provider>('chocolatine'); // setProvider hidden with settings
  const [useTools] = useState(true); // setUseTools hidden with settings
  const [selectedDocument, setSelectedDocument] = useState<{ documentId: string; chunkIds: string[]; initialChunkId: string } | null>(null);
  const [templates, setTemplates] = useState<any[]>([]);
  const [formattedResponses, setFormattedResponses] = useState<Map<string, any>>(new Map());
  const [universes, setUniverses] = useState<ProductUniverse[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Quality analysis state (map message_id -> QualityAnalysis)
  const [qualityAnalyses, setQualityAnalyses] = useState<Map<string, QualityAnalysis>>(new Map());
  const inputRef = useRef<HTMLInputElement>(null);

  // Universe selection state
  const [selectedUniverseIds, setSelectedUniverseIds] = useState<string[]>([]);
  const [searchAllUniverses, setSearchAllUniverses] = useState(false);
  const [defaultUniverseId, setDefaultUniverseId] = useState<string | null>(null);

  // Interactive mode state (pre-analyze before sending)
  const [preAnalyzeResult, setPreAnalyzeResult] = useState<PreAnalyzeResponse | null>(null);
  const [pendingMessage, setPendingMessage] = useState<string>('');
  const [isPreAnalyzing, setIsPreAnalyzing] = useState(false);

  // Favorite suggestions state (pre-RAG check)
  const [favoriteSuggestions, setFavoriteSuggestions] = useState<FavoriteSearchResult[]>([]);
  const [selectedFavoriteForDetail, setSelectedFavoriteForDetail] = useState<SharedFavorite | FavoriteSearchResult | null>(null);
  const [pendingQuestionForFavorites, setPendingQuestionForFavorites] = useState<string>('');

  // Charger l'utilisateur courant
  useEffect(() => {
    loadCurrentUser();
  }, []);

  // Charger l'univers par défaut, puis les conversations
  useEffect(() => {
    const init = async () => {
      let loadedDefaultUniverseId: string | null = null;
      try {
        // 1. Charger l'univers par défaut de l'utilisateur
        const defaultResponse = await api.getMyDefaultUniverse();
        if (defaultResponse.default_universe) {
          loadedDefaultUniverseId = defaultResponse.default_universe.universe_id;
          setDefaultUniverseId(loadedDefaultUniverseId);
        }
      } catch (error) {
        console.error('Error loading default universe:', error);
      }
      // 2. Charger les conversations (passer directement la valeur, pas le state)
      await loadConversations(loadedDefaultUniverseId);
    };
    init();
  }, []);

  // Charger les messages de la conversation courante
  useEffect(() => {
    if (currentConversation) {
      loadMessages(currentConversation.id);
      // Logs de débogage pour diagnostiquer le problème du toggle
      console.log('🎚️ Current conversation loaded:', currentConversation);
      console.log('🎚️ reranking_enabled value:', currentConversation.reranking_enabled);
    }
  }, [currentConversation]);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Charger les templates de réponse
  useEffect(() => {
    api.listActiveTemplates().then(setTemplates).catch(console.error);
  }, []);

  // Charger les univers accessibles à l'utilisateur (pas tous les univers)
  useEffect(() => {
    api.getMyUniverseAccess().then(data => {
      // Convertir UserUniverseAccess[] en ProductUniverse[] (partial)
      const accessibleUniverses = data.map(access => ({
        id: access.universe_id,
        name: access.universe_name,
        slug: access.universe_id, // Utiliser l'ID comme slug fallback
        color: access.universe_color,
        is_active: true,
        detection_keywords: [],
        created_at: '',
        updated_at: '',
      } as ProductUniverse));
      setUniverses(accessibleUniverses);
    }).catch(console.error);
  }, []);

  const loadCurrentUser = async () => {
    try {
      const user = await api.getCurrentUser();
      setCurrentUser(user);

      // Vérifier si changement de mot de passe obligatoire
      if (user.must_change_password) {
        setMustChangePassword(true);
      }
    } catch (error) {
      console.error('Error loading current user:', error);
      navigate('/login');
    }
  };

  const handlePasswordChanged = async () => {
    setMustChangePassword(false);
    // Recharger l'utilisateur pour mettre à jour le flag
    await loadCurrentUser();
  };

  const handlePasswordSubmit = async (currentPassword: string, newPassword: string, confirmPassword: string) => {
    // Si c'est la première connexion, utiliser l'endpoint spécial qui ne vérifie pas le mot de passe actuel
    if (mustChangePassword) {
      await api.changeFirstLoginPassword({
        current_password: '', // Non utilisé par l'endpoint first-password-change
        new_password: newPassword,
        confirm_password: confirmPassword,
      });
    } else {
      await api.changeMyPassword({
        current_password: currentPassword,
        new_password: newPassword,
        confirm_password: confirmPassword,
      });
    }
  };

  const handleLogout = async () => {
    await api.logout();
    navigate('/login');
  };

  const loadConversations = async (passedDefaultUniverseId?: string | null) => {
    try {
      const convs = await api.getConversations(50, 0, true); // Include archived conversations
      setConversations(convs);
      if (convs.length > 0 && !currentConversation) {
        // Chercher une conversation vierge (0 messages)
        const emptyConversation = convs.find(c => c.message_count === 0);
        if (emptyConversation) {
          setCurrentConversation(emptyConversation);
        } else {
          // Aucune conversation vierge, créer une nouvelle (passer convs et defaultUniverse)
          await createNewConversation(convs, passedDefaultUniverseId);
        }
      } else if (convs.length === 0) {
        // Créer automatiquement une conversation si aucune n'existe
        await createNewConversation(undefined, passedDefaultUniverseId);
      }
    } catch (error) {
      console.error('Error loading conversations:', error);
    }
  };

  const loadMessages = async (conversationId: string) => {
    try {
      const msgs = await api.getConversationMessages(conversationId);
      setMessages(msgs);

      // Charger les réponses formatées pour tous les messages assistant
      const newFormattedResponses = new Map();
      for (const msg of msgs) {
        if (msg.role === 'assistant' && msg.id) {
          const formatted = await api.getFormattedResponse(msg.id);
          if (formatted) {
            newFormattedResponses.set(msg.id, formatted);
          }
        }
      }
      setFormattedResponses(newFormattedResponses);
    } catch (error) {
      console.error('Error loading messages:', error);
    }
  };

  const createNewConversation = async (
    existingConversations?: ConversationWithStats[],
    passedDefaultUniverseId?: string | null
  ) => {
    try {
      // Priority: selectedUniverseIds > passedDefaultUniverseId > state defaultUniverseId
      const currentUniverseId = selectedUniverseIds.length > 0
        ? selectedUniverseIds[0]
        : (passedDefaultUniverseId || defaultUniverseId || undefined);
      const currentUniverse = currentUniverseId ? universes.find(u => u.id === currentUniverseId) : undefined;

      console.log('🌍 Creating conversation with universe:', currentUniverseId, currentUniverse?.name);

      const conv = await api.createConversation({
        title: 'Nouvelle conversation',
        provider: provider as 'mistral' | 'chocolatine',
        use_tools: useTools,
        universe_id: currentUniverseId,
      });

      // Add default stats and universe info for ConversationWithStats
      // Use API response values as fallback (conv already has universe_name/color from backend JOIN)
      const convWithStats: ConversationWithStats = {
        ...conv,
        thumbs_up_count: 0,
        thumbs_down_count: 0,
        universe_id: currentUniverseId || conv.universe_id,
        universe_name: currentUniverse?.name || conv.universe_name,
        universe_color: currentUniverse?.color || conv.universe_color,
      };
      // Utiliser existingConversations si fourni, sinon le state actuel
      if (existingConversations) {
        setConversations([convWithStats, ...existingConversations]);
      } else {
        setConversations(prev => [convWithStats, ...prev]);
      }
      setCurrentConversation(convWithStats);
      setMessages([]);
    } catch (error) {
      console.error('Error creating conversation:', error);
    }
  };

  // Core function to actually send the message (bypasses pre-analyze)
  const doSendMessage = async (messageToSend: string) => {
    if (!messageToSend.trim() || !currentConversation || isLoading) return;

    const wasRerankingEnabled = currentConversation.reranking_enabled;
    setIsLoading(true);

    try {
      const response = await api.sendMessage({
        conversation_id: currentConversation.id,
        message: messageToSend,
        provider,
        use_tools: useTools,
        reranking_enabled: currentConversation.reranking_enabled,
        universe_ids: selectedUniverseIds.length > 0 ? selectedUniverseIds : undefined,
        search_all_universes: searchAllUniverses,
        hybrid_search_enabled: currentConversation.hybrid_search_enabled,
        hybrid_search_alpha: currentConversation.hybrid_search_alpha,
      });

      setMessages([...messages, response.user_message, response.assistant_message]);

      // Capturer l'analyse de qualité si présente (phases soft/interactive)
      const qualityAnalysis = response.quality_analysis;

      if (qualityAnalysis && qualityAnalysis.classification !== 'clear') {
        setQualityAnalyses(prev => {
          const newMap = new Map(prev);
          newMap.set(response.assistant_message.id, qualityAnalysis);
          return newMap;
        });
      }

      // Mettre à jour la conversation dans la liste (preserve stats and universe data)
      const updatedConvWithStats: ConversationWithStats = {
        ...response.conversation,
        thumbs_up_count: currentConversation.thumbs_up_count,
        thumbs_down_count: currentConversation.thumbs_down_count,
        // Fallback: preserve universe data if not in response
        universe_id: response.conversation.universe_id ?? currentConversation.universe_id,
        universe_name: response.conversation.universe_name ?? currentConversation.universe_name,
        universe_color: response.conversation.universe_color ?? currentConversation.universe_color,
      };
      setConversations(convs =>
        convs.map(c => c.id === currentConversation.id ? updatedConvWithStats : c)
      );

      // Désactiver automatiquement le toggle "Recherche approfondie" après la réponse
      if (wasRerankingEnabled) {
        const updatedConversation: ConversationWithStats = {
          ...updatedConvWithStats,
          reranking_enabled: false,
        };
        setCurrentConversation(updatedConversation);
        setConversations(convs =>
          convs.map(c => c.id === currentConversation.id ? updatedConversation : c)
        );
      }
    } catch (error) {
      console.error('Error sending message:', error);
      alert('Erreur lors de l\'envoi du message');
    } finally {
      setIsLoading(false);
    }
  };

  // Main send function - checks for favorites, then interactive mode
  const sendMessage = async () => {
    if (!inputMessage.trim() || !currentConversation || isLoading || isPreAnalyzing) return;

    const messageToSend = inputMessage;

    // Step 1: Check for similar favorites (pre-RAG suggestion)
    try {
      const favoriteResponse = await api.checkFavoriteSuggestions(
        messageToSend,
        selectedUniverseIds.length > 0 ? selectedUniverseIds : undefined
      );

      if (favoriteResponse.has_suggestions && favoriteResponse.suggestions.length > 0) {
        // Show favorite suggestions banner
        setFavoriteSuggestions(favoriteResponse.suggestions);
        setPendingQuestionForFavorites(messageToSend);
        // Don't clear input yet - user might decline
        return;
      }
    } catch (error) {
      console.error('Error checking favorites:', error);
      // Continue with normal flow on error
    }

    // Step 2: Continue with normal send flow
    await proceedWithSend(messageToSend);
  };

  // Proceed with sending after favorite check
  const proceedWithSend = async (messageToSend: string) => {
    // Check if user has interactive suggestion mode enabled
    const isInteractiveMode = currentUser?.suggestion_mode === 'interactive';

    if (isInteractiveMode) {
      // Pre-analyze the question before sending
      setIsPreAnalyzing(true);
      try {
        const preAnalysis = await api.preAnalyzeQuestion({
          message: messageToSend,
          conversation_id: currentConversation!.id,
          universe_ids: selectedUniverseIds.length > 0 ? selectedUniverseIds : undefined,
        });

        if (preAnalysis.needs_clarification && preAnalysis.suggestions.length > 0) {
          // Show the interactive modal instead of sending
          setPendingMessage(messageToSend);
          setPreAnalyzeResult(preAnalysis);
          // Don't clear input yet - user might cancel
          return;
        }

        // Question is clear, proceed to send
        setInputMessage('');
        await doSendMessage(messageToSend);
      } catch (error) {
        console.error('Error in pre-analyze:', error);
        // On error, fallback to direct send
        setInputMessage('');
        await doSendMessage(messageToSend);
      } finally {
        setIsPreAnalyzing(false);
      }
    } else {
      // Not in interactive mode, send directly
      setInputMessage('');
      await doSendMessage(messageToSend);
    }
  };

  // Handle accepting a favorite suggestion
  const handleAcceptFavorite = async (favoriteId: string) => {
    try {
      const response = await api.copyFavoriteToConversation(favoriteId);
      // Navigate to the new conversation
      const newConv = await api.getConversation(response.conversation_id);
      setCurrentConversation(newConv as ConversationWithStats);
      // Clear the suggestion state
      setFavoriteSuggestions([]);
      setPendingQuestionForFavorites('');
      setInputMessage('');
      // Reload conversations to show the new one
      await loadConversations();
    } catch (error) {
      console.error('Error copying favorite:', error);
      alert('Erreur lors de la copie du favori');
    }
  };

  // Handle declining favorite suggestions
  const handleDeclineFavorites = async () => {
    const messageToSend = pendingQuestionForFavorites;
    setFavoriteSuggestions([]);
    setPendingQuestionForFavorites('');
    // Continue with normal RAG flow
    await proceedWithSend(messageToSend);
  };

  // Handle viewing favorite detail
  const handleViewFavoriteDetail = (favorite: FavoriteSearchResult) => {
    setSelectedFavoriteForDetail(favorite);
  };

  // Handle using a suggestion from the interactive modal
  const handleUseSuggestion = async (suggestion: string) => {
    setPreAnalyzeResult(null);
    setPendingMessage('');
    setInputMessage('');
    await doSendMessage(suggestion);
  };

  // Handle sending the original question anyway
  const handleSendAnyway = async () => {
    const messageToSend = pendingMessage;
    setPreAnalyzeResult(null);
    setPendingMessage('');
    setInputMessage('');
    await doSendMessage(messageToSend);
  };

  // Handle canceling the interactive modal
  const handleCancelInteractive = () => {
    setPreAnalyzeResult(null);
    setPendingMessage('');
    // Keep the input message so user can edit it
  };

  // Relancer la recherche avec le mode hybride opposé
  const relaunchWithMode = async (hybridMode: boolean) => {
    if (!currentConversation || messages.length === 0) return;

    // 1. Trouver le premier message utilisateur
    const firstUserMessage = messages.find(m => m.role === 'user');
    if (!firstUserMessage) return;

    setIsLoading(true);

    // Get current universe for the new conversation (fallback to default universe)
    const currentUniverseId = selectedUniverseIds.length > 0
      ? selectedUniverseIds[0]
      : (defaultUniverseId || undefined);
    const currentUniverse = currentUniverseId ? universes.find(u => u.id === currentUniverseId) : undefined;

    try {
      // 2. Créer nouvelle conversation avec l'univers
      const newConversation = await api.createConversation({
        title: 'Nouvelle conversation',
        provider: provider as 'mistral' | 'chocolatine',
        use_tools: useTools,
        universe_id: currentUniverseId,
      });

      // 3. Mettre à jour les settings hybrides de la nouvelle conversation
      await api.updateConversation(newConversation.id, {
        hybrid_search_enabled: hybridMode,
        hybrid_search_alpha: 0.5,
      });

      // 4. Mettre à jour le state local (with stats and universe info)
      const updatedConversation: ConversationWithStats = {
        ...newConversation,
        hybrid_search_enabled: hybridMode,
        hybrid_search_alpha: 0.5,
        thumbs_up_count: 0,
        thumbs_down_count: 0,
        universe_id: currentUniverseId,
        universe_name: currentUniverse?.name,
        universe_color: currentUniverse?.color,
      };
      setCurrentConversation(updatedConversation);
      setConversations([updatedConversation, ...conversations]);
      setMessages([]);

      // 5. Envoyer le message original avec le nouveau mode
      const response = await api.sendMessage({
        conversation_id: newConversation.id,
        message: firstUserMessage.content,
        provider,
        use_tools: useTools,
        reranking_enabled: false,
        universe_ids: selectedUniverseIds.length > 0 ? selectedUniverseIds : undefined,
        search_all_universes: searchAllUniverses,
        hybrid_search_enabled: hybridMode,
        hybrid_search_alpha: 0.5,
      });

      setMessages([response.user_message, response.assistant_message]);

      // Mettre à jour la conversation dans la liste (preserve stats and universe data)
      const responseConvWithStats: ConversationWithStats = {
        ...response.conversation,
        thumbs_up_count: 0,
        thumbs_down_count: 0,
        // Fallback: preserve universe data if not in response
        universe_id: response.conversation.universe_id ?? newConversation.universe_id,
        universe_name: response.conversation.universe_name ?? newConversation.universe_name,
        universe_color: response.conversation.universe_color ?? newConversation.universe_color,
      };
      setConversations(convs =>
        convs.map(c => c.id === newConversation.id ? responseConvWithStats : c)
      );
    } catch (error) {
      console.error('Error relaunching with hybrid mode:', error);
      alert('Erreur lors de la relance de la recherche');
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
      console.log('🎯 Rating message:', messageId, 'with rating:', rating);
      await api.rateMessage(messageId, { rating });
      console.log('✅ Rating successful');

      // Mettre à jour optimistiquement le state local
      setMessages(msgs =>
        msgs.map(m => m.id === messageId ? { ...m, rating } : m)
      );

      // Recharger les messages depuis la base pour avoir le rating persisté
      if (currentConversation) {
        await loadMessages(currentConversation.id);
      }
    } catch (error) {
      console.error('❌ Error rating message:', error);
      alert(`Erreur lors du rating: ${error}`);
    }
  };

  const copyMessage = (content: string) => {
    navigator.clipboard.writeText(content);
  };

  const handleRenameConversation = async (id: string, newTitle: string) => {
    if (!newTitle.trim()) {
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
    } catch (error) {
      console.error('Error deleting conversation:', error);
      alert('Erreur lors de la suppression');
    }
  };

  const handleArchiveConversation = async (id: string) => {
    try {
      const updated = await api.archiveConversation(id);
      setConversations(convs =>
        convs.map(c => c.id === id ? { ...c, is_archived: updated.is_archived } : c)
      );
      if (currentConversation?.id === id) {
        setCurrentConversation({ ...currentConversation, is_archived: updated.is_archived });
      }
    } catch (error) {
      console.error('Error archiving conversation:', error);
      alert('Erreur lors de l\'archivage');
    }
  };

  const handleUnarchiveConversation = async (id: string) => {
    try {
      const updated = await api.unarchiveConversation(id);
      setConversations(convs =>
        convs.map(c => c.id === id ? { ...c, is_archived: updated.is_archived } : c)
      );
      if (currentConversation?.id === id) {
        setCurrentConversation({ ...currentConversation, is_archived: updated.is_archived });
      }
    } catch (error) {
      console.error('Error unarchiving conversation:', error);
      alert('Erreur lors de la désarchivage');
    }
  };

  const refreshConversations = () => {
    loadConversations();
  };

  const handleBulkArchive = async (olderThanDays: number) => {
    // Find conversations older than specified days
    const cutoffDate = new Date();
    cutoffDate.setDate(cutoffDate.getDate() - olderThanDays);

    const toArchive = conversations.filter(c => {
      const convDate = new Date(c.updated_at);
      return !c.is_archived && convDate < cutoffDate;
    });

    if (toArchive.length === 0) {
      alert('Aucune conversation à archiver');
      return;
    }

    try {
      await api.bulkArchiveConversations(toArchive.map(c => c.id));
      await loadConversations();
    } catch (error) {
      console.error('Error bulk archiving:', error);
      alert('Erreur lors de l\'archivage');
    }
  };

  const handleBulkDelete = async (archived: boolean) => {
    const toDelete = conversations.filter(c => archived ? c.is_archived : true);

    if (toDelete.length === 0) {
      alert('Aucune conversation à supprimer');
      return;
    }

    if (!confirm(`Êtes-vous sûr de vouloir supprimer ${toDelete.length} conversations ?`)) {
      return;
    }

    try {
      await api.bulkDeleteConversations(toDelete.map(c => c.id), true);
      await loadConversations();
    } catch (error) {
      console.error('Error bulk deleting:', error);
      alert('Erreur lors de la suppression');
    }
  };

  return (
    <div className="flex h-screen bg-gray-50 dark:bg-gray-900">
      {/* Sidebar */}
      <ConversationSidebar
        isOpen={sidebarOpen}
        conversations={conversations}
        currentConversation={currentConversation}
        onSelectConversation={setCurrentConversation}
        onNewConversation={() => createNewConversation()}
        onRenameConversation={handleRenameConversation}
        onDeleteConversation={handleDeleteConversation}
        onArchiveConversation={handleArchiveConversation}
        onUnarchiveConversation={handleUnarchiveConversation}
        onOpenSettings={() => setShowConversationSettings(true)}
        onRefreshConversations={refreshConversations}
        onReloadConversations={loadConversations}
        username={currentUser?.username}
        universes={universes}
        currentUniverseId={selectedUniverseIds[0]}
      />

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
            <h1 className="font-semibold text-lg truncate max-w-sm">
              {currentConversation?.title || 'RAGFab'}
            </h1>
            {currentConversation && (
              <div className="flex items-center gap-3">
                <UniverseSelector
                  selectedUniverseIds={selectedUniverseIds}
                  searchAllUniverses={searchAllUniverses}
                  onChange={async (universeIds, searchAll) => {
                    setSelectedUniverseIds(universeIds);
                    setSearchAllUniverses(searchAll);

                    // Si conversation vide (0 messages) ET un univers spécifique sélectionné, mettre à jour son univers
                    // Note: Si "Tous les univers" (universeIds vide), on garde l'univers actuel
                    if (currentConversation && currentConversation.message_count === 0 && universeIds.length > 0) {
                      const newUniverseId = universeIds[0];
                      // Ne pas appeler l'API si l'univers est déjà le même
                      if (newUniverseId !== currentConversation.universe_id) {
                        try {
                          await api.moveConversationToUniverse(
                            currentConversation.id,
                            newUniverseId
                          );
                          // Récupérer les infos de l'univers depuis le state (l'API ne retourne pas universe_name/color)
                          const targetUniverse = universes.find(u => u.id === newUniverseId);
                          const universeName = targetUniverse?.name;
                          const universeColor = targetUniverse?.color;
                          // Mettre à jour le state local
                          setCurrentConversation(prev => prev ? {
                            ...prev,
                            universe_id: newUniverseId,
                            universe_name: universeName,
                            universe_color: universeColor,
                          } : null);
                          // Mettre à jour dans la liste des conversations
                          setConversations(prev => prev.map(c =>
                            c.id === currentConversation.id
                              ? { ...c, universe_id: newUniverseId, universe_name: universeName, universe_color: universeColor }
                              : c
                          ));
                        } catch (error) {
                          console.error('Erreur mise à jour univers conversation:', error);
                        }
                      }
                    }
                  }}
                  compact={true}
                />
                <div className="h-6 w-px bg-gray-300 dark:bg-gray-600"></div>
                <RerankingToggle
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
                <div className="h-6 w-px bg-gray-300 dark:bg-gray-600"></div>
                <HybridSearchToggle
                  conversationId={currentConversation.id}
                  onChange={(enabled, alpha) => {
                    console.log('🔀 Hybrid search settings:', { enabled, alpha });
                    // Mettre à jour le state local de la conversation
                    setCurrentConversation({
                      ...currentConversation,
                      hybrid_search_enabled: enabled,
                      hybrid_search_alpha: alpha,
                    });
                    // Mettre à jour dans la liste des conversations
                    setConversations(convs =>
                      convs.map(c =>
                        c.id === currentConversation.id
                          ? { ...c, hybrid_search_enabled: enabled, hybrid_search_alpha: alpha }
                          : c
                      )
                    );
                  }}
                />
              </div>
            )}
          </div>

          <div className="flex items-center gap-2">
            {/* Settings button hidden - kept for future reactivation
            <button
              onClick={() => setShowSettings(!showSettings)}
              className="btn-ghost"
              title="Paramètres"
            >
              <Settings size={20} />
            </button>
            */}
            <button
              onClick={toggleTheme}
              className="btn-ghost"
              title={theme === 'light' ? 'Mode sombre' : 'Mode clair'}
            >
              {theme === 'light' ? <Moon size={20} /> : <Sun size={20} />}
            </button>

            {/* User Menu */}
            {currentUser && (
              <>
                <div className="h-6 w-px bg-gray-300 dark:bg-gray-600 mx-1"></div>
                <UserMenu user={currentUser} onLogout={handleLogout} />
              </>
            )}
          </div>
        </div>

        {/* Settings Panel - Hidden but kept for future reactivation
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
        */}

        {/* Messages */}
        <div className="flex-1 overflow-y-auto custom-scrollbar">
          {/* Favorite Suggestion Banner */}
          {favoriteSuggestions.length > 0 && (
            <div className="max-w-3xl mx-auto pt-4">
              <FavoriteSuggestionBanner
                suggestions={favoriteSuggestions}
                onAccept={handleAcceptFavorite}
                onDecline={handleDeclineFavorites}
                onViewDetail={handleViewFavoriteDetail}
              />
            </div>
          )}

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
                    className={`w-8 h-8 rounded-full flex items-center justify-center text-white ${
                      message.role === 'user'
                        ? 'bg-blue-500'
                        : 'bg-cyan-500 dark:bg-cyan-600'
                    }`}
                  >
                    {message.role === 'user' ? <UserIcon className="w-5 h-5" /> : <Bot className="w-5 h-5" />}
                  </div>
                  <div className="flex-1 min-w-0">
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
                        <div className="space-y-3">
                          {message.sources.map((source: any, i: number) => (
                            <div key={i} className="space-y-2">
                              <div
                                onClick={() => setSelectedDocument({
                                  documentId: source.document_id,
                                  chunkIds: (message.sources || [])
                                    .filter((s: any) => s.document_id === source.document_id)
                                    .map((s: any) => s.chunk_id),
                                  initialChunkId: source.chunk_id
                                })}
                                className="text-sm text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 p-2 rounded border border-gray-200 dark:border-gray-700 cursor-pointer hover:border-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-all"
                              >
                                <div className="font-medium text-blue-600 dark:text-blue-400 flex items-center gap-2">
                                  {source.is_image_chunk ? '🖼️' : '📄'} {source.document_title}
                                  <span className="text-xs text-gray-400">→ Voir le document</span>
                                </div>
                                <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                                  Chunk #{source.chunk_index} • Similarité: {(source.similarity * 100).toFixed(1)}%
                                  {source.is_image_chunk && <span className="ml-2 text-purple-500">• Image</span>}
                                </div>
                                {/* Only show text content for non-image chunks */}
                                {!source.is_image_chunk && (
                                  <div className="text-xs text-gray-600 dark:text-gray-400 mt-1 italic">
                                    "{source.content}"
                                  </div>
                                )}
                              </div>

                              {/* Display images inline if available */}
                              {source.images && source.images.length > 0 && (
                                <div className="pl-2">
                                  <ImageViewer
                                    images={source.images}
                                    documentTitle={source.document_title}
                                  />
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Afficher la réponse formatée sauvegardée (si existe) */}
                    {message.role === 'assistant' && message.id && formattedResponses.get(message.id) && (
                      <div className="mt-4 bg-green-50 border border-green-200 rounded-lg p-4 space-y-3">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-semibold text-green-800">
                              ✅ Réponse formatée ITOP
                            </span>
                          </div>
                          <button
                            onClick={() => {
                              const formatted = formattedResponses.get(message.id);
                              if (formatted) {
                                navigator.clipboard.writeText(formatted.formatted_content);
                              }
                            }}
                            className="inline-flex items-center gap-1 px-3 py-1.5 text-sm font-medium text-green-700 bg-white border border-green-300 rounded-md hover:bg-green-50 transition-colors"
                            title="Copier pour ITOP"
                          >
                            <Copy className="w-4 h-4" />
                            Copier pour ITOP
                          </button>
                        </div>

                        <div className="bg-white border border-green-200 rounded p-3 text-sm text-gray-800 whitespace-pre-wrap font-sans leading-relaxed">
                          {formattedResponses.get(message.id)?.formatted_content}
                        </div>
                      </div>
                    )}

                    {/* Templates de réponse pour ITOP */}
                    {message.role === 'assistant' && templates.length > 0 && (
                      <ResponseTemplates
                        originalResponse={message.content}
                        conversationId={currentConversation?.id}
                        messageId={message.id}
                        templates={templates}
                        onFormatted={async () => {
                          // Recharger la formatted_response depuis la base après application du template
                          if (message.id) {
                            const formatted = await api.getFormattedResponse(message.id);
                            if (formatted) {
                              setFormattedResponses(new Map(formattedResponses.set(message.id, formatted)));
                            }
                          }
                        }}
                      />
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
                          onClick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            rateMessage(message.id, 1);
                          }}
                          className={`btn-ghost p-1 ${
                            message.rating === 1 ? 'text-green-500' : ''
                          }`}
                          title="Bon"
                          type="button"
                        >
                          <ThumbsUp size={16} />
                        </button>
                        <button
                          onClick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            rateMessage(message.id, -1);
                          }}
                          className={`btn-ghost p-1 ${
                            message.rating === -1 ? 'text-red-500' : ''
                          }`}
                          title="Mauvais"
                          type="button"
                        >
                          <ThumbsDown size={16} />
                        </button>
                        {/* Icône relance en mode hybride (si mode actuel = normal) */}
                        {!currentConversation?.hybrid_search_enabled && (
                          <button
                            onClick={() => relaunchWithMode(true)}
                            className="btn-ghost p-1"
                            title="Relancer en recherche hybride"
                            disabled={isLoading}
                          >
                            <div className="relative">
                              <Search size={16} />
                              <Zap size={10} className="absolute -bottom-1 -right-1 text-yellow-500" />
                            </div>
                          </button>
                        )}
                        {/* Icône relance en mode normal (si mode actuel = hybride) */}
                        {currentConversation?.hybrid_search_enabled && (
                          <button
                            onClick={() => relaunchWithMode(false)}
                            className="btn-ghost p-1"
                            title="Relancer en recherche normale"
                            disabled={isLoading}
                          >
                            <Search size={16} />
                          </button>
                        )}
                      </div>
                    )}

                    {/* Suggestions de reformulation (si analyse de qualité disponible) */}
                    {message.role === 'assistant' && qualityAnalyses.has(message.id) && (
                      <QuestionSuggestions
                        qualityAnalysis={qualityAnalyses.get(message.id)!}
                        onSuggestionClick={(suggestion) => {
                          setInputMessage(suggestion);
                          inputRef.current?.focus();
                          // Optionnellement, supprimer l'analyse après utilisation
                          setQualityAnalyses(prev => {
                            const newMap = new Map(prev);
                            newMap.delete(message.id);
                            return newMap;
                          });
                        }}
                        onDismiss={() => {
                          setQualityAnalyses(prev => {
                            const newMap = new Map(prev);
                            newMap.delete(message.id);
                            return newMap;
                          });
                        }}
                      />
                    )}
                  </div>
                </div>
              </div>
            ))}

            {/* Typing indicator */}
            {isLoading && (
              <div className="flex items-start gap-3 mb-6">
                <div className="w-8 h-8 rounded-full bg-cyan-500 dark:bg-cyan-600 flex items-center justify-center text-white">
                  <Bot className="w-5 h-5" />
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
            <div className="relative flex-1">
              <input
                ref={inputRef}
                type="text"
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
                placeholder={isPreAnalyzing ? "Analyse en cours..." : "Posez votre question..."}
                className="input w-full"
                disabled={isLoading || isPreAnalyzing || !currentConversation}
              />
              {isPreAnalyzing && (
                <div className="absolute right-3 top-1/2 -translate-y-1/2">
                  <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
                </div>
              )}
            </div>
            <button
              onClick={sendMessage}
              disabled={!inputMessage.trim() || isLoading || isPreAnalyzing || !currentConversation}
              className="btn-primary"
            >
              <Send size={20} />
            </button>
          </div>
          {/* Interactive mode indicator */}
          {currentUser?.suggestion_mode === 'interactive' && (
            <div className="max-w-3xl mx-auto mt-2">
              <span className="text-xs text-amber-600 dark:text-amber-400 flex items-center gap-1">
                <span className="w-2 h-2 bg-amber-500 rounded-full"></span>
                Mode interactif actif - Vos questions seront analysees avant envoi
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Document View Modal */}
      {selectedDocument && (
        <DocumentViewModal
          documentId={selectedDocument.documentId}
          chunkIds={selectedDocument.chunkIds}
          initialChunkId={selectedDocument.initialChunkId}
          onClose={() => setSelectedDocument(null)}
        />
      )}

      {/* Change Password Modal (blocking if must_change_password=true) */}
      {mustChangePassword && (
        <ChangePasswordModal
          isFirstLogin={true}
          onPasswordChanged={handlePasswordChanged}
          onSubmit={handlePasswordSubmit}
        />
      )}

      {/* Interactive Suggestion Modal (pre-analyze mode) */}
      {preAnalyzeResult && (
        <InteractiveSuggestionModal
          preAnalysis={preAnalyzeResult}
          onUseSuggestion={handleUseSuggestion}
          onSendAnyway={handleSendAnyway}
          onCancel={handleCancelInteractive}
          isLoading={isLoading}
        />
      )}

      {/* Conversation Settings Modal */}
      <ConversationSettings
        isOpen={showConversationSettings}
        onClose={() => setShowConversationSettings(false)}
        onBulkArchive={handleBulkArchive}
        onBulkDelete={handleBulkDelete}
      />

      {/* Favorite Detail Modal (from suggestion banner) */}
      {selectedFavoriteForDetail && (
        <FavoriteDetailModal
          favorite={selectedFavoriteForDetail as SharedFavorite}
          onClose={() => setSelectedFavoriteForDetail(null)}
          onCopy={handleAcceptFavorite}
        />
      )}
    </div>
  );
}
