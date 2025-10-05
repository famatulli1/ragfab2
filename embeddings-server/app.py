"""
Serveur d'embeddings FastAPI
Utilise multilingual-e5-large pour des embeddings français optimisés
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional
import logging
from sentence_transformers import SentenceTransformer
import time
import os

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
MODEL_NAME = os.getenv("MODEL_NAME", "intfloat/multilingual-e5-large")
EMBEDDING_DIMENSION = 1024

# Initialisation de l'application
app = FastAPI(
    title="Serveur d'Embeddings",
    description="API d'embeddings multilingue optimisée pour le français",
    version="1.0.0"
)

# Variable globale pour le modèle
model: Optional[SentenceTransformer] = None


@app.on_event("startup")
async def load_model():
    """Charge le modèle au démarrage"""
    global model
    try:
        logger.info(f"Chargement du modèle {MODEL_NAME}...")
        start_time = time.time()
        model = SentenceTransformer(MODEL_NAME)
        load_time = time.time() - start_time
        logger.info(f"Modèle chargé en {load_time:.2f}s")
        logger.info(f"Dimension des embeddings: {model.get_sentence_embedding_dimension()}")
    except Exception as e:
        logger.error(f"Erreur lors du chargement du modèle: {e}")
        raise


class EmbedRequest(BaseModel):
    """Requête pour un embedding unique"""
    text: str

    class Config:
        json_schema_extra = {
            "example": {
                "text": "Ceci est un exemple de texte en français"
            }
        }


class EmbedBatchRequest(BaseModel):
    """Requête pour plusieurs embeddings"""
    texts: List[str]

    class Config:
        json_schema_extra = {
            "example": {
                "texts": [
                    "Premier texte à embedder",
                    "Deuxième texte à embedder"
                ]
            }
        }


class EmbedResponse(BaseModel):
    """Réponse avec un embedding"""
    embedding: List[float]
    dimension: int
    model: str


class EmbedBatchResponse(BaseModel):
    """Réponse avec plusieurs embeddings"""
    embeddings: List[List[float]]
    count: int
    dimension: int
    model: str


@app.get("/")
async def root():
    """Point d'entrée de l'API"""
    return {
        "service": "Serveur d'embeddings",
        "model": MODEL_NAME,
        "dimension": EMBEDDING_DIMENSION,
        "status": "ready" if model is not None else "loading"
    }


@app.get("/health")
async def health_check():
    """Vérification de santé du service"""
    if model is None:
        raise HTTPException(status_code=503, detail="Modèle non chargé")

    return {
        "status": "healthy",
        "model": MODEL_NAME,
        "dimension": model.get_sentence_embedding_dimension()
    }


@app.post("/embed", response_model=EmbedResponse)
async def embed_text(request: EmbedRequest):
    """
    Génère un embedding pour un texte unique

    Args:
        request: Requête contenant le texte à embedder

    Returns:
        Embedding du texte
    """
    if model is None:
        raise HTTPException(status_code=503, detail="Modèle non chargé")

    if not request.text or not request.text.strip():
        raise HTTPException(status_code=400, detail="Le texte ne peut pas être vide")

    try:
        # Pour E5, préfixer avec "query: " pour les recherches
        # ou "passage: " pour les documents
        # Ici on laisse tel quel pour plus de flexibilité
        start_time = time.time()
        embedding = model.encode(request.text, normalize_embeddings=True)
        elapsed = time.time() - start_time

        logger.info(f"Embedding généré en {elapsed:.3f}s pour {len(request.text)} caractères")

        return EmbedResponse(
            embedding=embedding.tolist(),
            dimension=len(embedding),
            model=MODEL_NAME
        )
    except Exception as e:
        logger.error(f"Erreur lors de la génération de l'embedding: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/embed_batch", response_model=EmbedBatchResponse)
async def embed_batch(request: EmbedBatchRequest):
    """
    Génère des embeddings pour plusieurs textes

    Args:
        request: Requête contenant la liste des textes

    Returns:
        Liste des embeddings
    """
    if model is None:
        raise HTTPException(status_code=503, detail="Modèle non chargé")

    if not request.texts:
        raise HTTPException(status_code=400, detail="La liste de textes ne peut pas être vide")

    # Filtrer les textes vides
    valid_texts = [text for text in request.texts if text and text.strip()]

    if not valid_texts:
        raise HTTPException(status_code=400, detail="Aucun texte valide fourni")

    try:
        start_time = time.time()
        embeddings = model.encode(valid_texts, normalize_embeddings=True, show_progress_bar=False)
        elapsed = time.time() - start_time

        logger.info(f"Batch de {len(valid_texts)} embeddings généré en {elapsed:.3f}s")

        return EmbedBatchResponse(
            embeddings=[emb.tolist() for emb in embeddings],
            count=len(embeddings),
            dimension=len(embeddings[0]),
            model=MODEL_NAME
        )
    except Exception as e:
        logger.error(f"Erreur lors de la génération du batch: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/info")
async def model_info():
    """Informations sur le modèle"""
    if model is None:
        raise HTTPException(status_code=503, detail="Modèle non chargé")

    return {
        "model_name": MODEL_NAME,
        "embedding_dimension": model.get_sentence_embedding_dimension(),
        "max_seq_length": model.max_seq_length,
        "description": "Modèle multilingue optimisé pour le français (E5-large)"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8001,
        log_level="info"
    )
