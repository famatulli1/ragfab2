"""
Modèles Pydantic pour l'API
"""
from pydantic import BaseModel, Field
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


class ConversationUpdate(BaseModel):
    title: Optional[str] = None
    is_archived: Optional[bool] = None
    reranking_enabled: Optional[bool] = None  # Update reranking preference


class Conversation(BaseModel):
    id: UUID
    title: str
    provider: str
    use_tools: bool
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    is_archived: bool = Field(default=False, alias="archived")  # Alias pour la colonne DB "archived"
    reranking_enabled: Optional[bool] = None  # None=use env var, True/False=explicit

    class Config:
        populate_by_name = True  # Accepte à la fois "archived" et "is_archived"


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
