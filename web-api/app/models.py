"""
Modèles Pydantic pour l'API
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


# ============================================================================
# Auth Models
# ============================================================================

class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class User(BaseModel):
    id: UUID
    username: str
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: bool = True
    is_admin: bool = True
    must_change_password: bool = False
    suggestion_mode: Optional[str] = None  # off, soft, interactive, or None (use global)
    created_at: datetime


# ============================================================================
# Document Models
# ============================================================================

class DocumentBase(BaseModel):
    title: str
    source: str


class DocumentCreate(DocumentBase):
    content: str
    metadata: Optional[Dict[str, Any]] = None


class Document(DocumentBase):
    id: UUID
    created_at: datetime
    chunk_count: Optional[int] = 0


class DocumentStats(Document):
    total_content_length: Optional[int] = 0
    avg_chunk_tokens: Optional[float] = 0
    universe_id: Optional[UUID] = None
    universe_name: Optional[str] = None
    universe_slug: Optional[str] = None
    universe_color: Optional[str] = None


class DocumentListResponse(BaseModel):
    """Paginated document list response"""
    documents: List[DocumentStats]
    total: int
    page: int
    page_size: int
    total_pages: int


class ChunkResponse(BaseModel):
    id: UUID
    content: str
    chunk_index: int
    token_count: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


# ============================================================================
# Image Models
# ============================================================================

class ImageMetadata(BaseModel):
    """Metadata for an extracted document image."""
    id: UUID
    document_id: UUID
    chunk_id: Optional[UUID] = None
    page_number: int
    position: Dict[str, float]  # {x, y, width, height}
    image_path: str
    image_base64: Optional[str] = None  # For inline display
    image_format: str
    image_size_bytes: int
    description: Optional[str] = None
    ocr_text: Optional[str] = None
    confidence_score: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime


class ImageResponse(BaseModel):
    """Simplified image response for API."""
    id: UUID
    page_number: int
    position: Dict[str, float]
    description: Optional[str] = None
    ocr_text: Optional[str] = None
    image_base64: str  # Always included for inline display


class ChunkWithImages(ChunkResponse):
    """Chunk response with associated images."""
    images: List[ImageResponse] = []


# ============================================================================
# Ingestion Job Models
# ============================================================================

class IngestionJobCreate(BaseModel):
    filename: str
    file_size: int


class IngestionJob(BaseModel):
    id: UUID
    filename: str
    file_size: Optional[int] = None
    status: str  # pending, processing, completed, failed
    progress: int = 0
    document_id: Optional[UUID] = None
    chunks_created: int = 0
    error_message: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# ============================================================================
# Conversation Models
# ============================================================================

class ConversationCreate(BaseModel):
    title: Optional[str] = "Nouvelle conversation"
    provider: str = "mistral"  # mistral, chocolatine
    use_tools: bool = True
    reranking_enabled: Optional[bool] = None  # None=global, True=on, False=off
    universe_id: Optional[UUID] = None  # Univers auquel appartient la conversation


class ConversationUpdate(BaseModel):
    title: Optional[str] = None
    is_archived: Optional[bool] = None
    reranking_enabled: Optional[bool] = None  # Update reranking preference
    hybrid_search_enabled: Optional[bool] = None  # Update hybrid search per conversation
    hybrid_search_alpha: Optional[float] = None  # Update alpha parameter per conversation
    universe_id: Optional[UUID] = None  # Changer l'univers de la conversation


class Conversation(BaseModel):
    model_config = ConfigDict(populate_by_name=True)  # Pydantic v2: accepte à la fois "archived" et "is_archived"

    id: UUID
    title: str
    provider: str
    use_tools: bool
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    is_archived: bool = Field(default=False, validation_alias="archived")  # validation_alias pour input DB, serialise comme is_archived
    reranking_enabled: Optional[bool] = None  # None=use env var, True/False=explicit
    hybrid_search_enabled: bool = False  # Hybrid search setting per conversation
    hybrid_search_alpha: float = 0.5  # Alpha parameter (0=keywords, 1=vector)
    universe_id: Optional[UUID] = None  # Univers de la conversation
    universe_name: Optional[str] = None  # Nom de l'univers (depuis la vue)
    universe_slug: Optional[str] = None  # Slug de l'univers
    universe_color: Optional[str] = None  # Couleur de l'univers


class ConversationWithStats(Conversation):
    thumbs_up_count: int = 0
    thumbs_down_count: int = 0


# ============================================================================
# Message Models
# ============================================================================

class MessageCreate(BaseModel):
    conversation_id: UUID
    content: str
    role: str = "user"  # user ou assistant


class MessageResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    role: str
    content: str
    sources: Optional[List[Dict[str, Any]]] = None
    provider: Optional[str] = None
    model_name: Optional[str] = None
    token_usage: Optional[Dict[str, Any]] = None
    created_at: datetime
    is_regenerated: bool = False
    rating: Optional[int] = None  # -1, None, 1


class ChatRequest(BaseModel):
    conversation_id: UUID
    message: str
    provider: Optional[str] = None  # Override conversation provider
    use_tools: Optional[bool] = None  # Override conversation use_tools
    reranking_enabled: Optional[bool] = None  # Override conversation reranking setting
    universe_ids: Optional[List[UUID]] = None  # Filtrer par univers spécifiques
    search_all_universes: bool = False  # Chercher dans tous les univers autorisés
    hybrid_search_enabled: Optional[bool] = None  # Override hybrid search setting
    hybrid_search_alpha: Optional[float] = None  # Override hybrid search alpha (0=keywords, 1=semantic)


class ChatResponse(BaseModel):
    user_message: MessageResponse
    assistant_message: MessageResponse
    conversation: Conversation


# ============================================================================
# Rating Models
# ============================================================================

class RatingCreate(BaseModel):
    rating: int = Field(..., ge=-1, le=1)  # -1 = thumbs down, 1 = thumbs up
    feedback: Optional[str] = None


class Rating(BaseModel):
    id: UUID
    message_id: UUID
    user_id: UUID  # User who submitted the rating (direct traceability)
    rating: int
    feedback: Optional[str] = None
    created_at: datetime


# ============================================================================
# Export Models
# ============================================================================

class ExportFormat(str):
    MARKDOWN = "markdown"
    PDF = "pdf"


class ExportRequest(BaseModel):
    format: str = "markdown"  # markdown or pdf


# ============================================================================
# User Management Models (Admin)
# ============================================================================

class UserCreate(BaseModel):
    """Modèle pour créer un nouvel utilisateur"""
    username: str = Field(..., min_length=3, max_length=50, description="Nom d'utilisateur unique")
    email: Optional[str] = Field(None, max_length=255, description="Adresse email")
    first_name: str = Field(..., min_length=1, max_length=100, description="Prénom")
    last_name: str = Field(..., min_length=1, max_length=100, description="Nom")
    password: str = Field(..., min_length=8, description="Mot de passe (minimum 8 caractères)")
    is_admin: bool = Field(default=False, description="Rôle administrateur")
    is_active: bool = Field(default=True, description="Compte actif")


class UserUpdate(BaseModel):
    """Modèle pour mettre à jour un utilisateur (admin)"""
    email: Optional[str] = Field(None, max_length=255, description="Adresse email")
    first_name: Optional[str] = Field(None, max_length=100, description="Prénom")
    last_name: Optional[str] = Field(None, max_length=100, description="Nom")
    is_active: Optional[bool] = Field(None, description="Statut actif/inactif")
    is_admin: Optional[bool] = Field(None, description="Rôle administrateur")


class UserResponse(BaseModel):
    """Modèle de réponse pour un utilisateur"""
    id: UUID
    username: str
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: bool
    is_admin: bool
    suggestion_mode: Optional[str] = None
    created_at: datetime
    last_login: Optional[datetime] = None


class UserListResponse(BaseModel):
    """Modèle de réponse pour la liste des utilisateurs"""
    id: UUID
    username: str
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: bool
    is_admin: bool
    suggestion_mode: Optional[str] = None
    created_at: datetime
    last_login: Optional[datetime] = None


class PasswordReset(BaseModel):
    """Modèle pour réinitialiser le mot de passe (admin)"""
    new_password: str = Field(..., min_length=8, description="Nouveau mot de passe (minimum 8 caractères)")


class UserProfileUpdate(BaseModel):
    """Modèle pour mettre à jour son propre profil (utilisateur)"""
    first_name: Optional[str] = Field(None, min_length=1, max_length=100, description="Prénom")
    last_name: Optional[str] = Field(None, min_length=1, max_length=100, description="Nom")


class PasswordChange(BaseModel):
    """Modèle pour changer son propre mot de passe"""
    current_password: str = Field(..., description="Mot de passe actuel")
    new_password: str = Field(..., min_length=8, description="Nouveau mot de passe (minimum 8 caractères)")
    confirm_password: str = Field(..., description="Confirmation du nouveau mot de passe")


class UserPreferencesUpdate(BaseModel):
    """Modèle pour mettre à jour les préférences utilisateur"""
    suggestion_mode: Optional[str] = Field(
        None,
        description="Mode de suggestions: off, soft, interactive, ou null pour utiliser le paramètre global"
    )


class UserPreferencesResponse(BaseModel):
    """Modèle de réponse pour les préférences utilisateur"""
    suggestion_mode: Optional[str] = None
    effective_mode: str  # Le mode effectif (user pref ou global)


# ============================================================================
# Product Universe Models
# ============================================================================

class ProductUniverseBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(..., min_length=1, max_length=50, pattern=r'^[a-z0-9-]+$')
    description: Optional[str] = None
    detection_keywords: Optional[List[str]] = None
    color: str = Field(default='#6366f1', pattern=r'^#[0-9a-fA-F]{6}$')
    is_active: bool = True


class ProductUniverseCreate(ProductUniverseBase):
    pass


class ProductUniverseUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    detection_keywords: Optional[List[str]] = None
    color: Optional[str] = Field(None, pattern=r'^#[0-9a-fA-F]{6}$')
    is_active: Optional[bool] = None


class ProductUniverse(ProductUniverseBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProductUniverseList(BaseModel):
    universes: List[ProductUniverse]
    total: int


# ============================================================================
# User Universe Access Models
# ============================================================================

class UserUniverseAccessCreate(BaseModel):
    """Création d'un accès univers pour un utilisateur"""
    universe_id: UUID
    is_default: bool = False


class UserUniverseAccessSimple(BaseModel):
    """Accès univers simplifié (pour inclusion dans User)"""
    universe_id: UUID
    universe_name: str
    universe_slug: str
    universe_color: str
    is_default: bool = False

    class Config:
        from_attributes = True


class UserUniverseAccess(BaseModel):
    """Accès univers complet"""
    id: UUID
    user_id: UUID
    universe_id: UUID
    universe_name: str
    universe_slug: str
    universe_color: str
    is_default: bool
    granted_at: datetime
    granted_by: Optional[UUID] = None
    granted_by_username: Optional[str] = None

    class Config:
        from_attributes = True


class UserUniverseAccessList(BaseModel):
    """Liste des accès univers d'un utilisateur"""
    user_id: UUID
    username: str
    accesses: List[UserUniverseAccess]
    total: int


class SetDefaultUniverseRequest(BaseModel):
    """Requête pour définir l'univers par défaut"""
    universe_id: UUID


class UserWithUniverses(User):
    """User avec ses univers autorisés"""
    allowed_universes: List[UserUniverseAccessSimple] = []
    default_universe_id: Optional[UUID] = None


# ============================================================================
# Question Quality Models
# ============================================================================

class QuestionSuggestion(BaseModel):
    """Une suggestion de reformulation de question."""
    text: str = Field(..., description="Texte de la question reformulée")
    type: str = Field(..., description="Type: reformulation, clarification, domain_term")
    reason: Optional[str] = Field(None, description="Raison de la suggestion")


class QualityAnalysis(BaseModel):
    """Résultat de l'analyse de qualité d'une question."""
    classification: str = Field(..., description="Classification: clear, too_vague, wrong_vocabulary, missing_context, out_of_scope")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Score de confiance (0.0-1.0)")
    heuristic_score: float = Field(..., ge=0.0, le=1.0, description="Score des heuristiques")
    suggestions: List[QuestionSuggestion] = Field(default_factory=list, description="Suggestions de reformulation")
    detected_terms: List[str] = Field(default_factory=list, description="Termes métier détectés")
    suggested_terms: List[str] = Field(default_factory=list, description="Termes métier suggérés")
    reasoning: Optional[str] = Field(None, description="Explication courte")
    analyzed_by: str = Field(default="heuristics", description="Méthode d'analyse: heuristics, llm, heuristics_fallback")


class ChatResponseWithQuality(ChatResponse):
    """ChatResponse étendu avec analyse de qualité (pour phase soft/interactive)."""
    quality_analysis: Optional[QualityAnalysis] = Field(None, description="Analyse de qualité si question problématique")


# ============================================================================
# Mode Interactive - Pre-Analyze
# ============================================================================

class PreAnalyzeRequest(BaseModel):
    """Requête d'analyse préalable d'une question (mode interactive)."""
    message: str = Field(..., min_length=1, description="Question à analyser avant envoi")
    conversation_id: Optional[UUID] = Field(None, description="ID de la conversation pour contexte")
    universe_ids: Optional[List[UUID]] = Field(None, description="Univers à utiliser pour le probe search")


class PreAnalyzeResponse(BaseModel):
    """Réponse d'analyse préalable pour le mode interactive."""
    needs_clarification: bool = Field(..., description="True si la question nécessite reformulation")
    classification: Optional[str] = Field(None, description="Classification: clear, too_vague, etc.")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Score de confiance")
    suggestions: List[QuestionSuggestion] = Field(default_factory=list, description="Suggestions de reformulation")
    original_question: str = Field(..., description="Question originale")
    detected_intent: Optional[str] = Field(None, description="Intention détectée (howto, explain, etc.)")
    extracted_terms: List[str] = Field(default_factory=list, description="Termes extraits des documents")


# ============================================================================
# Conversation Management Models
# ============================================================================

class ConversationPreferencesUpdate(BaseModel):
    """Préférences de gestion des conversations."""
    retention_days: Optional[int] = Field(None, ge=1, le=365, description="Jours avant suppression (null=jamais)")
    retention_target: Optional[str] = Field(None, description="'archived' ou 'all'")
    auto_archive_days: Optional[int] = Field(None, ge=1, le=365, description="Jours d'inactivité avant archivage")
    default_view: Optional[str] = Field(None, description="'all', 'universes', ou 'archive'")
    conversations_per_page: Optional[int] = Field(None, ge=10, le=100, description="Conversations par page")


class ConversationPreferencesResponse(BaseModel):
    """Réponse des préférences de conversation."""
    user_id: UUID
    retention_days: Optional[int] = None
    retention_target: str = "archived"
    auto_archive_days: Optional[int] = None
    default_view: str = "all"
    conversations_per_page: int = 20
    created_at: datetime
    updated_at: datetime


class ConversationStats(BaseModel):
    """Statistiques des conversations utilisateur."""
    active_count: int = Field(..., description="Nombre de conversations actives")
    archived_count: int = Field(..., description="Nombre de conversations archivées")
    total_count: int = Field(..., description="Total des conversations")
    warning_level: str = Field(..., description="'none', 'approaching' (>=40), ou 'exceeded' (>=50)")
    oldest_active_date: Optional[datetime] = Field(None, description="Date de la plus ancienne conversation active")


class ConversationSearchResult(BaseModel):
    """Résultat de recherche de conversation."""
    conversation_id: UUID
    title: str
    universe_id: Optional[UUID] = None
    universe_name: Optional[str] = None
    universe_color: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    message_count: int
    archived: bool
    match_type: str = Field(..., description="'title', 'message', ou 'both'")
    rank: float = Field(..., description="Score de pertinence")


class ConversationSearchResponse(BaseModel):
    """Réponse de recherche de conversations."""
    results: List[ConversationSearchResult]
    total: int
    query: str


class BulkArchiveRequest(BaseModel):
    """Requête d'archivage en masse."""
    conversation_ids: List[UUID] = Field(..., min_length=1, description="IDs des conversations à archiver")


class BulkDeleteRequest(BaseModel):
    """Requête de suppression en masse."""
    conversation_ids: List[UUID] = Field(..., min_length=1, description="IDs des conversations à supprimer")
    confirm: bool = Field(False, description="Confirmation de suppression définitive")


class BulkActionResponse(BaseModel):
    """Réponse d'action en masse."""
    success_count: int
    failed_count: int = 0
    errors: List[str] = Field(default_factory=list)


# ============================================================================
# Shared Favorites Models
# ============================================================================

from enum import Enum
from typing import Literal


class FavoriteStatus(str, Enum):
    """Status d'un favori partagé."""
    PENDING = "pending"
    PUBLISHED = "published"
    REJECTED = "rejected"


class FavoriteCreate(BaseModel):
    """Requête pour proposer une conversation comme favori."""
    conversation_id: UUID = Field(..., description="ID de la conversation source")


class FavoriteUpdate(BaseModel):
    """Mise à jour d'un favori (admin uniquement)."""
    published_title: Optional[str] = Field(None, max_length=500, description="Titre édité")
    published_question: Optional[str] = Field(None, description="Question éditée")
    published_response: Optional[str] = Field(None, description="Réponse éditée")
    admin_notes: Optional[str] = Field(None, description="Notes admin (privées)")


class FavoriteValidation(BaseModel):
    """Requête de validation d'un favori (publish/reject)."""
    action: Literal["publish", "reject"] = Field(..., description="Action: publish ou reject")
    published_title: Optional[str] = Field(None, max_length=500, description="Titre à publier")
    published_question: Optional[str] = Field(None, description="Question éditée avant publication")
    published_response: Optional[str] = Field(None, description="Réponse éditée avant publication")
    rejection_reason: Optional[str] = Field(None, description="Raison du rejet (si action=reject)")


class FavoriteResponse(BaseModel):
    """Réponse détaillée d'un favori."""
    id: UUID
    title: str = Field(..., description="Titre affiché (published_title ou extrait de question)")
    question: str = Field(..., description="Question affichée (published ou original)")
    response: str = Field(..., description="Réponse affichée (published ou original)")
    sources: Optional[List[Dict[str, Any]]] = Field(None, description="Sources RAG originales")
    status: str = Field(..., description="pending, published, rejected")
    proposed_by_username: Optional[str] = None
    validated_by_username: Optional[str] = None
    universe_id: Optional[UUID] = None
    universe_name: Optional[str] = None
    universe_slug: Optional[str] = None
    universe_color: Optional[str] = None
    view_count: int = 0
    copy_count: int = 0
    created_at: datetime
    validated_at: Optional[datetime] = None
    last_edited_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    admin_notes: Optional[str] = None  # Visible uniquement pour admin


class FavoriteSearchResult(BaseModel):
    """Résultat de recherche sémantique dans les favoris."""
    id: UUID
    title: str
    question: str
    response: str
    sources: Optional[List[Dict[str, Any]]] = None
    similarity: float = Field(..., ge=0.0, le=1.0, description="Score de similarité cosinus")
    universe_id: Optional[UUID] = None
    universe_name: Optional[str] = None
    universe_color: Optional[str] = None
    view_count: int = 0
    copy_count: int = 0


class FavoriteListResponse(BaseModel):
    """Liste paginée des favoris."""
    favorites: List[FavoriteResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class FavoriteSuggestionResponse(BaseModel):
    """Réponse de suggestion pre-RAG (quand similarité > 0.85)."""
    has_suggestions: bool = Field(..., description="True si des favoris similaires existent")
    suggestions: List[FavoriteSearchResult] = Field(default_factory=list)
    message: Optional[str] = Field(None, description="Message à afficher à l'utilisateur")


class FavoriteCopyResponse(BaseModel):
    """Réponse après copie d'un favori vers une nouvelle conversation."""
    conversation_id: UUID = Field(..., description="ID de la nouvelle conversation créée")
    message: str = Field(default="Favori copié avec succès")
