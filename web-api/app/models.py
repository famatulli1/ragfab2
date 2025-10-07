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
    is_active: bool = True
    is_admin: bool = True
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


class ConversationUpdate(BaseModel):
    title: Optional[str] = None
    is_archived: Optional[bool] = None


class Conversation(BaseModel):
    id: UUID
    title: str
    provider: str
    use_tools: bool
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    archived: bool = False


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
