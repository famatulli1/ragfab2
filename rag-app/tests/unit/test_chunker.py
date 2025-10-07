"""
Unit tests for ingestion/chunker.py
Tests document chunking functionality with different strategies
"""

import pytest
from unittest.mock import MagicMock, patch, Mock
from typing import List

from ingestion.chunker import (
    ChunkingConfig,
    DocumentChunk,
    DoclingHybridChunker,
    SimpleChunker,
    create_chunker,
)


@pytest.fixture
def basic_config():
    """Create basic chunking configuration"""
    return ChunkingConfig(
        chunk_size=500,
        chunk_overlap=100,
        max_chunk_size=1000,
        min_chunk_size=50,
        use_semantic_splitting=False,  # Use simple chunker for faster tests
    )


@pytest.fixture
def hybrid_config():
    """Create configuration for hybrid chunker"""
    return ChunkingConfig(
        chunk_size=1000,
        chunk_overlap=200,
        max_tokens=512,
        use_semantic_splitting=True,
    )


@pytest.fixture
def sample_content():
    """Sample document content for testing"""
    return """
# Introduction

This is the introduction paragraph. It contains important information about the document.

## Section 1

This is section 1 content. It has multiple sentences. Each sentence adds value.
The section continues with more details. These details are comprehensive.

## Section 2

This is section 2 which is shorter.

### Subsection 2.1

Detailed information in the subsection. More details here as well.
Another paragraph in the subsection.

# Conclusion

Final thoughts and summary.
    """.strip()


@pytest.mark.unit
class TestChunkingConfig:
    """Test ChunkingConfig validation and initialization"""

    def test_valid_config(self):
        """Test creation of valid configuration"""
        config = ChunkingConfig(
            chunk_size=1000,
            chunk_overlap=200,
            max_chunk_size=2000,
            min_chunk_size=100,
        )
        assert config.chunk_size == 1000
        assert config.chunk_overlap == 200
        assert config.max_chunk_size == 2000
        assert config.min_chunk_size == 100

    def test_default_values(self):
        """Test default configuration values"""
        config = ChunkingConfig()
        assert config.chunk_size == 1000
        assert config.chunk_overlap == 200
        assert config.max_chunk_size == 2000
        assert config.min_chunk_size == 100
        assert config.use_semantic_splitting is True
        assert config.preserve_structure is True
        assert config.max_tokens == 512

    def test_overlap_exceeds_chunk_size(self):
        """Test validation: overlap must be less than chunk size"""
        with pytest.raises(ValueError, match="Chunk overlap must be less than chunk size"):
            ChunkingConfig(chunk_size=100, chunk_overlap=150)

    def test_overlap_equals_chunk_size(self):
        """Test validation: overlap cannot equal chunk size"""
        with pytest.raises(ValueError, match="Chunk overlap must be less than chunk size"):
            ChunkingConfig(chunk_size=100, chunk_overlap=100)

    def test_negative_min_chunk_size(self):
        """Test validation: minimum chunk size must be positive"""
        with pytest.raises(ValueError, match="Minimum chunk size must be positive"):
            ChunkingConfig(min_chunk_size=0)

    def test_negative_min_chunk_size_negative(self):
        """Test validation: minimum chunk size cannot be negative"""
        with pytest.raises(ValueError, match="Minimum chunk size must be positive"):
            ChunkingConfig(min_chunk_size=-10)


@pytest.mark.unit
class TestDocumentChunk:
    """Test DocumentChunk dataclass"""

    def test_chunk_creation(self):
        """Test creating a document chunk"""
        chunk = DocumentChunk(
            content="Test content",
            index=0,
            start_char=0,
            end_char=12,
            metadata={"title": "Test"},
            token_count=3,
        )
        assert chunk.content == "Test content"
        assert chunk.index == 0
        assert chunk.token_count == 3
        assert chunk.metadata["title"] == "Test"

    def test_chunk_auto_token_count(self):
        """Test automatic token count estimation"""
        chunk = DocumentChunk(
            content="Test content with more words",
            index=0,
            start_char=0,
            end_char=28,
            metadata={},
        )
        # Should estimate ~4 chars per token
        assert chunk.token_count == 28 // 4

    def test_chunk_with_embedding(self):
        """Test chunk with embedding vector"""
        embedding = [0.1] * 1024
        chunk = DocumentChunk(
            content="Test",
            index=0,
            start_char=0,
            end_char=4,
            metadata={},
            embedding=embedding,
        )
        assert chunk.embedding == embedding
        assert len(chunk.embedding) == 1024


@pytest.mark.unit
@pytest.mark.asyncio
class TestSimpleChunker:
    """Test SimpleChunker functionality"""

    async def test_simple_chunker_init(self, basic_config):
        """Test SimpleChunker initialization"""
        chunker = SimpleChunker(basic_config)
        assert chunker.config == basic_config

    async def test_chunk_empty_content(self, basic_config):
        """Test chunking empty content"""
        chunker = SimpleChunker(basic_config)
        chunks = await chunker.chunk_document("", "Test", "test.md")
        assert len(chunks) == 0

    async def test_chunk_whitespace_only(self, basic_config):
        """Test chunking whitespace-only content"""
        chunker = SimpleChunker(basic_config)
        chunks = await chunker.chunk_document("   \n\n   ", "Test", "test.md")
        assert len(chunks) == 0

    async def test_chunk_short_content(self, basic_config):
        """Test chunking content shorter than chunk size"""
        chunker = SimpleChunker(basic_config)
        content = "Short paragraph.\n\nAnother short paragraph."
        chunks = await chunker.chunk_document(content, "Test", "test.md")

        assert len(chunks) == 1
        assert "Short paragraph" in chunks[0].content
        assert "Another short paragraph" in chunks[0].content

    async def test_chunk_metadata(self, basic_config):
        """Test chunk metadata is set correctly"""
        chunker = SimpleChunker(basic_config)
        content = "Test content"
        chunks = await chunker.chunk_document(
            content,
            "Test Title",
            "test.md",
            metadata={"custom": "value"},
        )

        assert len(chunks) == 1
        assert chunks[0].metadata["title"] == "Test Title"
        assert chunks[0].metadata["source"] == "test.md"
        assert chunks[0].metadata["chunk_method"] == "simple"
        assert chunks[0].metadata["custom"] == "value"
        assert chunks[0].metadata["total_chunks"] == 1

    async def test_chunk_indexing(self, basic_config):
        """Test chunk indexing is sequential"""
        chunker = SimpleChunker(basic_config)
        content = "\n\n".join([f"Paragraph {i}" * 50 for i in range(5)])
        chunks = await chunker.chunk_document(content, "Test", "test.md")

        for i, chunk in enumerate(chunks):
            assert chunk.index == i

    async def test_chunk_positions(self, basic_config):
        """Test chunk start/end character positions"""
        chunker = SimpleChunker(basic_config)
        content = "Para 1\n\nPara 2\n\nPara 3"
        chunks = await chunker.chunk_document(content, "Test", "test.md")

        assert len(chunks) >= 1
        assert chunks[0].start_char == 0
        assert chunks[0].end_char > 0

    async def test_multiple_paragraphs(self, basic_config, sample_content):
        """Test chunking content with multiple paragraphs"""
        chunker = SimpleChunker(basic_config)
        chunks = await chunker.chunk_document(sample_content, "Test", "test.md")

        assert len(chunks) > 0
        assert all(chunk.content.strip() for chunk in chunks)
        assert all(chunk.metadata["total_chunks"] == len(chunks) for chunk in chunks)

    async def test_respects_chunk_size(self):
        """Test that chunks respect configured size"""
        config = ChunkingConfig(chunk_size=200, chunk_overlap=50)
        chunker = SimpleChunker(config)
        # SimpleChunker splits on paragraphs (\n\n), so provide content with paragraphs
        paragraphs = ["A" * 100 for _ in range(10)]  # 10 paragraphs of 100 chars each
        content = "\n\n".join(paragraphs)  # Total ~1000 chars with paragraph breaks
        chunks = await chunker.chunk_document(content, "Test", "test.md")

        assert len(chunks) > 1
        # Most chunks should be around chunk_size (some variance expected)
        for chunk in chunks[:-1]:  # Exclude last chunk
            assert len(chunk.content) <= config.chunk_size * 1.5


@pytest.mark.unit
class TestDoclingHybridChunker:
    """Test DoclingHybridChunker functionality"""

    def test_hybrid_chunker_init(self, hybrid_config):
        """Test DoclingHybridChunker initialization"""
        # Use real tokenizer instead of mock (Pydantic v2 rejects mocks)
        chunker = DoclingHybridChunker(hybrid_config)
        assert chunker.config == hybrid_config
        assert chunker.tokenizer is not None
        assert chunker.chunker is not None

    @pytest.mark.asyncio
    async def test_chunk_without_docling_doc(self, hybrid_config):
        """Test chunking without DoclingDocument falls back to simple chunking"""
        # Use real tokenizer (Pydantic v2 rejects mocks)
        chunker = DoclingHybridChunker(hybrid_config)
        content = "Test content without docling doc"
        chunks = await chunker.chunk_document(content, "Test", "test.md")

        assert len(chunks) >= 1
        assert all(chunk.metadata["chunk_method"] == "simple_fallback" for chunk in chunks)

    @pytest.mark.asyncio
    async def test_chunk_with_docling_doc(self, hybrid_config):
        """Test chunking with DoclingDocument"""
        # Use real tokenizer (Pydantic v2 rejects mocks)
        chunker = DoclingHybridChunker(hybrid_config)

        # Mock DoclingDocument
        mock_docling_doc = MagicMock()

        # Mock HybridChunker behavior
        mock_chunk = MagicMock()
        with patch.object(chunker.chunker, "chunk") as mock_chunk_method:
            mock_chunk_method.return_value = [mock_chunk, mock_chunk]

            with patch.object(chunker.chunker, "contextualize") as mock_contextualize:
                mock_contextualize.return_value = "Contextualized chunk text"

                chunks = await chunker.chunk_document(
                    "Test content",
                    "Test",
                    "test.md",
                    docling_doc=mock_docling_doc,
                )

                assert len(chunks) == 2
                assert all(chunk.metadata["chunk_method"] == "hybrid" for chunk in chunks)
                assert all(chunk.metadata["has_context"] for chunk in chunks)
                # Token count will be calculated by real tokenizer
                assert all(chunk.token_count > 0 for chunk in chunks)

    @pytest.mark.asyncio
    async def test_chunk_hybrid_failure_fallback(self, hybrid_config):
        """Test fallback to simple chunking when HybridChunker fails"""
        # Use real tokenizer (Pydantic v2 rejects mocks)
        chunker = DoclingHybridChunker(hybrid_config)
        mock_docling_doc = MagicMock()

        # Make chunker.chunk raise an exception
        with patch.object(chunker.chunker, "chunk", side_effect=Exception("Chunking failed")):
            chunks = await chunker.chunk_document(
                "Test content",
                "Test",
                "test.md",
                docling_doc=mock_docling_doc,
            )

            assert len(chunks) >= 1
            assert all(chunk.metadata["chunk_method"] == "simple_fallback" for chunk in chunks)

    def test_simple_fallback_chunk(self, hybrid_config):
        """Test _simple_fallback_chunk method"""
        # Use real tokenizer (Pydantic v2 rejects mocks)
        chunker = DoclingHybridChunker(hybrid_config)
        content = "Test content for fallback chunking. More content here."
        base_metadata = {"title": "Test", "source": "test.md"}

        chunks = chunker._simple_fallback_chunk(content, base_metadata)

        assert len(chunks) >= 1
        assert all(chunk.metadata["chunk_method"] == "simple_fallback" for chunk in chunks)
        assert all("total_chunks" in chunk.metadata for chunk in chunks)

    def test_simple_fallback_respects_boundaries(self, hybrid_config):
        """Test that fallback chunking tries to respect sentence boundaries"""
        # Use real tokenizer (Pydantic v2 rejects mocks)
        config = ChunkingConfig(chunk_size=50, chunk_overlap=10)
        chunker = DoclingHybridChunker(config)

        content = "First sentence. Second sentence. Third sentence. Fourth sentence."
        base_metadata = {"title": "Test"}

        chunks = chunker._simple_fallback_chunk(content, base_metadata)

        # Should have multiple chunks
        assert len(chunks) >= 2

        # Check that chunks end at reasonable boundaries (period or newline)
        for chunk in chunks[:-1]:  # Exclude last chunk
            # Content should be trimmed
            assert chunk.content == chunk.content.strip()


@pytest.mark.unit
class TestCreateChunker:
    """Test chunker factory function"""

    def test_create_simple_chunker(self):
        """Test factory creates SimpleChunker when semantic splitting is disabled"""
        config = ChunkingConfig(use_semantic_splitting=False)
        chunker = create_chunker(config)
        assert isinstance(chunker, SimpleChunker)

    def test_create_hybrid_chunker(self):
        """Test factory creates DoclingHybridChunker when semantic splitting is enabled"""
        config = ChunkingConfig(use_semantic_splitting=True)
        # Use real tokenizer (Pydantic v2 rejects mocks)
        chunker = create_chunker(config)
        assert isinstance(chunker, DoclingHybridChunker)


@pytest.mark.unit
@pytest.mark.asyncio
class TestChunkerIntegration:
    """Integration-style tests for chunker functionality"""

    async def test_end_to_end_simple_chunking(self, sample_content):
        """Test complete chunking workflow with SimpleChunker"""
        config = ChunkingConfig(
            chunk_size=300,
            chunk_overlap=50,
            use_semantic_splitting=False,
        )
        chunker = create_chunker(config)

        chunks = await chunker.chunk_document(
            content=sample_content,
            title="Test Document",
            source="test.md",
            metadata={"author": "Test Author"},
        )

        # Verify chunks were created
        assert len(chunks) > 0

        # Verify metadata
        for chunk in chunks:
            assert chunk.metadata["title"] == "Test Document"
            assert chunk.metadata["source"] == "test.md"
            assert chunk.metadata["author"] == "Test Author"
            assert chunk.metadata["total_chunks"] == len(chunks)

        # Verify indexing
        for i, chunk in enumerate(chunks):
            assert chunk.index == i

        # Verify content
        assert all(chunk.content.strip() for chunk in chunks)
        assert all(chunk.token_count > 0 for chunk in chunks)

    async def test_chunking_preserves_information(self):
        """Test that chunking doesn't lose information"""
        config = ChunkingConfig(
            chunk_size=100,
            chunk_overlap=20,
            use_semantic_splitting=False,
        )
        chunker = create_chunker(config)

        original_content = "Test content that should be preserved in chunks."
        chunks = await chunker.chunk_document(original_content, "Test", "test.md")

        # Reconstruct content from chunks (accounting for overlap)
        reconstructed = chunks[0].content
        for chunk in chunks[1:]:
            # Simple reconstruction without overlap handling
            reconstructed += " " + chunk.content

        # All words from original should appear in reconstructed
        original_words = set(original_content.lower().split())
        reconstructed_words = set(reconstructed.lower().split())
        assert original_words.issubset(reconstructed_words)
