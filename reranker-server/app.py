"""
Serveur de Reranking FastAPI
Utilise BAAI/bge-reranker-v2-m3 pour affiner les résultats de recherche vectorielle
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import logging
from sentence_transformers import CrossEncoder
import time
import os

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")

# Initialisation de l'application
app = FastAPI(
    title="Serveur de Reranking",
    description="API de reranking multilingue pour améliorer la pertinence des résultats RAG",
    version="1.0.0"
)

# Variable globale pour le modèle
model: Optional[CrossEncoder] = None


@app.on_event("startup")
async def load_model():
    """Charge le modèle de reranking au démarrage"""
    global model
    try:
        logger.info(f"Chargement du modèle de reranking {RERANKER_MODEL}...")
        start_time = time.time()
        model = CrossEncoder(RERANKER_MODEL, max_length=512)
        load_time = time.time() - start_time
        logger.info(f"Modèle de reranking chargé en {load_time:.2f}s")
    except Exception as e:
        logger.error(f"Erreur lors du chargement du modèle: {e}")
        raise


class DocumentItem(BaseModel):
    """Un document à reranker"""
    chunk_id: str
    document_id: str
    document_title: str
    document_source: str
    chunk_index: int
    content: str
    similarity: float

    class Config:
        json_schema_extra = {
            "example": {
                "chunk_id": "123e4567-e89b-12d3-a456-426614174000",
                "document_id": "987e6543-e21b-34d5-b678-426614174111",
                "document_title": "Guide_Medical.pdf",
                "document_source": "/documents/Guide_Medical.pdf",
                "chunk_index": 5,
                "content": "Le traitement de cette pathologie nécessite...",
                "similarity": 0.85
            }
        }


class RerankRequest(BaseModel):
    """Requête de reranking"""
    query: str
    documents: List[DocumentItem]
    top_k: Optional[int] = 5

    class Config:
        json_schema_extra = {
            "example": {
                "query": "Quel est le traitement de cette pathologie ?",
                "documents": [
                    {
                        "chunk_id": "123",
                        "document_id": "456",
                        "document_title": "Guide.pdf",
                        "document_source": "/docs/guide.pdf",
                        "chunk_index": 1,
                        "content": "Le traitement...",
                        "similarity": 0.85
                    }
                ],
                "top_k": 5
            }
        }


class RerankResponse(BaseModel):
    """Réponse avec documents reranked"""
    documents: List[DocumentItem]
    count: int
    model: str
    processing_time: float


@app.get("/")
async def root():
    """Point d'entrée de l'API"""
    return {
        "service": "Serveur de reranking",
        "model": RERANKER_MODEL,
        "status": "ready" if model is not None else "loading"
    }


@app.get("/health")
async def health_check():
    """Vérification de santé du service"""
    if model is None:
        raise HTTPException(status_code=503, detail="Modèle non chargé")

    return {
        "status": "healthy",
        "model": RERANKER_MODEL
    }


@app.post("/rerank", response_model=RerankResponse)
async def rerank_documents(request: RerankRequest):
    """
    Rerank les documents en fonction de leur pertinence par rapport à la query

    Le modèle CrossEncoder analyse la relation sémantique fine entre la query
    et chaque document, produisant un score de pertinence plus précis que la
    simple similarité cosinus des embeddings.

    Args:
        request: Requête contenant la query et la liste des documents

    Returns:
        Documents triés par pertinence décroissante
    """
    if model is None:
        raise HTTPException(status_code=503, detail="Modèle non chargé")

    if not request.query or not request.query.strip():
        raise HTTPException(status_code=400, detail="La query ne peut pas être vide")

    if not request.documents:
        raise HTTPException(status_code=400, detail="La liste de documents ne peut pas être vide")

    try:
        start_time = time.time()

        # Créer des paires (query, document_content) pour le CrossEncoder
        pairs = [[request.query, doc.content] for doc in request.documents]

        # Obtenir les scores de reranking
        # Le CrossEncoder retourne des scores (pas des probabilités)
        # Plus le score est élevé, plus la pertinence est forte
        scores = model.predict(pairs)

        # Combiner documents avec leurs scores et trier par score décroissant
        docs_with_scores = list(zip(request.documents, scores))
        docs_with_scores.sort(key=lambda x: x[1], reverse=True)

        # Extraire les top-k documents
        top_k = min(request.top_k, len(docs_with_scores))
        reranked_docs = [doc for doc, score in docs_with_scores[:top_k]]

        elapsed = time.time() - start_time

        logger.info(
            f"Reranked {len(request.documents)} documents en {elapsed:.3f}s, "
            f"retourné top-{top_k}"
        )

        return RerankResponse(
            documents=reranked_docs,
            count=len(reranked_docs),
            model=RERANKER_MODEL,
            processing_time=elapsed
        )

    except Exception as e:
        logger.error(f"Erreur lors du reranking: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/info")
async def model_info():
    """Informations sur le modèle de reranking"""
    if model is None:
        raise HTTPException(status_code=503, detail="Modèle non chargé")

    return {
        "model_name": RERANKER_MODEL,
        "max_length": model.max_length,
        "description": "Modèle de reranking multilingue optimisé pour affiner les résultats de recherche vectorielle"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8002,
        log_level="info"
    )
