"""
Shared pytest fixtures for rag-app tests
"""

import pytest
from unittest.mock import MagicMock, AsyncMock

from ingestion.chunker import ChunkingConfig, DocumentChunk
from ingestion.embedder import EmbeddingGenerator


@pytest.fixture
def chunking_config():
    """Create default chunking configuration for testing"""
    return ChunkingConfig(
        chunk_size=500,
        chunk_overlap=100,
        use_semantic_splitting=False,  # Use simple chunker for tests
    )


@pytest.fixture
def sample_chunks():
    """Create sample document chunks"""
    return [
        DocumentChunk(
            content=f"Test chunk {i} with some content",
            index=i,
            start_char=i * 30,
            end_char=(i + 1) * 30,
            metadata={"title": "Test", "source": "test.md"},
            token_count=7,
        )
        for i in range(3)
    ]


@pytest.fixture
def mock_embedder():
    """Create mock embedder"""
    embedder = MagicMock(spec=EmbeddingGenerator)
    embedder.check_health = AsyncMock(return_value=True)
    embedder.generate_embedding = AsyncMock(return_value=[0.1] * 1024)
    embedder.generate_embeddings_batch = AsyncMock(
        return_value=[[0.1] * 1024, [0.2] * 1024, [0.3] * 1024]
    )
    embedder.get_embedding_dimension = MagicMock(return_value=1024)
    return embedder


@pytest.fixture
def mock_db_conn():
    """Create mock database connection"""
    conn = AsyncMock()
    conn.execute = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchrow = AsyncMock(return_value=None)
    return conn


@pytest.fixture
def sample_document_content():
    """Sample document content for testing"""
    return """
# Test Document

## Introduction
This is a sample document for testing purposes.

## Main Content
The document contains multiple paragraphs with relevant information.
Each section adds value to the overall understanding.

### Subsection
Detailed information in subsections.

## Conclusion
Final summary and closing thoughts.
    """.strip()
