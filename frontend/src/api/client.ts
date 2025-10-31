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
} from '../types';

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
    chunkerType: 'hybrid' | 'parent_child' = 'hybrid'
  ): Promise<{ job_id: string; filename: string; status: string; message: string }> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('ocr_engine', ocrEngine);
    formData.append('vlm_engine', vlmEngine);
    formData.append('chunker_type', chunkerType);

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
}

export const api = new APIClient();
export default api;
