/**
 * Types TypeScript pour le système de validation des thumbs down
 */

export type ThumbsDownClassification =
  | 'bad_question'           // Question mal formulée
  | 'bad_answer'             // Réponse incorrecte
  | 'missing_sources'        // Sources manquantes
  | 'unrealistic_expectations'; // Attentes hors scope

export type AdminAction =
  | 'contact_user'           // Accompagner utilisateur
  | 'mark_for_reingestion'  // Marquer document pour réingestion
  | 'ignore'                // Thumbs down illégitime
  | 'pending';              // Pas d'action

export interface ThumbsDownValidation {
  id: string;
  message_id: string;
  rating_id: string;
  user_id: string;

  // Données contextuelles
  user_question: string;
  assistant_response: string;
  sources_used: any[] | null;
  user_feedback: string | null;

  // Classification IA
  ai_classification: ThumbsDownClassification;
  ai_confidence: number;
  ai_reasoning: string;
  suggested_reformulation: string | null;
  missing_info_details: string | null;
  needs_admin_review: boolean;

  // Validation admin
  admin_override: ThumbsDownClassification | null;
  admin_notes: string | null;
  admin_action: AdminAction;
  validated_by: string | null;
  validated_at: string | null;

  // Cancellation info (soft delete)
  is_cancelled?: boolean;
  cancelled_by?: string;
  cancelled_by_username?: string;
  cancelled_at?: string;
  cancellation_reason?: string;

  // Métadonnées
  created_at: string;

  // Données utilisateur (jointes)
  username: string;
  user_email: string;
  first_name: string | null;
  last_name: string | null;
  validated_by_username: string | null;

  // Classification finale (computed)
  final_classification?: ThumbsDownClassification;
}

export interface ThumbsDownStats {
  summary: {
    total_thumbs_down: number;
    pending_review: number;
    bad_questions: number;
    bad_answers: number;
    missing_sources: number;
    unrealistic_expectations: number;
    avg_confidence: number;
    admin_overrides: number;
    users_to_contact: number;
    documents_to_reingest: number;
  };
  temporal_distribution: Array<{
    date: string;
    count: number;
    avg_confidence: number;
  }>;
}

export interface UserToContact {
  user_id: string;
  username: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  bad_questions_count: number;
  recent_questions: string[];
  last_bad_question_date: string;
  validation_ids: string[];
}

export interface ReingestionCandidate {
  document_id: string;
  document_title: string;
  source: string;
  occurrences_count: number;
  last_occurrence: string;
  chunk_ids: string[];
  user_questions: string[];
}

export interface ValidationUpdate {
  admin_override?: ThumbsDownClassification;
  admin_notes?: string;
  admin_action: AdminAction;
}

export interface PendingValidationsResponse {
  pending_validations: ThumbsDownValidation[];
  count: number;
}

export interface AllValidationsResponse {
  validations: ThumbsDownValidation[];
  total_count: number;
  page_size: number;
  offset: number;
}

export interface UsersToContactResponse {
  users_to_contact: UserToContact[];
  total_users: number;
}

export interface ReingestionCandidatesResponse {
  documents: ReingestionCandidate[];
  total_documents: number;
}

// Filtres pour requête ALL
export interface ThumbsDownFilters {
  classification?: ThumbsDownClassification;
  needs_review?: boolean;
  admin_action?: AdminAction;
  validated?: boolean;
  limit?: number;
  offset?: number;
}
