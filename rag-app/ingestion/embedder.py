"""
Document embedding generation via serveur d'embeddings personnalisé
Adapté pour utiliser le serveur FastAPI d'embeddings au lieu d'OpenAI
"""

import os
import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import httpx
from dotenv import load_dotenv

from .chunker import DocumentChunk

load_dotenv()

logger = logging.getLogger(__name__)

# Configuration du serveur d'embeddings
EMBEDDINGS_API_URL = os.getenv("EMBEDDINGS_API_URL", "http://localhost:8001")
EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "1024"))


class EmbeddingGenerator:
    """Génère des embeddings via le serveur d'embeddings personnalisé."""

    def __init__(
        self,
        api_url: str = EMBEDDINGS_API_URL,
        dimension: int = EMBEDDING_DIMENSION,
        batch_size: int = 100,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        timeout: float = 60.0,
    ):
        """
        Initialize embedding generator.

        Args:
            api_url: URL du serveur d'embeddings
            dimension: Dimension des embeddings attendue
            batch_size: Nombre de textes à traiter en parallèle
            max_retries: Nombre maximum de tentatives
            retry_delay: Délai entre les tentatives en secondes
            timeout: Timeout des requêtes HTTP
        """
        self.api_url = api_url.rstrip("/")
        self.dimension = dimension
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout

        # Endpoints
        self.embed_endpoint = f"{self.api_url}/embed"
        self.embed_batch_endpoint = f"{self.api_url}/embed_batch"
        self.health_endpoint = f"{self.api_url}/health"

        logger.info(f"Embedding generator initialized with API: {self.api_url}")

    async def check_health(self) -> bool:
        """
        Vérifie que le serveur d'embeddings est accessible

        Returns:
            True si le serveur répond, False sinon
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.health_endpoint)
                response.raise_for_status()
                data = response.json()
                logger.info(f"Serveur d'embeddings: {data.get('status', 'unknown')}")
                return True
        except Exception as e:
            logger.error(f"Serveur d'embeddings non accessible: {e}")
            return False

    async def generate_embedding(self, text: str) -> List[float]:
        """
        Génère un embedding pour un texte unique

        Args:
            text: Texte à embedder

        Returns:
            Vecteur d'embedding
        """
        if not text or not text.strip():
            logger.warning("Texte vide fourni, retour d'un vecteur zéro")
            return [0.0] * self.dimension

        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        self.embed_endpoint,
                        json={"text": text},
                    )
                    response.raise_for_status()
                    result = response.json()

                embedding = result.get("embedding", [])

                if len(embedding) != self.dimension:
                    logger.warning(
                        f"Dimension incorrecte: attendu {self.dimension}, reçu {len(embedding)}"
                    )

                return embedding

            except httpx.HTTPError as e:
                if attempt == self.max_retries - 1:
                    logger.error(f"Échec de génération d'embedding après {self.max_retries} tentatives: {e}")
                    raise

                delay = self.retry_delay * (2 ** attempt)
                logger.warning(f"Erreur HTTP, nouvelle tentative dans {delay}s")
                await asyncio.sleep(delay)

            except Exception as e:
                logger.error(f"Erreur inattendue lors de la génération d'embedding: {e}")
                if attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(self.retry_delay)

        # Fallback: retourner un vecteur zéro
        return [0.0] * self.dimension

    async def generate_embeddings_batch(
        self, texts: List[str]
    ) -> List[List[float]]:
        """
        Génère des embeddings pour un batch de textes

        Args:
            texts: Liste de textes à embedder

        Returns:
            Liste de vecteurs d'embeddings
        """
        if not texts:
            return []

        # Filtrer les textes vides
        processed_texts = [text if text and text.strip() else "" for text in texts]

        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        self.embed_batch_endpoint,
                        json={"texts": processed_texts},
                    )
                    response.raise_for_status()
                    result = response.json()

                embeddings = result.get("embeddings", [])

                if len(embeddings) != len(processed_texts):
                    logger.warning(
                        f"Nombre d'embeddings incorrect: attendu {len(processed_texts)}, reçu {len(embeddings)}"
                    )

                return embeddings

            except httpx.HTTPError as e:
                if attempt == self.max_retries - 1:
                    logger.error(f"Échec du batch après {self.max_retries} tentatives: {e}")
                    # Fallback: traiter individuellement
                    return await self._process_individually(processed_texts)

                delay = self.retry_delay * (2 ** attempt)
                logger.warning(f"Erreur HTTP batch, nouvelle tentative dans {delay}s")
                await asyncio.sleep(delay)

            except Exception as e:
                logger.error(f"Erreur lors du batch embedding: {e}")
                if attempt == self.max_retries - 1:
                    return await self._process_individually(processed_texts)
                await asyncio.sleep(self.retry_delay)

        # Fallback
        return [[0.0] * self.dimension for _ in processed_texts]

    async def _process_individually(
        self, texts: List[str]
    ) -> List[List[float]]:
        """
        Traite les textes individuellement en cas d'échec du batch

        Args:
            texts: Liste de textes

        Returns:
            Liste d'embeddings
        """
        embeddings = []

        for text in texts:
            try:
                if not text or not text.strip():
                    embeddings.append([0.0] * self.dimension)
                    continue

                embedding = await self.generate_embedding(text)
                embeddings.append(embedding)

                # Petit délai pour ne pas surcharger l'API
                await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(f"Échec d'embedding pour un texte: {e}")
                embeddings.append([0.0] * self.dimension)

        return embeddings

    async def embed_chunks(
        self,
        chunks: List[DocumentChunk],
        progress_callback: Optional[callable] = None,
    ) -> List[DocumentChunk]:
        """
        Génère des embeddings pour des chunks de documents

        Args:
            chunks: Liste de chunks
            progress_callback: Callback optionnel pour la progression

        Returns:
            Chunks avec embeddings ajoutés
        """
        if not chunks:
            return chunks

        logger.info(f"Génération d'embeddings pour {len(chunks)} chunks")

        # Vérifier que le serveur est accessible
        if not await self.check_health():
            raise RuntimeError(
                f"Le serveur d'embeddings n'est pas accessible à {self.api_url}. "
                "Vérifiez qu'il est démarré et accessible."
            )

        # Traiter par batches
        embedded_chunks = []
        total_batches = (len(chunks) + self.batch_size - 1) // self.batch_size

        for i in range(0, len(chunks), self.batch_size):
            batch_chunks = chunks[i : i + self.batch_size]
            batch_texts = [chunk.content for chunk in batch_chunks]

            try:
                # Générer les embeddings
                embeddings = await self.generate_embeddings_batch(batch_texts)

                # Ajouter les embeddings aux chunks
                for chunk, embedding in zip(batch_chunks, embeddings):
                    chunk.metadata.update({
                        "embedding_model": "multilingual-e5-large",
                        "embedding_dimension": self.dimension,
                        "embedding_generated_at": datetime.now().isoformat(),
                    })
                    chunk.embedding = embedding
                    embedded_chunks.append(chunk)

                # Mise à jour de la progression
                current_batch = (i // self.batch_size) + 1
                if progress_callback:
                    progress_callback(current_batch, total_batches)

                logger.info(f"Batch {current_batch}/{total_batches} traité")

            except Exception as e:
                logger.error(f"Échec du batch {i // self.batch_size + 1}: {e}")

                # Ajouter les chunks avec des vecteurs zéro en fallback
                for chunk in batch_chunks:
                    chunk.metadata.update({
                        "embedding_error": str(e),
                        "embedding_generated_at": datetime.now().isoformat(),
                    })
                    chunk.embedding = [0.0] * self.dimension
                    embedded_chunks.append(chunk)

        logger.info(f"Embeddings générés pour {len(embedded_chunks)} chunks")
        return embedded_chunks

    async def embed_query(self, query: str) -> List[float]:
        """
        Génère un embedding pour une requête de recherche

        Args:
            query: Requête de recherche

        Returns:
            Embedding de la requête
        """
        return await self.generate_embedding(query)

    def get_embedding_dimension(self) -> int:
        """Retourne la dimension des embeddings"""
        return self.dimension


# Factory function
def create_embedder(
    api_url: str = EMBEDDINGS_API_URL,
    **kwargs,
) -> EmbeddingGenerator:
    """
    Crée un générateur d'embeddings

    Args:
        api_url: URL du serveur d'embeddings
        **kwargs: Arguments additionnels

    Returns:
        Instance d'EmbeddingGenerator
    """
    return EmbeddingGenerator(api_url=api_url, **kwargs)


# Exemple d'utilisation
async def main():
    """Exemple d'utilisation de l'embedder"""
    from .chunker import ChunkingConfig, create_chunker

    # Créer chunker et embedder
    config = ChunkingConfig(chunk_size=200, use_semantic_splitting=False)
    chunker = create_chunker(config)
    embedder = create_embedder()

    sample_text = """
    Les initiatives d'IA de Google incluent des modèles de langage avancés,
    la vision par ordinateur et la recherche en apprentissage automatique.
    L'entreprise a beaucoup investi dans les architectures de transformateurs
    et l'optimisation des réseaux neuronaux.
    """

    # Chunker le document
    chunks = chunker.chunk_document(
        content=sample_text, title="Initiatives IA", source="example.md"
    )

    print(f"Créé {len(chunks)} chunks")

    # Générer les embeddings
    def progress_callback(current, total):
        print(f"Traitement du batch {current}/{total}")

    embedded_chunks = await embedder.embed_chunks(chunks, progress_callback)

    for i, chunk in enumerate(embedded_chunks):
        print(
            f"Chunk {i}: {len(chunk.content)} caractères, "
            f"embedding dim: {len(chunk.embedding)}"
        )

    # Test query embedding
    query_embedding = await embedder.embed_query("Recherche IA Google")
    print(f"Dimension de l'embedding de requête: {len(query_embedding)}")


if __name__ == "__main__":
    asyncio.run(main())
