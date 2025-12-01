import axios, { AxiosInstance, AxiosError } from 'axios';
import type {
  LoginRequest,
  TokenResponse,
  User,
  DocumentStats,
  DocumentListParams,
  DocumentListResponse,
  UniverseDocumentCounts,
  Chunk,
  IngestionJob,
  Conversation,
  ConversationWithStats,
  Message,
  ChatRequest,
  ChatResponseWithQuality,
  RatingCreate,
  UserCreate,
  UserUpdate,
  UserResponse,
  UserListResponse,
  ProductUniverse,
  ProductUniverseCreate,
  ProductUniverseUpdate,
  UserUniverseAccess,
  PreAnalyzeRequest,
  PreAnalyzeResponse,
  // Conversation Management
  ConversationCreate,
  ConversationUpdate,
  ConversationPreferences,
  ConversationPreferencesUpdate,
  ConversationStats,
  ConversationSearchResult,
  BulkActionResponse,
  // Shared Favorites
  SharedFavorite,
  FavoriteSearchResult,
  FavoriteListResponse,
  FavoriteSuggestionResponse,
  FavoriteCopyResponse,
  FavoriteUpdate,
  FavoriteValidation,
} from '../types';
import type {
  ThumbsDownStats,
  ThumbsDownValidation,
  ValidationUpdate,
  PendingValidationsResponse,
  AllValidationsResponse,
  UsersToContactResponse,
  ReingestionCandidatesResponse,
  ThumbsDownFilters,
} from '../types/thumbsDown';

const API_URL = (import.meta as any).env?.VITE_API_URL || '';

class APIClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_URL,
      headers: {
        'Content-Type': 'application/json',
      },
      // Pas de limite de taille pour les uploads
      maxBodyLength: Infinity,
      maxContentLength: Infinity,
    });

    // Intercepteur pour ajouter le token JWT
    this.client.interceptors.request.use((config) => {
      const token = localStorage.getItem('access_token');
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    });

    // Intercepteur pour gérer les erreurs
    this.client.interceptors.response.use(
      (response) => response,
      (error: AxiosError) => {
        if (error.response?.status === 401) {
          // Token expiré, déconnecter l'utilisateur
          localStorage.removeItem('access_token');
          window.location.href = '/admin';
        }
        return Promise.reject(error);
      }
    );
  }

  // ============================================================================
  // Auth
  // ============================================================================

  async login(credentials: LoginRequest): Promise<TokenResponse> {
    const { data } = await this.client.post<TokenResponse>('/api/auth/login', credentials);
    localStorage.setItem('access_token', data.access_token);
    return data;
  }

  async getCurrentUser(): Promise<User> {
    const { data } = await this.client.get<User>('/api/auth/me');
    return data;
  }

  async logout(): Promise<void> {
    await this.client.post('/api/auth/logout');
    localStorage.removeItem('access_token');
  }

  async checkMustChangePassword(): Promise<{ must_change_password: boolean }> {
    const { data } = await this.client.get('/api/auth/me/must-change-password');
    return data;
  }

  async updateMyProfile(profileData: import('../types').UserProfileUpdate): Promise<User> {
    const { data } = await this.client.patch<User>('/api/auth/me/profile', profileData);
    return data;
  }

  async changeMyPassword(passwordData: import('../types').PasswordChange): Promise<{ message: string }> {
    const { data } = await this.client.post('/api/auth/me/change-password', passwordData);
    return data;
  }

  async changeFirstLoginPassword(passwordData: import('../types').PasswordChange): Promise<{ message: string }> {
    const { data } = await this.client.post('/api/auth/me/first-password-change', passwordData);
    return data;
  }

  async getMyPreferences(): Promise<import('../types').UserPreferencesResponse> {
    const { data } = await this.client.get('/api/auth/me/preferences');
    return data;
  }

  async updateMyPreferences(preferences: import('../types').UserPreferencesUpdate): Promise<import('../types').UserPreferencesResponse> {
    const { data } = await this.client.put('/api/auth/me/preferences', preferences);
    return data;
  }

  // ============================================================================
  // Documents
  // ============================================================================

  async getDocuments(params: DocumentListParams = {}): Promise<DocumentListResponse> {
    const { data } = await this.client.get<DocumentListResponse>('/api/documents', {
      params: {
        page: params.page || 1,
        page_size: params.page_size || 20,
        universe_id: params.universe_id || undefined,
        no_universe: params.no_universe || undefined,
        search: params.search || undefined,
        sort_by: params.sort_by || 'created_at',
        order: params.order || 'desc',
      },
    });
    return data;
  }

  async getUniverseDocumentCounts(): Promise<UniverseDocumentCounts> {
    const { data } = await this.client.get<UniverseDocumentCounts>('/api/universes/documents/counts');
    return data;
  }

  async getDocument(id: string): Promise<DocumentStats> {
    const { data} = await this.client.get<DocumentStats>(`/api/documents/${id}`);
    return data;
  }

  async getDocumentChunks(id: string, limit = 100, offset = 0): Promise<Chunk[]> {
    const { data } = await this.client.get<Chunk[]>(`/api/documents/${id}/chunks`, {
      params: { limit, offset },
    });
    return data;
  }

  async getDocumentView(id: string): Promise<{
    document: {
      id: string;
      title: string;
      source: string;
      content: string;
      created_at: string;
    };
    chunks: Array<{
      id: string;
      content: string;
      chunk_index: number;
    }>;
  }> {
    const { data } = await this.client.get(`/api/documents/${id}/view`);
    return data;
  }

  async uploadDocument(
    file: File,
    ocrEngine: 'rapidocr' | 'easyocr' | 'tesseract' = 'rapidocr',
    vlmEngine: 'paddleocr-vl' | 'internvl' | 'none' = 'paddleocr-vl',
    chunkerType: 'hybrid' | 'parent_child' = 'hybrid',
    universeId?: string
  ): Promise<{ job_id: string; filename: string; status: string; universe_id?: string; message: string }> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('ocr_engine', ocrEngine);
    formData.append('vlm_engine', vlmEngine);
    formData.append('chunker_type', chunkerType);
    if (universeId) {
      formData.append('universe_id', universeId);
    }

    const { data } = await this.client.post('/api/admin/documents/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return data;
  }

  async getIngestionJob(jobId: string): Promise<IngestionJob> {
    const { data } = await this.client.get<IngestionJob>(`/api/admin/documents/jobs/${jobId}`);
    return data;
  }

  async deleteDocument(id: string): Promise<void> {
    await this.client.delete(`/api/documents/${id}`);
  }

  async reingestDocument(
    documentId: string,
    config: {
      ocr_engine: 'rapidocr' | 'easyocr' | 'tesseract';
      vlm_engine: 'paddleocr-vl' | 'internvl' | 'none';
      chunker_type: 'hybrid' | 'parent_child';
    }
  ): Promise<{ job_id: string; message: string; old_document_id: string; new_job_id: string }> {
    const { data } = await this.client.post(`/api/admin/documents/${documentId}/reingest`, config);
    return data;
  }

  // ============================================================================
  // Conversations
  // ============================================================================

  async getConversations(
    limit = 50,
    offset = 0,
    includeArchived = false,
    universeId?: string
  ): Promise<ConversationWithStats[]> {
    const params: any = { limit, offset, include_archived: includeArchived };
    if (universeId) {
      params.universe_id = universeId;
    }
    const { data } = await this.client.get<ConversationWithStats[]>('/api/conversations', { params });
    return data;
  }

  async createConversation(
    titleOrConfig?: string | ConversationCreate,
    provider = 'mistral',
    useTools = true
  ): Promise<Conversation> {
    // Support both old signature (title, provider, useTools) and new signature (ConversationCreate)
    let payload: ConversationCreate;

    if (typeof titleOrConfig === 'object') {
      payload = titleOrConfig;
    } else {
      payload = {
        title: titleOrConfig || 'Nouvelle conversation',
        provider: provider as 'mistral' | 'chocolatine',
        use_tools: useTools,
      };
    }

    const { data } = await this.client.post<Conversation>('/api/conversations', payload);
    return data;
  }

  async getConversation(id: string): Promise<Conversation> {
    const { data } = await this.client.get<Conversation>(`/api/conversations/${id}`);
    return data;
  }

  async updateConversation(id: string, updates: ConversationUpdate): Promise<Conversation> {
    const { data } = await this.client.patch<Conversation>(`/api/conversations/${id}`, updates);
    return data;
  }

  async deleteConversation(id: string): Promise<void> {
    await this.client.delete(`/api/conversations/${id}`);
  }

  // ============================================================================
  // Conversation Management
  // ============================================================================

  async getConversationPreferences(): Promise<ConversationPreferences> {
    const { data } = await this.client.get<ConversationPreferences>('/api/me/conversation-preferences');
    return data;
  }

  async updateConversationPreferences(
    preferences: ConversationPreferencesUpdate
  ): Promise<ConversationPreferences> {
    const { data } = await this.client.put<ConversationPreferences>(
      '/api/me/conversation-preferences',
      preferences
    );
    return data;
  }

  async getConversationStats(): Promise<ConversationStats> {
    const { data } = await this.client.get<ConversationStats>('/api/conversations/stats');
    return data;
  }

  async archiveConversation(id: string): Promise<Conversation> {
    const { data } = await this.client.post<Conversation>(`/api/conversations/${id}/archive`);
    return data;
  }

  async unarchiveConversation(id: string): Promise<Conversation> {
    const { data } = await this.client.post<Conversation>(`/api/conversations/${id}/unarchive`);
    return data;
  }

  async bulkArchiveConversations(conversationIds: string[]): Promise<BulkActionResponse> {
    const { data } = await this.client.post<BulkActionResponse>('/api/conversations/bulk/archive', {
      conversation_ids: conversationIds,
    });
    return data;
  }

  async bulkDeleteConversations(conversationIds: string[], confirm = true): Promise<BulkActionResponse> {
    const { data } = await this.client.post<BulkActionResponse>('/api/conversations/bulk/delete', {
      conversation_ids: conversationIds,
      confirm,
    });
    return data;
  }

  async searchConversations(
    query: string,
    options?: {
      universeId?: string;
      includeArchived?: boolean;
      searchMessages?: boolean;
      limit?: number;
      offset?: number;
    }
  ): Promise<ConversationSearchResult[]> {
    const params: any = { q: query };
    if (options?.universeId) params.universe_id = options.universeId;
    if (options?.includeArchived !== undefined) params.include_archived = options.includeArchived;
    if (options?.searchMessages !== undefined) params.search_messages = options.searchMessages;
    if (options?.limit) params.limit = options.limit;
    if (options?.offset) params.offset = options.offset;

    const { data } = await this.client.get<ConversationSearchResult[]>('/api/conversations/search', {
      params,
    });
    return data;
  }

  async moveConversationToUniverse(conversationId: string, universeId: string | null): Promise<Conversation> {
    return this.updateConversation(conversationId, { universe_id: universeId || undefined });
  }

  // ============================================================================
  // Messages
  // ============================================================================

  async getConversationMessages(conversationId: string, limit = 100, offset = 0): Promise<Message[]> {
    const { data } = await this.client.get<Message[]>(`/api/conversations/${conversationId}/messages`, {
      params: { limit, offset },
    });
    return data;
  }

  async sendMessage(request: ChatRequest): Promise<ChatResponseWithQuality> {
    const { data } = await this.client.post<ChatResponseWithQuality>('/api/chat', request);
    return data;
  }

  async preAnalyzeQuestion(request: PreAnalyzeRequest): Promise<PreAnalyzeResponse> {
    const { data } = await this.client.post<PreAnalyzeResponse>('/api/chat/pre-analyze', request);
    return data;
  }

  async regenerateMessage(messageId: string): Promise<Message> {
    const { data } = await this.client.post<Message>(`/api/messages/${messageId}/regenerate`);
    return data;
  }

  async rateMessage(messageId: string, rating: RatingCreate): Promise<void> {
    await this.client.post(`/api/messages/${messageId}/rate`, rating);
  }

  // ============================================================================
  // Export
  // ============================================================================

  async exportConversation(conversationId: string, format: 'markdown' | 'pdf'): Promise<Blob> {
    const { data } = await this.client.post(
      `/api/conversations/${conversationId}/export`,
      { format },
      { responseType: 'blob' }
    );
    return data;
  }

  // ============================================================================
  // Health
  // ============================================================================

  async healthCheck(): Promise<{ status: string; database: string; timestamp: string }> {
    const { data } = await this.client.get('/health');
    return data;
  }

  // ============================================================================
  // User Management (Admin)
  // ============================================================================

  async listUsers(limit = 100, offset = 0, is_active?: boolean, is_admin?: boolean): Promise<UserListResponse[]> {
    const params: any = { limit, offset };
    if (is_active !== undefined) params.is_active = is_active;
    if (is_admin !== undefined) params.is_admin = is_admin;

    const { data } = await this.client.get<UserListResponse[]>('/api/admin/users', { params });
    return data;
  }

  async createUser(userData: UserCreate): Promise<UserResponse> {
    const { data } = await this.client.post<UserResponse>('/api/admin/users', userData);
    return data;
  }

  async getUser(userId: string): Promise<UserResponse> {
    const { data } = await this.client.get<UserResponse>(`/api/admin/users/${userId}`);
    return data;
  }

  async updateUser(userId: string, updates: UserUpdate): Promise<UserResponse> {
    const { data } = await this.client.patch<UserResponse>(`/api/admin/users/${userId}`, updates);
    return data;
  }

  async deleteUser(userId: string): Promise<void> {
    await this.client.delete(`/api/admin/users/${userId}`);
  }

  async resetUserPassword(userId: string, newPassword: string): Promise<void> {
    await this.client.post(`/api/admin/users/${userId}/reset-password`, { new_password: newPassword });
  }

  // ============================================================================
  // Universes
  // ============================================================================

  // Liste tous les univers (actifs par défaut)
  async getUniverses(includeInactive = false): Promise<{ universes: ProductUniverse[]; total: number }> {
    const { data } = await this.client.get('/api/universes', {
      params: { include_inactive: includeInactive },
    });
    return data;
  }

  // Récupère un univers par ID
  async getUniverse(universeId: string): Promise<ProductUniverse> {
    const { data } = await this.client.get<ProductUniverse>(`/api/universes/${universeId}`);
    return data;
  }

  // Crée un nouvel univers (admin)
  async createUniverse(universeData: ProductUniverseCreate): Promise<ProductUniverse> {
    const { data } = await this.client.post<ProductUniverse>('/api/universes', universeData);
    return data;
  }

  // Met à jour un univers (admin)
  async updateUniverse(universeId: string, updates: ProductUniverseUpdate): Promise<ProductUniverse> {
    const { data } = await this.client.patch<ProductUniverse>(`/api/universes/${universeId}`, updates);
    return data;
  }

  // Supprime un univers (admin)
  async deleteUniverse(universeId: string): Promise<void> {
    await this.client.delete(`/api/universes/${universeId}`);
  }

  // ============================================================================
  // User Universe Access (Current User)
  // ============================================================================

  // Récupère les univers auxquels l'utilisateur courant a accès
  async getMyUniverseAccess(): Promise<UserUniverseAccess[]> {
    const { data } = await this.client.get<UserUniverseAccess[]>('/api/universes/me/access');
    return data;
  }

  // Définit l'univers par défaut de l'utilisateur courant
  async setMyDefaultUniverse(universeId: string): Promise<UserUniverseAccess> {
    const { data } = await this.client.post<UserUniverseAccess>('/api/universes/me/set-default', {
      universe_id: universeId,
    });
    return data;
  }

  // Récupère l'univers par défaut de l'utilisateur courant
  async getMyDefaultUniverse(): Promise<{ default_universe: UserUniverseAccess | null }> {
    const { data } = await this.client.get('/api/universes/me/default');
    return data;
  }

  // ============================================================================
  // User Universe Access Management (Admin)
  // ============================================================================

  // Récupère les accès univers d'un utilisateur (admin)
  async getUserUniverseAccess(userId: string): Promise<{
    user_id: string;
    username: string;
    accesses: UserUniverseAccess[];
    total: number;
  }> {
    const { data } = await this.client.get(`/api/universes/users/${userId}/access`);
    return data;
  }

  // Accorde l'accès à un univers pour un utilisateur (admin)
  async grantUniverseAccess(
    userId: string,
    universeId: string,
    isDefault = false
  ): Promise<UserUniverseAccess> {
    const { data } = await this.client.post<UserUniverseAccess>(
      `/api/universes/users/${userId}/access`,
      { universe_id: universeId, is_default: isDefault }
    );
    return data;
  }

  // Révoque l'accès à un univers pour un utilisateur (admin)
  async revokeUniverseAccess(userId: string, universeId: string): Promise<void> {
    await this.client.delete(`/api/universes/users/${userId}/access/${universeId}`);
  }

  // Définit l'univers par défaut d'un utilisateur (admin)
  async setUserDefaultUniverse(userId: string, universeId: string): Promise<void> {
    await this.client.post(`/api/universes/users/${userId}/access/${universeId}/set-default`);
  }

  // ============================================================================
  // Document Universe Assignment
  // ============================================================================

  // Récupère le nombre de documents dans un univers
  async getUniverseDocumentCount(universeId: string): Promise<{ universe_id: string; document_count: number }> {
    const { data } = await this.client.get(`/api/universes/${universeId}/documents/count`);
    return data;
  }

  // Assigne un document à un univers (admin)
  async assignDocumentToUniverse(universeId: string, documentId: string): Promise<void> {
    await this.client.post(`/api/universes/${universeId}/documents/${documentId}/assign`);
  }

  // Retire un document de son univers (admin)
  async unassignDocumentFromUniverse(documentId: string): Promise<void> {
    await this.client.post(`/api/universes/documents/${documentId}/unassign`);
  }

  // ============================================================================
  // Response Templates
  // ============================================================================

  async listActiveTemplates(): Promise<any[]> {
    const { data } = await this.client.get('/api/templates');
    return data;
  }

  async applyResponseTemplate(
    templateId: string,
    payload: {
      original_response: string;
      conversation_id?: string;
      message_id?: string;
    }
  ): Promise<{ formatted_response: string; template_used: string; processing_time_ms: number }> {
    const { data } = await this.client.post(`/api/templates/${templateId}/apply`, payload);
    return data;
  }

  async getFormattedResponse(messageId: string): Promise<{
    formatted_content: string;
    template_id: string;
    template_name: string;
    created_at: string;
  } | null> {
    try {
      const { data } = await this.client.get(`/api/templates/formatted/${messageId}`);
      return data;
    } catch (error) {
      // Si 404 ou autre erreur, retourner null (pas de version formatée sauvegardée)
      return null;
    }
  }

  async listAllTemplatesAdmin(): Promise<any[]> {
    const { data } = await this.client.get('/api/templates/admin/templates');
    return data;
  }

  async updateTemplateAdmin(templateId: string, updates: any): Promise<any> {
    const { data} = await this.client.put(`/api/templates/admin/templates/${templateId}`, updates);
    return data;
  }

  // ============================================================================
  // Analytics
  // ============================================================================

  async getAnalyticsSummary(days = 30): Promise<any> {
    const { data } = await this.client.get('/api/analytics/ratings/summary', {
      params: { days }
    });
    return data;
  }

  async getWorstChunks(limit = 10, minAppearances = 3): Promise<any[]> {
    const { data } = await this.client.get('/api/analytics/ratings/worst-chunks', {
      params: { limit, min_appearances: minAppearances }
    });
    return data;
  }

  async getWorstDocuments(limit = 10, minAppearances = 5): Promise<any[]> {
    const { data } = await this.client.get('/api/analytics/ratings/worst-documents', {
      params: { limit, min_appearances: minAppearances }
    });
    return data;
  }

  async getRatingsByReranking(days = 30): Promise<any> {
    const { data } = await this.client.get('/api/analytics/ratings/by-reranking', {
      params: { days }
    });
    return data;
  }

  async getRatingsWithFeedback(limit = 50, ratingValue?: number): Promise<any[]> {
    const params: any = { limit };
    if (ratingValue !== undefined) {
      params.rating_value = ratingValue;
    }
    const { data } = await this.client.get('/api/analytics/ratings/with-feedback', { params });
    return data;
  }

  // ============================================================================
  // QUALITY MANAGEMENT ENDPOINTS (Quick Win #4)
  // ============================================================================

  async getBlacklistedChunks(limit = 50): Promise<any[]> {
    const { data } = await this.client.get('/api/analytics/quality/blacklisted-chunks', {
      params: { limit }
    });
    return data;
  }

  async getReingestionRecommendations(limit = 20): Promise<any[]> {
    const { data } = await this.client.get('/api/analytics/quality/reingestion-recommendations', {
      params: { limit }
    });
    return data;
  }

  async getQualityAuditLog(limit = 100, action?: string): Promise<any[]> {
    const params: any = { limit };
    if (action) {
      params.action = action;
    }
    const { data } = await this.client.get('/api/analytics/quality/audit-log', { params });
    return data;
  }

  async unblacklistChunk(chunkId: string, reason: string): Promise<any> {
    const { data } = await this.client.post(`/api/analytics/quality/chunk/${chunkId}/unblacklist`, {
      reason
    });
    return data;
  }

  async whitelistChunk(chunkId: string, reason: string): Promise<any> {
    const { data } = await this.client.post(`/api/analytics/quality/chunk/${chunkId}/whitelist`, {
      reason
    });
    return data;
  }

  async ignoreReingestionRecommendation(documentId: string, reason: string): Promise<any> {
    const { data } = await this.client.post(
      `/api/analytics/quality/document/${documentId}/ignore-recommendation`,
      { reason }
    );
    return data;
  }

  async triggerQualityAnalysis(): Promise<any> {
    const { data } = await this.client.post('/api/analytics/quality/trigger-analysis', {});
    return data;
  }

  async getAnalysisStatus(runId: string): Promise<any> {
    const { data } = await this.client.get(`/api/analytics/quality/analysis-status/${runId}`);
    return data;
  }

  async getAnalysisHistory(limit = 50): Promise<any[]> {
    const { data } = await this.client.get('/api/analytics/quality/analysis-history', {
      params: { limit }
    });
    return data;
  }

  async getReingestionCount(): Promise<{ count: number }> {
    const { data } = await this.client.get('/api/analytics/quality/reingestion-count');
    return data;
  }

  // ============================================================================
  // THUMBS DOWN VALIDATION SYSTEM
  // ============================================================================

  /**
   * Get thumbs down validations pending admin review
   * These are validations where AI confidence < threshold or admin hasn't validated yet
   */
  async getPendingThumbsDownValidations(): Promise<PendingValidationsResponse> {
    const { data } = await this.client.get<PendingValidationsResponse>(
      '/api/analytics/thumbs-down/pending-review'
    );
    return data;
  }

  /**
   * Get all thumbs down validations with optional filters
   * @param filters - Optional filters for classification, admin_action, validation status, etc.
   */
  async getAllThumbsDownValidations(filters?: ThumbsDownFilters): Promise<AllValidationsResponse> {
    const params: any = {};

    if (filters) {
      if (filters.classification) params.classification = filters.classification;
      if (filters.needs_review !== undefined) params.needs_review = filters.needs_review;
      if (filters.admin_action) params.admin_action = filters.admin_action;
      if (filters.validated !== undefined) params.validated = filters.validated;
      if (filters.limit) params.limit = filters.limit;
      if (filters.offset) params.offset = filters.offset;
    }

    const { data } = await this.client.get<AllValidationsResponse>(
      '/api/analytics/thumbs-down/all',
      { params }
    );
    return data;
  }

  /**
   * Validate a thumbs down (admin review)
   * @param validationId - UUID of the validation record
   * @param update - Admin override, notes, and action
   */
  async validateThumbsDown(
    validationId: string,
    update: ValidationUpdate
  ): Promise<{
    validation_id: string;
    final_classification: string;
    actions_taken: string[]
  }> {
    const { data } = await this.client.post(
      `/api/analytics/thumbs-down/${validationId}/validate`,
      update
    );
    return data;
  }

  /**
   * Get a single thumbs down validation by ID with full details
   * @param validationId - UUID of the validation
   * @returns Complete validation object with user info and message content
   */
  async getThumbsDownValidationById(validationId: string): Promise<ThumbsDownValidation> {
    const { data } = await this.client.get<ThumbsDownValidation>(
      `/api/analytics/thumbs-down/validation/${validationId}`
    );
    return data;
  }

  /**
   * Get list of users needing accompaniment (bad_question classifications)
   * These users have submitted questions with poor formulation
   */
  async getUsersToContact(): Promise<UsersToContactResponse> {
    const { data } = await this.client.get<UsersToContactResponse>(
      '/api/analytics/thumbs-down/users-to-contact'
    );
    return data;
  }

  /**
   * Get documents recommended for reingestion (missing_sources classifications)
   * These documents have generated thumbs down due to missing or poor sources
   */
  async getReingestionCandidates(): Promise<ReingestionCandidatesResponse> {
    const { data } = await this.client.get<ReingestionCandidatesResponse>(
      '/api/analytics/thumbs-down/reingestion-candidates'
    );
    return data;
  }

  /**
   * Get thumbs down statistics and temporal distribution
   * @param days - Number of days to include (default: 30)
   */
  async getThumbsDownStats(days = 30): Promise<ThumbsDownStats> {
    const { data } = await this.client.get<ThumbsDownStats>(
      '/api/analytics/thumbs-down/stats',
      { params: { days } }
    );
    return data;
  }

  /**
   * Manually trigger AI analysis for a specific thumbs down rating
   * Useful for re-analyzing or forcing analysis for old ratings
   * @param ratingId - UUID of the message_rating record
   */
  async triggerThumbsDownAnalysis(ratingId: string): Promise<{
    validation_id: string;
    classification: string;
    confidence: number;
    needs_review: boolean;
  }> {
    const { data } = await this.client.post(
      '/api/analytics/thumbs-down/analyze',
      { rating_id: ratingId }
    );
    return data;
  }

  /**
   * Cancel a thumbs down rating (soft delete)
   * Used when admin determines the bad result was due to poorly formulated user question
   * @param validationId - UUID of the validation record
   * @param reason - Admin's reason for cancellation (required for audit trail)
   */
  async cancelThumbsDown(
    validationId: string,
    reason: string
  ): Promise<{
    success: boolean;
    message: string;
    validation_id: string;
    rating_id: string;
    cancelled_by: string;
  }> {
    const { data } = await this.client.post(
      `/api/analytics/thumbs-down/${validationId}/cancel`,
      { cancellation_reason: reason }
    );
    return data;
  }

  // ============================================================================
  // SHARED FAVORITES
  // ============================================================================

  /**
   * Propose a conversation as a shared favorite
   * @param conversationId - The conversation to propose
   */
  async proposeFavorite(conversationId: string): Promise<SharedFavorite> {
    const { data } = await this.client.post<SharedFavorite>('/api/favorites', {
      conversation_id: conversationId,
    });
    return data;
  }

  /**
   * Get published favorites with optional filtering
   * @param params - Optional filters (page, page_size, universe_id, search)
   */
  async getFavorites(params?: {
    page?: number;
    page_size?: number;
    universe_id?: string;
    search?: string;
  }): Promise<FavoriteListResponse> {
    const { data } = await this.client.get<FavoriteListResponse>('/api/favorites', {
      params: {
        page: params?.page || 1,
        page_size: params?.page_size || 20,
        universe_id: params?.universe_id,
        search: params?.search,
      },
    });
    return data;
  }

  /**
   * Semantic search for similar favorites
   * @param query - Search query
   * @param universeId - Optional universe filter
   * @param limit - Max results (default 10)
   */
  async searchFavorites(
    query: string,
    universeId?: string,
    limit = 10
  ): Promise<FavoriteSearchResult[]> {
    const params: any = { q: query, limit };
    if (universeId) params.universe_id = universeId;

    const { data } = await this.client.get<FavoriteSearchResult[]>('/api/favorites/search', {
      params,
    });
    return data;
  }

  /**
   * Check for similar favorites before RAG (pre-RAG suggestion)
   * @param question - User's question
   * @param universeIds - Optional universe IDs to search within
   */
  async checkFavoriteSuggestions(
    question: string,
    universeIds?: string[]
  ): Promise<FavoriteSuggestionResponse> {
    const params: any = { question };
    if (universeIds && universeIds.length > 0) {
      params.universe_ids = universeIds.join(',');  // Backend expects comma-separated string
    }

    const { data } = await this.client.get<FavoriteSuggestionResponse>('/api/favorites/suggestions', {
      params,
    });
    return data;
  }

  /**
   * Get full details of a favorite
   * @param favoriteId - Favorite UUID
   */
  async getFavoriteDetail(favoriteId: string): Promise<SharedFavorite> {
    const { data } = await this.client.get<SharedFavorite>(`/api/favorites/${favoriteId}`);
    return data;
  }

  /**
   * Copy a favorite to user's conversations
   * @param favoriteId - Favorite to copy
   */
  async copyFavoriteToConversation(favoriteId: string): Promise<FavoriteCopyResponse> {
    const { data } = await this.client.post<FavoriteCopyResponse>(
      `/api/favorites/${favoriteId}/copy`
    );
    return data;
  }

  // ============================================================================
  // SHARED FAVORITES - Admin
  // ============================================================================

  /**
   * Get pending favorites awaiting validation (admin only)
   */
  async getPendingFavorites(params?: {
    page?: number;
    page_size?: number;
  }): Promise<FavoriteListResponse> {
    const { data } = await this.client.get<FavoriteListResponse>('/api/favorites/admin/pending', {
      params: {
        page: params?.page || 1,
        page_size: params?.page_size || 20,
      },
    });
    return data;
  }

  /**
   * Update a favorite (admin only)
   * @param favoriteId - Favorite to update
   * @param updates - Fields to update
   */
  async updateFavorite(favoriteId: string, updates: FavoriteUpdate): Promise<SharedFavorite> {
    const { data } = await this.client.patch<SharedFavorite>(
      `/api/favorites/${favoriteId}`,
      updates
    );
    return data;
  }

  /**
   * Validate (publish/reject) a pending favorite (admin only)
   * @param favoriteId - Favorite to validate
   * @param validation - Validation action and optional edits
   */
  async validateFavorite(
    favoriteId: string,
    validation: FavoriteValidation
  ): Promise<SharedFavorite> {
    const { data } = await this.client.post<SharedFavorite>(
      `/api/favorites/${favoriteId}/validate`,
      validation
    );
    return data;
  }

  /**
   * Delete a favorite (admin only)
   * @param favoriteId - Favorite to delete
   */
  async deleteFavorite(favoriteId: string): Promise<void> {
    await this.client.delete(`/api/favorites/${favoriteId}`);
  }
}

export const api = new APIClient();
export default api;
