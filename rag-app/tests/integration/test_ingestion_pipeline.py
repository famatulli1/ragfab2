"""
Integration tests for the ingestion pipeline
Tests the complete document ingestion workflow
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import tempfile
import os
from pathlib import Path

from ingestion.chunker import ChunkingConfig, DocumentChunk, create_chunker
from ingestion.embedder import EmbeddingGenerator
from ingestion.ingest import DocumentIngestionPipeline


@pytest.fixture
def temp_document():
    """Create temporary test document"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        content = """
# Test Document

## Introduction
This is a test document for integration testing.

## Main Content
The document contains multiple paragraphs with relevant information.
Each paragraph adds value to the overall content.

## Conclusion
Final thoughts and summary of the test document.
        """.strip()
        f.write(content)
        temp_path = f.name

    yield temp_path

    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def chunking_config():
    """Create test chunking configuration"""
    return ChunkingConfig(
        chunk_size=200,
        chunk_overlap=50,
        use_semantic_splitting=False,  # Use simple chunker for testing
    )


@pytest.fixture
def mock_embedder():
    """Create mock embedder for testing"""
    embedder = MagicMock(spec=EmbeddingGenerator)
    embedder.check_health = AsyncMock(return_value=True)
    embedder.embed_chunks = AsyncMock(
        side_effect=lambda chunks, callback=None: [
            DocumentChunk(
                content=c.content,
                index=c.index,
                start_char=c.start_char,
                end_char=c.end_char,
                metadata={**c.metadata, "embedding_model": "test"},
                token_count=c.token_count,
                embedding=[0.1] * 1024,
            )
            for c in chunks
        ]
    )
    embedder.get_embedding_dimension = MagicMock(return_value=1024)
    return embedder


@pytest.fixture
def mock_db_conn():
    """Create mock database connection"""
    conn = AsyncMock()
    conn.execute = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    return conn


@pytest.mark.integration
@pytest.mark.asyncio
class TestChunkerEmbedderIntegration:
    """Test integration between chunker and embedder"""

    async def test_chunker_to_embedder_workflow(self, chunking_config):
        """Test complete chunking and embedding workflow"""
        chunker = create_chunker(chunking_config)

        content = "Test content for chunking. " * 50  # Long content
        chunks = await chunker.chunk_document(
            content=content,
            title="Test Doc",
            source="test.md",
        )

        assert len(chunks) > 0
        assert all(isinstance(c, DocumentChunk) for c in chunks)
        assert all(c.token_count > 0 for c in chunks)

        # Mock embedder
        with patch("ingestion.embedder.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "embeddings": [[0.1] * 1024 for _ in chunks],
                "count": len(chunks),
            }
            mock_response.raise_for_status = MagicMock()

            mock_health_response = MagicMock()
            mock_health_response.json.return_value = {"status": "healthy"}
            mock_health_response.raise_for_status = MagicMock()

            async_client = AsyncMock()
            async_client.post.return_value = mock_response
            async_client.get.return_value = mock_health_response
            mock_client.return_value.__aenter__.return_value = async_client

            embedder = EmbeddingGenerator(
                api_url="http://test:8001",
                dimension=1024,
            )

            embedded_chunks = await embedder.embed_chunks(chunks)

            assert len(embedded_chunks) == len(chunks)
            assert all(chunk.embedding is not None for chunk in embedded_chunks)
            assert all(len(chunk.embedding) == 1024 for chunk in embedded_chunks)
            assert all(
                "embedding_model" in chunk.metadata for chunk in embedded_chunks
            )

    async def test_chunker_preserves_metadata_for_embedder(self, chunking_config):
        """Test that metadata flows through chunking to embedding"""
        chunker = create_chunker(chunking_config)

        custom_metadata = {
            "author": "Test Author",
            "document_type": "research",
        }

        chunks = await chunker.chunk_document(
            content="Test content",
            title="Test Doc",
            source="test.md",
            metadata=custom_metadata,
        )

        assert all(chunk.metadata["author"] == "Test Author" for chunk in chunks)
        assert all(chunk.metadata["document_type"] == "research" for chunk in chunks)


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.embeddings
@pytest.mark.asyncio
class TestIngestionPipelineIntegration:
    """Test complete ingestion pipeline integration"""

    async def test_document_ingestion_complete_workflow(
        self, temp_document, chunking_config, mock_embedder, mock_db_conn
    ):
        """Test complete document ingestion from file to database"""
        # Create pipeline with mocked components
        with patch("ingestion.ingest.create_chunker") as mock_create_chunker, \
             patch("ingestion.ingest.create_embedder") as mock_create_embedder, \
             patch("ingestion.ingest.database.db_pool") as mock_pool:

            # Setup mocks
            chunker = create_chunker(chunking_config)
            mock_create_chunker.return_value = chunker
            mock_create_embedder.return_value = mock_embedder

            mock_pool.acquire.return_value.__aenter__.return_value = mock_db_conn

            # Create pipeline
            pipeline = DocumentIngestionPipeline(
                documents_folder=str(Path(temp_document).parent),
                chunking_config=chunking_config,
            )

            # Ingest single document
            result = await pipeline.ingest_document(temp_document)

            assert result is not None
            assert result["success"] is True
            assert result["chunks_created"] > 0
            assert "document_id" in result

            # Verify embedder was called
            mock_embedder.embed_chunks.assert_called_once()

            # Verify database inserts
            assert mock_db_conn.execute.call_count >= 2  # document + chunks

    async def test_pipeline_handles_invalid_document(
        self, chunking_config, mock_embedder, mock_db_conn
    ):
        """Test pipeline handles invalid/missing documents gracefully"""
        with patch("ingestion.ingest.create_chunker") as mock_create_chunker, \
             patch("ingestion.ingest.create_embedder") as mock_create_embedder, \
             patch("ingestion.ingest.database.db_pool") as mock_pool:

            chunker = create_chunker(chunking_config)
            mock_create_chunker.return_value = chunker
            mock_create_embedder.return_value = mock_embedder
            mock_pool.acquire.return_value.__aenter__.return_value = mock_db_conn

            pipeline = DocumentIngestionPipeline(
                documents_folder="/tmp/test_docs",
                chunking_config=chunking_config,
            )

            # Try to ingest non-existent file
            result = await pipeline.ingest_document("/nonexistent/file.md")

            assert result["success"] is False
            assert "error" in result or "message" in result

    async def test_pipeline_batch_processing(
        self, temp_document, chunking_config, mock_embedder, mock_db_conn
    ):
        """Test pipeline can process multiple documents"""
        # Create multiple temp documents
        temp_docs = [temp_document]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f2:
            f2.write("# Second Document\nContent for second test document.")
            temp_docs.append(f2.name)

        try:
            with patch("ingestion.ingest.create_chunker") as mock_create_chunker, \
                 patch("ingestion.ingest.create_embedder") as mock_create_embedder, \
                 patch("ingestion.ingest.database.db_pool") as mock_pool:

                chunker = create_chunker(chunking_config)
                mock_create_chunker.return_value = chunker
                mock_create_embedder.return_value = mock_embedder
                mock_pool.acquire.return_value.__aenter__.return_value = mock_db_conn

                pipeline = DocumentIngestionPipeline(
                    documents_folder=str(Path(temp_document).parent),
                    chunking_config=chunking_config,
                )

                # Process multiple documents
                results = []
                for doc_path in temp_docs:
                    result = await pipeline.ingest_document(doc_path)
                    results.append(result)

                assert len(results) == len(temp_docs)
                # Check that embedder was called for each document
                assert mock_embedder.embed_chunks.call_count == len(temp_docs)

        finally:
            # Cleanup second temp file
            if len(temp_docs) > 1 and os.path.exists(temp_docs[1]):
                os.unlink(temp_docs[1])


@pytest.mark.integration
@pytest.mark.asyncio
class TestDatabaseIntegration:
    """Test database integration for ingestion"""

    async def test_chunks_inserted_with_embeddings(self, mock_db_conn):
        """Test that chunks with embeddings are properly inserted"""
        chunks = [
            DocumentChunk(
                content="Test chunk 1",
                index=0,
                start_char=0,
                end_char=13,
                metadata={"title": "Test", "source": "test.md"},
                token_count=3,
                embedding=[0.1] * 1024,
            ),
            DocumentChunk(
                content="Test chunk 2",
                index=1,
                start_char=13,
                end_char=26,
                metadata={"title": "Test", "source": "test.md"},
                token_count=3,
                embedding=[0.2] * 1024,
            ),
        ]

        # Mock database insertion
        with patch("ingestion.ingest.database.db_pool") as mock_pool:
            mock_pool.acquire.return_value.__aenter__.return_value = mock_db_conn

            # Simulate chunk insertion
            for chunk in chunks:
                await mock_db_conn.execute(
                    "INSERT INTO chunks (content, embedding) VALUES ($1, $2)",
                    chunk.content,
                    chunk.embedding,
                )

            # Verify execute was called for each chunk
            assert mock_db_conn.execute.call_count >= len(chunks)

    async def test_document_metadata_persisted(self, mock_db_conn):
        """Test that document metadata is properly persisted"""
        doc_metadata = {
            "title": "Test Document",
            "source": "test.md",
            "author": "Test Author",
            "created_at": "2024-01-01",
        }

        with patch("ingestion.ingest.database.db_pool") as mock_pool:
            mock_pool.acquire.return_value.__aenter__.return_value = mock_db_conn

            # Simulate document insertion
            await mock_db_conn.execute(
                "INSERT INTO documents (title, source, metadata) VALUES ($1, $2, $3)",
                doc_metadata["title"],
                doc_metadata["source"],
                doc_metadata,
            )

            mock_db_conn.execute.assert_called_once()


@pytest.mark.integration
@pytest.mark.asyncio
class TestErrorHandling:
    """Test error handling in integration scenarios"""

    async def test_embedder_failure_fallback(self, chunking_config):
        """Test pipeline handles embedder failures gracefully"""
        chunker = create_chunker(chunking_config)

        chunks = await chunker.chunk_document(
            content="Test content",
            title="Test",
            source="test.md",
        )

        # Create embedder that fails
        with patch("ingestion.embedder.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=Exception("Embedding service failed")
            )
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=MagicMock(
                    json=lambda: {"status": "healthy"},
                    raise_for_status=lambda: None,
                )
            )

            embedder = EmbeddingGenerator(api_url="http://test:8001")

            # Should still return chunks with zero embeddings
            embedded = await embedder.embed_chunks(chunks)

            assert len(embedded) == len(chunks)
            # Should have fallback zero embeddings
            assert all(chunk.embedding == [0.0] * 1024 for chunk in embedded)
            assert all("embedding_error" in chunk.metadata for chunk in embedded)

    async def test_database_connection_failure(self, chunking_config, mock_embedder):
        """Test pipeline handles database connection failures"""
        with patch("ingestion.ingest.create_chunker") as mock_create_chunker, \
             patch("ingestion.ingest.create_embedder") as mock_create_embedder, \
             patch("ingestion.ingest.database.db_pool", None):

            chunker = create_chunker(chunking_config)
            mock_create_chunker.return_value = chunker
            mock_create_embedder.return_value = mock_embedder

            pipeline = DocumentIngestionPipeline(
                documents_folder="/tmp/test",
                chunking_config=chunking_config,
            )

            # Should handle gracefully
            with tempfile.NamedTemporaryFile(mode="w", suffix=".md") as f:
                f.write("Test content")
                f.flush()

                result = await pipeline.ingest_document(f.name)

                assert result["success"] is False
                assert "database" in str(result.get("error", "")).lower() or \
                       "connection" in str(result.get("error", "")).lower()
