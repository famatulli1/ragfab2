"""
Unit tests for ingestion/embedder.py
Tests embedding generation functionality with mocked HTTP calls
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List
import httpx

from ingestion.embedder import (
    EmbeddingGenerator,
    create_embedder,
    EMBEDDINGS_API_URL,
    EMBEDDING_DIMENSION,
)
from ingestion.chunker import DocumentChunk


@pytest.fixture
def embedder():
    """Create embedder with test configuration"""
    return EmbeddingGenerator(
        api_url="http://test-api:8001",
        dimension=1024,
        batch_size=5,
        max_retries=2,
        retry_delay=0.1,
        timeout=10.0,
    )


@pytest.fixture
def sample_chunks():
    """Create sample document chunks for testing"""
    return [
        DocumentChunk(
            content=f"Test content {i}",
            index=i,
            start_char=i * 100,
            end_char=(i + 1) * 100,
            metadata={
                "test": True,
                "title": "Test Doc",
                "source": "test.md"
            },
            token_count=10,
        )
        for i in range(3)
    ]


@pytest.mark.unit
class TestEmbeddingGeneratorInit:
    """Test EmbeddingGenerator initialization"""

    def test_init_defaults(self):
        """Test initialization with default values"""
        embedder = EmbeddingGenerator()
        assert embedder.api_url == EMBEDDINGS_API_URL.rstrip("/")
        assert embedder.dimension == EMBEDDING_DIMENSION
        assert embedder.batch_size == 20
        assert embedder.max_retries == 3

    def test_init_custom_values(self):
        """Test initialization with custom values"""
        embedder = EmbeddingGenerator(
            api_url="http://custom:9000",
            dimension=768,
            batch_size=10,
            max_retries=5,
            retry_delay=2.0,
            timeout=120.0,
        )
        assert embedder.api_url == "http://custom:9000"
        assert embedder.dimension == 768
        assert embedder.batch_size == 10
        assert embedder.max_retries == 5
        assert embedder.retry_delay == 2.0
        assert embedder.timeout == 120.0

    def test_endpoints_set_correctly(self):
        """Test API endpoints are set correctly"""
        embedder = EmbeddingGenerator(api_url="http://test:8001")
        assert embedder.embed_endpoint == "http://test:8001/embed"
        assert embedder.embed_batch_endpoint == "http://test:8001/embed_batch"
        assert embedder.health_endpoint == "http://test:8001/health"


@pytest.mark.unit
@pytest.mark.asyncio
class TestHealthCheck:
    """Test health check functionality"""

    async def test_check_health_success(self, embedder):
        """Test successful health check"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "healthy"}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            result = await embedder.check_health()
            assert result is True

    async def test_check_health_failure(self, embedder):
        """Test health check when service is down"""
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.ConnectError("Connection failed")
            )
            result = await embedder.check_health()
            assert result is False


@pytest.mark.unit
@pytest.mark.asyncio
class TestGenerateEmbedding:
    """Test single embedding generation"""

    async def test_generate_embedding_success(self, embedder):
        """Test successful single embedding generation"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "embedding": [0.1] * 1024,
            "dimension": 1024,
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            embedding = await embedder.generate_embedding("test text")
            assert len(embedding) == 1024
            assert all(isinstance(x, float) for x in embedding)

    async def test_generate_embedding_empty_text(self, embedder):
        """Test embedding generation with empty text"""
        embedding = await embedder.generate_embedding("")
        assert len(embedding) == 1024
        assert all(x == 0.0 for x in embedding)

    async def test_generate_embedding_whitespace_only(self, embedder):
        """Test embedding generation with whitespace only"""
        embedding = await embedder.generate_embedding("   \n\t  ")
        assert len(embedding) == 1024
        assert all(x == 0.0 for x in embedding)

    async def test_generate_embedding_wrong_dimension(self, embedder):
        """Test handling of wrong dimension in response"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "embedding": [0.1] * 768,  # Wrong dimension
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            embedding = await embedder.generate_embedding("test")
            assert len(embedding) == 768  # Returns what server gave

    async def test_generate_embedding_retry_logic(self, embedder):
        """Test retry logic on HTTP errors"""
        embedder.max_retries = 3
        embedder.retry_delay = 0.01

        with patch("httpx.AsyncClient") as mock_client:
            # First two calls fail, third succeeds
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=[
                    httpx.HTTPError("Error 1"),
                    httpx.HTTPError("Error 2"),
                    MagicMock(
                        json=lambda: {"embedding": [0.1] * 1024},
                        raise_for_status=lambda: None,
                    ),
                ]
            )

            embedding = await embedder.generate_embedding("test")
            assert len(embedding) == 1024

    async def test_generate_embedding_max_retries_exceeded(self, embedder):
        """Test behavior when max retries exceeded"""
        embedder.max_retries = 2
        embedder.retry_delay = 0.01

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.HTTPError("Persistent error")
            )

            with pytest.raises(httpx.HTTPError):
                await embedder.generate_embedding("test")


@pytest.mark.unit
@pytest.mark.asyncio
class TestGenerateEmbeddingsBatch:
    """Test batch embedding generation"""

    async def test_generate_embeddings_batch_success(self, embedder):
        """Test successful batch embedding generation"""
        texts = ["text 1", "text 2", "text 3"]
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "embeddings": [[0.1] * 1024, [0.2] * 1024, [0.3] * 1024],
            "count": 3,
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            embeddings = await embedder.generate_embeddings_batch(texts)
            assert len(embeddings) == 3
            assert all(len(e) == 1024 for e in embeddings)

    async def test_generate_embeddings_batch_empty_list(self, embedder):
        """Test batch generation with empty list"""
        embeddings = await embedder.generate_embeddings_batch([])
        assert embeddings == []

    async def test_generate_embeddings_batch_with_empty_texts(self, embedder):
        """Test batch generation with some empty texts"""
        texts = ["text 1", "", "text 3", "   "]
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "embeddings": [[0.1] * 1024, [0.0] * 1024, [0.3] * 1024, [0.0] * 1024],
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            embeddings = await embedder.generate_embeddings_batch(texts)
            assert len(embeddings) == 4

    async def test_generate_embeddings_batch_fallback_to_individual(self, embedder):
        """Test fallback to individual processing when batch fails"""
        texts = ["text 1", "text 2"]

        # Mock batch endpoint failure
        with patch("httpx.AsyncClient") as mock_client:
            # Batch call fails
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.HTTPError("Batch failed")
            )

            # Mock individual calls succeeding
            with patch.object(
                embedder, "_process_individually", new_callable=AsyncMock
            ) as mock_individual:
                mock_individual.return_value = [[0.1] * 1024, [0.2] * 1024]

                embeddings = await embedder.generate_embeddings_batch(texts)
                assert len(embeddings) == 2
                mock_individual.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
class TestProcessIndividually:
    """Test individual text processing"""

    async def test_process_individually_success(self, embedder):
        """Test successful individual processing"""
        texts = ["text 1", "text 2", "text 3"]

        with patch.object(
            embedder, "generate_embedding", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.side_effect = [
                [0.1] * 1024,
                [0.2] * 1024,
                [0.3] * 1024,
            ]

            embeddings = await embedder._process_individually(texts)
            assert len(embeddings) == 3
            assert mock_gen.call_count == 3

    async def test_process_individually_with_empty_texts(self, embedder):
        """Test individual processing with empty texts"""
        texts = ["text 1", "", "text 3"]

        embeddings = await embedder._process_individually(texts)
        assert len(embeddings) == 3
        assert embeddings[1] == [0.0] * 1024  # Empty text gets zero vector

    async def test_process_individually_handles_errors(self, embedder):
        """Test error handling in individual processing"""
        texts = ["text 1", "text 2"]

        with patch.object(
            embedder, "generate_embedding", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.side_effect = [
                [0.1] * 1024,
                Exception("Generation failed"),
            ]

            embeddings = await embedder._process_individually(texts)
            assert len(embeddings) == 2
            assert embeddings[0] == [0.1] * 1024
            assert embeddings[1] == [0.0] * 1024  # Error gets zero vector


@pytest.mark.unit
@pytest.mark.asyncio
class TestEmbedChunks:
    """Test chunk embedding functionality"""

    async def test_embed_chunks_success(self, embedder, sample_chunks):
        """Test successful chunk embedding"""
        # Mock health check
        with patch.object(embedder, "check_health", new_callable=AsyncMock) as mock_health:
            mock_health.return_value = True

            # Mock batch generation
            with patch.object(
                embedder, "generate_embeddings_batch", new_callable=AsyncMock
            ) as mock_batch:
                mock_batch.return_value = [[0.1] * 1024, [0.2] * 1024, [0.3] * 1024]

                embedded = await embedder.embed_chunks(sample_chunks)
                assert len(embedded) == 3
                assert all(len(chunk.embedding) == 1024 for chunk in embedded)
                assert all("embedding_model" in chunk.metadata for chunk in embedded)

    async def test_embed_chunks_empty_list(self, embedder):
        """Test embedding empty chunk list"""
        embedded = await embedder.embed_chunks([])
        assert embedded == []

    async def test_embed_chunks_service_unavailable(self, embedder, sample_chunks):
        """Test behavior when embedding service is unavailable"""
        with patch.object(embedder, "check_health", new_callable=AsyncMock) as mock_health:
            mock_health.return_value = False

            with pytest.raises(RuntimeError, match="n'est pas accessible"):
                await embedder.embed_chunks(sample_chunks)

    async def test_embed_chunks_with_progress_callback(self, embedder, sample_chunks):
        """Test chunk embedding with progress callback"""
        progress_calls = []

        def progress_callback(current, total):
            progress_calls.append((current, total))

        with patch.object(embedder, "check_health", new_callable=AsyncMock) as mock_health:
            mock_health.return_value = True

            with patch.object(
                embedder, "generate_embeddings_batch", new_callable=AsyncMock
            ) as mock_batch:
                mock_batch.return_value = [[0.1] * 1024, [0.2] * 1024, [0.3] * 1024]

                await embedder.embed_chunks(sample_chunks, progress_callback)
                assert len(progress_calls) > 0
                assert progress_calls[0] == (1, 1)  # One batch for 3 chunks

    async def test_embed_chunks_batch_error_fallback(self, embedder, sample_chunks):
        """Test fallback to zero vectors when batch fails"""
        with patch.object(embedder, "check_health", new_callable=AsyncMock) as mock_health:
            mock_health.return_value = True

            with patch.object(
                embedder, "generate_embeddings_batch", new_callable=AsyncMock
            ) as mock_batch:
                mock_batch.side_effect = Exception("Batch processing failed")

                embedded = await embedder.embed_chunks(sample_chunks)
                assert len(embedded) == 3
                assert all(chunk.embedding == [0.0] * 1024 for chunk in embedded)
                assert all("embedding_error" in chunk.metadata for chunk in embedded)


@pytest.mark.unit
@pytest.mark.asyncio
class TestEmbedQuery:
    """Test query embedding"""

    async def test_embed_query_success(self, embedder):
        """Test successful query embedding"""
        with patch.object(
            embedder, "generate_embedding", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = [0.1] * 1024

            embedding = await embedder.embed_query("test query")
            assert len(embedding) == 1024
            mock_gen.assert_called_once_with("test query")


@pytest.mark.unit
class TestUtilityFunctions:
    """Test utility functions"""

    def test_get_embedding_dimension(self, embedder):
        """Test dimension getter"""
        assert embedder.get_embedding_dimension() == 1024

    def test_create_embedder_factory(self):
        """Test factory function"""
        embedder = create_embedder(
            api_url="http://custom:8002",
            dimension=768,
            batch_size=15,
        )
        assert embedder.api_url == "http://custom:8002"
        assert embedder.dimension == 768
        assert embedder.batch_size == 15
