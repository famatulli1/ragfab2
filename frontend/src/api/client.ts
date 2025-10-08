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

  async uploadDocument(file: File): Promise<{ job_id: string; filename: string; status: string; message: string }> {
    const formData = new FormData();
    formData.append('file', file);

    const { data } = await this.client.post('/api/documents/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return data;
  }

  async getIngestionJob(jobId: string): Promise<IngestionJob> {
    const { data } = await this.client.get<IngestionJob>(`/api/documents/jobs/${jobId}`);
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

  async updateConversation(id: string, updates: { title?: string; is_archived?: boolean; reranking_enabled?: boolean | null }): Promise<Conversation> {
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
}

export const api = new APIClient();
export default api;
