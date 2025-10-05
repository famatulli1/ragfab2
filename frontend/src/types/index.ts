// Types pour l'application RAGFab

export interface User {
  id: string;
  username: string;
  email?: string;
  is_active: boolean;
  is_admin: boolean;
  created_at: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface Document {
  id: string;
  title: string;
  source: string;
  created_at: string;
  chunk_count?: number;
}

export interface DocumentStats extends Document {
  total_content_length?: number;
  avg_chunk_tokens?: number;
}

export interface Chunk {
  id: string;
  content: string;
  chunk_index: number;
  token_count?: number;
  metadata?: Record<string, any>;
}

export interface IngestionJob {
  id: string;
  filename: string;
  file_size?: number;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress: number;
  document_id?: string;
  chunks_created: number;
  error_message?: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
}

export interface Conversation {
  id: string;
  title: string;
  provider: 'mistral' | 'chocolatine';
  use_tools: boolean;
  created_at: string;
  updated_at: string;
  message_count: number;
  is_archived: boolean;
}

export interface ConversationWithStats extends Conversation {
  thumbs_up_count: number;
  thumbs_down_count: number;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
  provider?: string;
  model_name?: string;
  token_usage?: TokenUsage;
  created_at: string;
  is_regenerated: boolean;
  rating?: -1 | 1 | null;
}

export interface Source {
  title: string;
  content: string;
  similarity?: number;
}

export interface TokenUsage {
  prompt: number;
  completion: number;
  total: number;
}

export interface ChatRequest {
  conversation_id: string;
  message: string;
  provider?: 'mistral' | 'chocolatine';
  use_tools?: boolean;
}

export interface ChatResponse {
  user_message: Message;
  assistant_message: Message;
  conversation: Conversation;
}

export interface RatingCreate {
  rating: -1 | 1;
  feedback?: string;
}

export interface ExportRequest {
  format: 'markdown' | 'pdf';
}

export type Theme = 'light' | 'dark';

export type Provider = 'mistral' | 'chocolatine';

export interface ProviderConfig {
  provider: Provider;
  use_tools: boolean;
  label: string;
  description: string;
}
