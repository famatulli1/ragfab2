"""
Routes API pour les templates de réponse.
Permet aux agents support de reformater les réponses RAG selon des templates prédéfinis.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID
import httpx
from datetime import datetime

from app import database
from app.routes.auth import get_current_user

router = APIRouter(prefix="/api/templates", tags=["templates"])

# ============================================================================
# Pydantic Models
# ============================================================================

class ResponseTemplate(BaseModel):
    """Modèle pour un template de réponse."""
    id: UUID
    name: str
    display_name: str
    icon: str
    description: Optional[str] = None
    is_active: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime

class ResponseTemplateAdmin(ResponseTemplate):
    """Modèle admin avec prompt_instructions visible."""
    prompt_instructions: str

class ApplyTemplateRequest(BaseModel):
    """Requête pour appliquer un template."""
    original_response: str = Field(..., description="Réponse originale à reformater")
    conversation_id: Optional[UUID] = Field(None, description="ID de la conversation (optionnel)")
    message_id: Optional[UUID] = Field(None, description="ID du message (optionnel)")

class ApplyTemplateResponse(BaseModel):
    """Réponse après application d'un template."""
    formatted_response: str
    template_used: str
    processing_time_ms: int

# ============================================================================
# Routes publiques (pour les agents)
# ============================================================================

@router.get("", response_model=List[ResponseTemplate])
async def list_active_templates(current_user: dict = Depends(get_current_user)):
    """
    Liste les templates actifs disponibles pour l'utilisateur.
    """
    async with database.db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, name, display_name, icon, description, is_active, sort_order, created_at, updated_at
            FROM response_templates
            WHERE is_active = true
            ORDER BY sort_order ASC
        """)

    templates = [ResponseTemplate(**dict(row)) for row in rows]
    return templates

class FormattedResponseData(BaseModel):
    """Modèle pour une réponse formatée sauvegardée."""
    formatted_content: str
    template_id: UUID
    template_name: str
    created_at: datetime

@router.get("/formatted/{message_id}", response_model=Optional[FormattedResponseData])
async def get_formatted_response(
    message_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """
    Récupère la réponse formatée sauvegardée pour un message donné.
    Retourne None si aucune réponse formatée n'existe pour ce message.
    """
    async with database.db_pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT
                fr.formatted_content,
                fr.template_id,
                rt.name as template_name,
                fr.created_at
            FROM formatted_responses fr
            JOIN response_templates rt ON fr.template_id = rt.id
            WHERE fr.message_id = $1
        """, message_id)

    if not row:
        return None

    return FormattedResponseData(**dict(row))

@router.post("/{template_id}/apply", response_model=ApplyTemplateResponse)
async def apply_template(
    template_id: UUID,
    request: ApplyTemplateRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Applique un template à une réponse pour la reformater.

    Process:
    1. Récupère le template depuis la BD
    2. Construit le prompt avec les instructions du template
    3. Appelle le LLM pour reformater la réponse
    4. Retourne la réponse formatée
    """
    import time
    start_time = time.time()

    # Récupérer le template
    async with database.db_pool.acquire() as conn:
        template_row = await conn.fetchrow("""
            SELECT name, display_name, prompt_instructions
            FROM response_templates
            WHERE id = $1 AND is_active = true
        """, template_id)

    if not template_row:
        raise HTTPException(status_code=404, detail="Template not found or inactive")

    # Construire le prompt final en injectant la réponse originale ET les données utilisateur
    prompt_instructions = template_row['prompt_instructions']
    final_prompt = prompt_instructions.replace('{original_response}', request.original_response)

    # Injecter les données de l'utilisateur pour la signature
    user_first_name = current_user.get('first_name', 'Agent')
    user_last_name = current_user.get('last_name', 'Support')
    final_prompt = final_prompt.replace('{user_first_name}', user_first_name)
    final_prompt = final_prompt.replace('{user_last_name}', user_last_name)

    # Appeler le LLM pour reformater
    from app.utils.generic_llm_provider import get_generic_llm_model

    model = get_generic_llm_model()
    api_url = model.api_url.rstrip('/')

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{api_url}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {model.api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": model.model_name,
                "messages": [
                    {"role": "system", "content": "Tu es un assistant qui formate des réponses professionnelles."},
                    {"role": "user", "content": final_prompt}
                ],
                "temperature": 0.3,  # Plus déterministe pour formatage
                "max_tokens": 2000
            }
        )

    if response.status_code != 200:
        raise HTTPException(status_code=500, detail=f"LLM API error: {response.text}")

    result = response.json()
    formatted_response = result['choices'][0]['message']['content'].strip()

    processing_time_ms = int((time.time() - start_time) * 1000)

    # Sauvegarder la réponse formatée en base de données (UPSERT)
    if request.message_id:
        async with database.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO formatted_responses (message_id, template_id, formatted_content)
                VALUES ($1, $2, $3)
                ON CONFLICT (message_id)
                DO UPDATE SET
                    template_id = EXCLUDED.template_id,
                    formatted_content = EXCLUDED.formatted_content,
                    updated_at = CURRENT_TIMESTAMP
            """, request.message_id, template_id, formatted_response)

    return ApplyTemplateResponse(
        formatted_response=formatted_response,
        template_used=template_row['display_name'],
        processing_time_ms=processing_time_ms
    )

# ============================================================================
# Routes admin (pour gérer les templates)
# ============================================================================

@router.get("/admin/templates", response_model=List[ResponseTemplateAdmin])
async def list_all_templates_admin(current_user: dict = Depends(get_current_user)):
    """
    Liste TOUS les templates (actifs et inactifs) avec prompt_instructions.
    Réservé aux admins.
    """
    if not current_user.get('is_admin'):
        raise HTTPException(status_code=403, detail="Admin access required")

    async with database.db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, name, display_name, icon, description, prompt_instructions,
                   is_active, sort_order, created_at, updated_at
            FROM response_templates
            ORDER BY sort_order ASC
        """)

    templates = [ResponseTemplateAdmin(**dict(row)) for row in rows]
    return templates

class UpdateTemplateRequest(BaseModel):
    """Requête pour modifier un template (admin)."""
    display_name: Optional[str] = None
    icon: Optional[str] = None
    description: Optional[str] = None
    prompt_instructions: Optional[str] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None

@router.put("/admin/templates/{template_id}", response_model=ResponseTemplateAdmin)
async def update_template_admin(
    template_id: UUID,
    update: UpdateTemplateRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Modifie un template existant.
    Réservé aux admins.
    """
    if not current_user.get('is_admin'):
        raise HTTPException(status_code=403, detail="Admin access required")

    # Construire la requête de mise à jour dynamiquement
    updates = []
    values = []
    idx = 1

    for field, value in update.dict(exclude_unset=True).items():
        updates.append(f"{field} = ${idx}")
        values.append(value)
        idx += 1

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    values.append(template_id)

    query = f"""
        UPDATE response_templates
        SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP
        WHERE id = ${idx}
        RETURNING id, name, display_name, icon, description, prompt_instructions,
                  is_active, sort_order, created_at, updated_at
    """

    async with database.db_pool.acquire() as conn:
        updated_row = await conn.fetchrow(query, *values)

    if not updated_row:
        raise HTTPException(status_code=404, detail="Template not found")

    return ResponseTemplateAdmin(**dict(updated_row))
