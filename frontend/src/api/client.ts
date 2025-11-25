import axios, { AxiosInstance, AxiosError } from 'axios';
import type {
  LoginRequest,
  TokenResponse,
  User,
  DocumentStats,
  Chunk,
  IngestionJob,
  Conversation,
  ConversationWithStats,
  Message,
  ChatRequest,
  ChatResponse,
  RatingCreate,
  UserCreate,
  UserUpdate,
  UserResponse,
  UserListResponse,
  ProductUniverse,
  ProductUniverseCreate,
  ProductUniverseUpdate,
  UserUniverseAccess,
  UserWithUniverses,
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

  // ============================================================================
  // Documents
  // ============================================================================

  async getDocuments(limit = 100, offset = 0): Promise<DocumentStats[]> {
    const { data } = await this.client.get<DocumentStats[]>('/api/documents', {
      params: { limit, offset },
    });
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

  async getConversations(limit = 50, offset = 0, includeArchived = false): Promise<ConversationWithStats[]> {
    const { data } = await this.client.get<ConversationWithStats[]>('/api/conversations', {
      params: { limit, offset, include_archived: includeArchived },
    });
    return data;
  }

  async createConversation(title?: string, provider = 'mistral', useTools = true): Promise<Conversation> {
    const { data } = await this.client.post<Conversation>('/api/conversations', {
      title: title || 'Nouvelle conversation',
      provider,
      use_tools: useTools,
    });
    return data;
  }

  async getConversation(id: string): Promise<Conversation> {
    const { data } = await this.client.get<Conversation>(`/api/conversations/${id}`);
    return data;
  }

  async updateConversation(id: string, updates: {
    title?: string;
    is_archived?: boolean;
    reranking_enabled?: boolean | null;
    hybrid_search_enabled?: boolean;
    hybrid_search_alpha?: number;
  }): Promise<Conversation> {
    const { data } = await this.client.patch<Conversation>(`/api/conversations/${id}`, updates);
    return data;
  }

  async deleteConversation(id: string): Promise<void> {
    await this.client.delete(`/api/conversations/${id}`);
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

  async sendMessage(request: ChatRequest): Promise<ChatResponse> {
    const { data } = await this.client.post<ChatResponse>('/api/chat', request);
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
}

export const api = new APIClient();
export default api;
