// Types pour l'application RAGFab

export type SuggestionMode = 'off' | 'soft' | 'interactive' | null;

export interface User {
  id: string;
  username: string;
  email?: string;
  first_name?: string;
  last_name?: string;
  is_active: boolean;
  is_admin: boolean;
  must_change_password: boolean;
  suggestion_mode?: SuggestionMode;
  created_at: string;
}

export interface UserPreferencesUpdate {
  suggestion_mode: SuggestionMode;
}

export interface UserPreferencesResponse {
  suggestion_mode: SuggestionMode;
  effective_mode: string;
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
  universe_id?: string;
  universe_name?: string;
  universe_color?: string;
}

// Document list with pagination
export interface DocumentListParams {
  page?: number;
  page_size?: number;
  universe_id?: string;
  no_universe?: boolean;
  search?: string;
  sort_by?: 'created_at' | 'title' | 'chunk_count' | 'universe_name';
  order?: 'asc' | 'desc';
}

export interface DocumentListResponse {
  documents: DocumentStats[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface UniverseDocumentCounts {
  counts: Record<string, number>;
  total: number;
  no_universe_count: number;
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
  reranking_enabled?: boolean | null; // null = use global env var, true/false = override
  hybrid_search_enabled: boolean; // Hybrid search per conversation
  hybrid_search_alpha: number; // Alpha parameter (0=keywords, 1=vector)
  // Conversation Management - Universe assignment
  universe_id?: string;
  universe_name?: string;
  universe_slug?: string;
  universe_color?: string;
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

export interface ImageData {
  id: string;
  page_number: number;
  position: { x: number; y: number; width: number; height: number };
  description?: string;
  ocr_text?: string;
  image_base64: string;
}

export interface Source {
  title: string;
  content: string;
  similarity?: number;
  images?: ImageData[];  // Images associated with this source
  is_image_chunk?: boolean;  // Flag to identify synthetic image chunks
  chunk_id?: string;
  document_id?: string;
  document_title?: string;
  document_source?: string;
  chunk_index?: number;
  deep_context?: boolean;  // True for deep context mode responses (full document analysis)
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
  reranking_enabled?: boolean | null;
  universe_ids?: string[];  // Filtrer par univers spécifiques
  search_all_universes?: boolean;  // Chercher dans tous les univers autorisés
  hybrid_search_enabled?: boolean;  // Activer la recherche hybride
  hybrid_search_alpha?: number;  // Alpha pour la recherche hybride (0=keywords, 1=semantic)
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

// User Management Types
export interface UserCreate {
  username: string;
  email?: string;
  password: string;
  is_admin: boolean;
  is_active: boolean;
}

export interface UserUpdate {
  email?: string;
  first_name?: string;
  last_name?: string;
  is_active?: boolean;
  is_admin?: boolean;
}

export interface UserResponse {
  id: string;
  username: string;
  email?: string;
  first_name?: string;
  last_name?: string;
  is_active: boolean;
  is_admin: boolean;
  created_at: string;
  last_login?: string;
}

export interface UserListResponse extends UserResponse {}

export interface PasswordReset {
  new_password: string;
}

export interface UserProfileUpdate {
  first_name?: string;
  last_name?: string;
}

export interface PasswordChange {
  current_password: string;
  new_password: string;
  confirm_password: string;
}

// Universe Types
export interface ProductUniverse {
  id: string;
  name: string;
  slug: string;
  description?: string;
  color: string;
  detection_keywords: string[];
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProductUniverseCreate {
  name: string;
  slug?: string;
  description?: string;
  color?: string;
  detection_keywords?: string[];
  is_active?: boolean;
}

export interface ProductUniverseUpdate {
  name?: string;
  description?: string;
  color?: string;
  detection_keywords?: string[];
  is_active?: boolean;
}

export interface UserUniverseAccess {
  user_id: string;
  universe_id: string;
  universe_name: string;
  universe_color: string;
  is_default: boolean;
  granted_at: string;
  granted_by?: string;
}

export interface UserWithUniverses extends User {
  universes: UserUniverseAccess[];
}

// ============================================================================
// Question Quality Types
// ============================================================================

export type QuestionClassification =
  | 'clear'
  | 'too_vague'
  | 'wrong_vocabulary'
  | 'missing_context'
  | 'out_of_scope';

export type SuggestionType = 'reformulation' | 'clarification' | 'domain_term' | 'vocabulary';

export interface QuestionSuggestion {
  text: string;
  type: SuggestionType;
  reason?: string;
  source_document?: string;  // Document d'où le terme a été extrait
}

export interface QualityAnalysis {
  classification: QuestionClassification;
  confidence: number;
  heuristic_score: number;
  suggestions: QuestionSuggestion[];
  detected_terms: string[];
  suggested_terms: string[];
  reasoning?: string;
  analyzed_by: 'heuristics' | 'llm' | 'heuristics_fallback' | 'disabled' | 'probe_search' | 'llm_with_context';
}

export interface ChatResponseWithQuality extends ChatResponse {
  quality_analysis?: QualityAnalysis;
}

// Mode Interactive - Pre-Analyze
export interface PreAnalyzeRequest {
  message: string;
  conversation_id?: string;
  universe_ids?: string[];
}

export interface PreAnalyzeResponse {
  needs_clarification: boolean;
  classification?: QuestionClassification;
  confidence?: number;
  suggestions: QuestionSuggestion[];
  original_question: string;
  detected_intent?: string;
  extracted_terms: string[];
}

// ============================================================================
// Conversation Management Types
// ============================================================================

export type ConversationTab = 'all' | 'universes' | 'archive' | 'favorites';

export interface ConversationFilters {
  search?: string;
  universeIds?: string[];
  archived?: boolean;
  tab: ConversationTab;
}

export interface ConversationCreate {
  title?: string;
  provider?: 'mistral' | 'chocolatine';
  use_tools?: boolean;
  reranking_enabled?: boolean | null;
  universe_id?: string;
}

export interface ConversationUpdate {
  title?: string;
  is_archived?: boolean;
  reranking_enabled?: boolean | null;
  hybrid_search_enabled?: boolean;
  hybrid_search_alpha?: number;
  universe_id?: string;
}

export interface ConversationPreferences {
  id: string;
  user_id: string;
  retention_days: number | null;
  retention_target: 'archived' | 'all';
  auto_archive_days: number | null;
  default_view: ConversationTab;
  conversations_per_page: number;
  created_at: string;
  updated_at: string;
}

export interface ConversationPreferencesUpdate {
  retention_days?: number | null;
  retention_target?: 'archived' | 'all';
  auto_archive_days?: number | null;
  default_view?: ConversationTab;
  conversations_per_page?: number;
}

export type WarningLevel = 'none' | 'approaching' | 'exceeded';

export interface ConversationStats {
  active_count: number;
  archived_count: number;
  total_count: number;
  warning_level: WarningLevel;
  oldest_active_date: string | null;
}

export type MatchType = 'title' | 'message' | 'both';

export interface ConversationSearchResult {
  conversation_id: string;
  title: string;
  universe_id?: string;
  universe_name?: string;
  universe_color?: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  archived: boolean;
  match_type: MatchType;
  rank: number;
}

export interface BulkArchiveRequest {
  conversation_ids: string[];
}

export interface BulkDeleteRequest {
  conversation_ids: string[];
  confirm: boolean;
}

export interface BulkActionResponse {
  success_count: number;
  failed_count: number;
  errors: string[];
}

// Time grouping for conversation list
export type TimeGroup = 'today' | 'yesterday' | 'last7days' | 'last30days' | 'older';

export type GroupedConversations = Record<TimeGroup, ConversationWithStats[]>;

// ============================================================================
// Shared Favorites Types
// ============================================================================

export type FavoriteStatus = 'pending' | 'published' | 'rejected';

export interface SharedFavorite {
  id: string;
  title: string;
  question: string;
  response: string;
  sources?: Source[];
  status: FavoriteStatus;
  proposed_by_username?: string;
  validated_by_username?: string;
  universe_id?: string;
  universe_name?: string;
  universe_slug?: string;
  universe_color?: string;
  view_count: number;
  copy_count: number;
  created_at: string;
  validated_at?: string;
  last_edited_at?: string;
  rejection_reason?: string;
  admin_notes?: string;
}

export interface FavoriteSearchResult extends Omit<SharedFavorite, 'status' | 'proposed_by_username' | 'validated_by_username' | 'rejection_reason' | 'admin_notes' | 'validated_at' | 'last_edited_at'> {
  similarity: number;
}

export interface FavoriteListResponse {
  favorites: SharedFavorite[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface FavoriteSuggestionResponse {
  has_suggestions: boolean;
  suggestions: FavoriteSearchResult[];
  message?: string;
}

export interface FavoriteCopyResponse {
  conversation_id: string;
  message: string;
}

export interface FavoriteCreate {
  conversation_id: string;
}

export interface FavoriteUpdate {
  published_title?: string;
  published_question?: string;
  published_response?: string;
  admin_notes?: string;
}

export interface FavoriteValidation {
  action: 'publish' | 'reject';
  published_title?: string;
  published_question?: string;
  published_response?: string;
  rejection_reason?: string;
}

// ============================================================================
// Deep Context Mode Types
// ============================================================================

export interface DeepContextRequest {
  document_ids: string[];
  max_tokens?: number;
}

export interface FollowUpSuggestion {
  text: string;
  relevance?: 'high' | 'medium' | 'low';
}

export interface DocumentTokenInfo {
  id: string;
  title: string;
  token_count: number;
  truncated: boolean;
}

export interface DeepContextResponse {
  message: Message;
  documents_used: DocumentTokenInfo[];
  total_tokens_used: number;
  follow_up_suggestions: FollowUpSuggestion[];
}
