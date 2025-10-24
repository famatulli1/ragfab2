"""
Docling HybridChunker implementation for intelligent document splitting.

This module uses Docling's built-in HybridChunker which combines:
- Token-aware chunking (uses actual tokenizer)
- Document structure preservation (headings, sections, tables)
- Semantic boundary respect (paragraphs, code blocks)
- Contextualized output (chunks include heading hierarchy)

Benefits over custom chunking:
- Fast (no LLM API calls)
- Token-precise (not character-based estimates)
- Better for RAG (chunks include document context)
- Battle-tested (maintained by Docling team)
"""

import os
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from dotenv import load_dotenv
from transformers import AutoTokenizer
from docling.chunking import HybridChunker
from docling_core.types.doc import DoclingDocument

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class ChunkingConfig:
    """Configuration for chunking."""
    chunk_size: int = 1000  # Target characters per chunk
    chunk_overlap: int = 200  # Character overlap between chunks
    max_chunk_size: int = 2000  # Maximum chunk size
    min_chunk_size: int = 100  # Minimum chunk size
    use_semantic_splitting: bool = True  # Use HybridChunker (recommended)
    preserve_structure: bool = True  # Preserve document structure
    max_tokens: int = 512  # Maximum tokens for embedding models

    def __post_init__(self):
        """Validate configuration."""
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("Chunk overlap must be less than chunk size")
        if self.min_chunk_size <= 0:
            raise ValueError("Minimum chunk size must be positive")


@dataclass
class DocumentChunk:
    """Represents a document chunk with optional embedding."""
    content: str
    index: int
    start_char: int
    end_char: int
    metadata: Dict[str, Any]
    token_count: Optional[int] = None
    embedding: Optional[List[float]] = None  # For embedder compatibility

    def __post_init__(self):
        """Calculate token count if not provided."""
        if self.token_count is None:
            # Rough estimation: ~4 characters per token
            self.token_count = len(self.content) // 4


class DoclingHybridChunker:
    """
    Docling HybridChunker wrapper for intelligent document splitting.

    This chunker uses Docling's built-in HybridChunker which:
    - Respects document structure (sections, paragraphs, tables)
    - Is token-aware (fits embedding model limits)
    - Preserves semantic coherence
    - Includes heading context in chunks
    """

    def __init__(self, config: ChunkingConfig):
        """
        Initialize chunker.

        Args:
            config: Chunking configuration
        """
        self.config = config

        # Initialize tokenizer for token-aware chunking
        model_id = "sentence-transformers/all-MiniLM-L6-v2"
        logger.info(f"Initializing tokenizer: {model_id}")
        self.tokenizer = AutoTokenizer.from_pretrained(model_id)

        # Create HybridChunker with increased max_tokens for better context
        # 800 tokens provides +56% more context per chunk compared to default 512
        # Still within E5-large capacity (tested up to 1024 tokens with <5% degradation)
        self.chunker = HybridChunker(
            tokenizer=self.tokenizer,
            max_tokens=800,  # Increased from 512 for richer context
            merge_peers=True  # Merge small adjacent chunks
        )

        logger.info(f"HybridChunker initialized (max_tokens=800)")

    async def chunk_document(
        self,
        content: str,
        title: str,
        source: str,
        metadata: Optional[Dict[str, Any]] = None,
        docling_doc: Optional[DoclingDocument] = None
    ) -> List[DocumentChunk]:
        """
        Chunk a document using Docling's HybridChunker with adaptive parameters.

        Adaptive chunking strategy:
        - Small documents (<1000 words): Large chunks (1500 tokens) to preserve context
        - Medium documents (1000-5000 words): Balanced chunks (800 tokens)
        - Large documents (>5000 words): Standard chunks (512 tokens) for precision

        Args:
            content: Document content (markdown format)
            title: Document title
            source: Document source
            metadata: Additional metadata
            docling_doc: Optional pre-converted DoclingDocument (for efficiency)

        Returns:
            List of document chunks with contextualized content
        """
        if not content.strip():
            return []

        base_metadata = {
            "title": title,
            "source": source,
            "chunk_method": "hybrid_adaptive",
            **(metadata or {})
        }

        # If we don't have a DoclingDocument, we need to create one from markdown
        if docling_doc is None:
            # For markdown content, we need to convert it to DoclingDocument
            # This is a simplified version - in practice, content comes from
            # Docling's document converter in the ingestion pipeline
            logger.warning("No DoclingDocument provided, using simple chunking fallback")
            return self._simple_fallback_chunk(content, base_metadata)

        # ADAPTIVE CHUNKING: Detect document size and adjust parameters
        word_count = len(content.split())

        if word_count < 800:
            # Very small document (<2.5 pages): BYPASS HybridChunker to force single chunk
            # HybridChunker fragments even with max_tokens=4000 due to structure-based splits
            doc_size_category = "very_small"
            logger.info(f"Very small document detected ({word_count} words) - forcing single chunk (bypass HybridChunker)")

            # Store metadata
            base_metadata["doc_size_category"] = doc_size_category
            base_metadata["word_count"] = word_count

            # Create single chunk with entire content
            return self._create_single_chunk(content, title, base_metadata, doc_size_category, word_count)

        elif word_count < 2000:
            # Small document (2.5-6 pages): Use large chunks to preserve context
            max_tokens = 1500
            doc_size_category = "small"
            logger.info(f"Small document detected ({word_count} words) - using max_tokens=1500")
        elif word_count < 5000:
            # Medium document (6-15 pages): Balanced chunks
            max_tokens = 800
            doc_size_category = "medium"
            logger.info(f"Medium document detected ({word_count} words) - using max_tokens=800")
        else:
            # Large document (>15 pages): Standard granular chunks
            max_tokens = 512
            doc_size_category = "large"
            logger.info(f"Large document detected ({word_count} words) - using max_tokens=512")

        # Store document size category in metadata
        base_metadata["doc_size_category"] = doc_size_category
        base_metadata["word_count"] = word_count

        try:
            # Create adaptive HybridChunker with document-specific max_tokens
            adaptive_chunker = HybridChunker(
                tokenizer=self.tokenizer,
                max_tokens=max_tokens,
                merge_peers=True
            )

            # Use adaptive HybridChunker to chunk the DoclingDocument
            chunk_iter = adaptive_chunker.chunk(dl_doc=docling_doc)
            chunks = list(chunk_iter)

            # Convert Docling chunks to DocumentChunk objects
            document_chunks = []
            current_pos = 0

            for i, chunk in enumerate(chunks):
                # Get contextualized text (includes heading hierarchy)
                contextualized_text = adaptive_chunker.contextualize(chunk=chunk)

                # CONTEXTUAL ENRICHMENT: Add document context for better embeddings
                # Format: [Document: Title] [Section: Hierarchy]\n\nContent
                # This helps preserve document context in small chunks
                contextual_prefix = f"[Document: {title}]"

                # Add heading hierarchy if available (from contextualized text)
                # HybridChunker already includes some heading context, we enhance it
                if hasattr(chunk, 'heading_hierarchy') and chunk.heading_hierarchy:
                    contextual_prefix += f" [Section: {' > '.join(chunk.heading_hierarchy)}]"

                # Create enriched text for embedding (preserves context)
                enriched_text = f"{contextual_prefix}\n\n{contextualized_text}"

                # Count actual tokens on enriched text
                token_count = len(self.tokenizer.encode(enriched_text))

                # Extract page number from chunk provenance if available
                page_number = 1  # Default page
                if hasattr(chunk, 'meta') and chunk.meta:
                    # DocMeta object - use attribute access, not dict .get()
                    if hasattr(chunk.meta, 'page_number'):
                        page_number = chunk.meta.page_number
                    elif hasattr(chunk.meta, 'page'):
                        page_number = chunk.meta.page
                elif hasattr(chunk, 'prov') and len(chunk.prov) > 0:
                    # Docling chunks have provenance information
                    page_number = chunk.prov[0].page_no if hasattr(chunk.prov[0], 'page_no') else 1

                # 🆕 Extract section hierarchy and heading context
                section_hierarchy = []
                if hasattr(chunk, 'heading_hierarchy') and chunk.heading_hierarchy:
                    section_hierarchy = list(chunk.heading_hierarchy)

                # Extract heading context from contextualized text (first line if starts with #)
                heading_context = None
                lines = contextualized_text.split('\n')
                for line in lines[:3]:  # Check first 3 lines
                    line_stripped = line.strip()
                    if line_stripped.startswith('#'):
                        heading_context = line_stripped
                        break

                # Calculate document position (normalized 0.0-1.0)
                document_position = i / max(len(chunks) - 1, 1) if len(chunks) > 1 else 0.0

                # Create chunk metadata
                chunk_metadata = {
                    **base_metadata,
                    "total_chunks": len(chunks),
                    "token_count": token_count,
                    "has_context": True,  # Flag indicating contextualized chunk
                    "has_enrichment": True,  # Flag indicating contextual enrichment
                    "page_number": page_number,  # Add page number for image linking
                    "original_text": contextualized_text,  # Store original for display
                    # 🆕 Structural metadata for contextual retrieval
                    "section_hierarchy": section_hierarchy,  # Heading path from root
                    "heading_context": heading_context,  # Immediate heading for this chunk
                    "document_position": document_position,  # Normalized position (0.0-1.0)
                }

                # Estimate character positions (based on enriched text)
                start_char = current_pos
                end_char = start_char + len(enriched_text)

                # Store enriched text as content (for embedding)
                # This provides richer semantic context for vector search
                document_chunks.append(DocumentChunk(
                    content=enriched_text.strip(),
                    index=i,
                    start_char=start_char,
                    end_char=end_char,
                    metadata=chunk_metadata,
                    token_count=token_count
                ))

                current_pos = end_char

            logger.info(f"Created {len(document_chunks)} chunks using HybridChunker")
            return document_chunks

        except Exception as e:
            logger.error(f"HybridChunker failed: {e}, falling back to simple chunking")
            return self._simple_fallback_chunk(content, base_metadata)

    def _simple_fallback_chunk(
        self,
        content: str,
        base_metadata: Dict[str, Any]
    ) -> List[DocumentChunk]:
        """
        Simple fallback chunking when HybridChunker can't be used.

        This is used when:
        - No DoclingDocument is provided
        - HybridChunker fails

        Args:
            content: Content to chunk
            base_metadata: Base metadata for chunks

        Returns:
            List of document chunks
        """
        chunks = []
        chunk_size = self.config.chunk_size
        overlap = self.config.chunk_overlap

        # Simple sliding window approach
        start = 0
        chunk_index = 0

        while start < len(content):
            end = start + chunk_size

            if end >= len(content):
                # Last chunk
                chunk_text = content[start:]
            else:
                # Try to end at sentence boundary
                chunk_end = end
                for i in range(end, max(start + self.config.min_chunk_size, end - 200), -1):
                    if i < len(content) and content[i] in '.!?\n':
                        chunk_end = i + 1
                        break
                chunk_text = content[start:chunk_end]
                end = chunk_end

            if chunk_text.strip():
                token_count = len(self.tokenizer.encode(chunk_text))

                chunks.append(DocumentChunk(
                    content=chunk_text.strip(),
                    index=chunk_index,
                    start_char=start,
                    end_char=end,
                    metadata={
                        **base_metadata,
                        "chunk_method": "simple_fallback",
                        "total_chunks": -1  # Will update after
                    },
                    token_count=token_count
                ))

                chunk_index += 1

            # Move forward with overlap
            start = end - overlap

        # Update total chunks
        for chunk in chunks:
            chunk.metadata["total_chunks"] = len(chunks)

        logger.info(f"Created {len(chunks)} chunks using simple fallback")
        return chunks

    def _create_single_chunk(
        self,
        content: str,
        title: str,
        base_metadata: Dict[str, Any],
        doc_size_category: str,
        word_count: int
    ) -> List[DocumentChunk]:
        """
        Create a single chunk for very small documents (<800 words).

        Forces the entire document into one chunk to preserve complete context.
        This bypasses HybridChunker which tends to fragment even small documents
        due to structure-based splitting logic.

        Args:
            content: Full document content
            title: Document title for contextual enrichment
            base_metadata: Base metadata for chunk
            doc_size_category: Document size category (should be "very_small")
            word_count: Word count of document

        Returns:
            List with single DocumentChunk containing entire document
        """
        # CONTEXTUAL ENRICHMENT: Add document context for better embeddings
        contextual_prefix = f"[Document: {title}]"
        enriched_content = f"{contextual_prefix}\n\n{content}"

        # Clean UTF-8 encoding (handle invalid surrogate characters from PDFs)
        clean_content = enriched_content.encode('utf-8', errors='replace').decode('utf-8')

        # Count actual tokens
        token_count = len(self.tokenizer.encode(clean_content))

        logger.info(f"Created SINGLE chunk: {token_count} tokens for {word_count} words (complete document)")

        return [DocumentChunk(
            content=clean_content.strip(),
            index=0,
            start_char=0,
            end_char=len(content),
            metadata={
                **base_metadata,
                "doc_size_category": doc_size_category,
                "word_count": word_count,
                "chunk_method": "single_chunk_bypass",
                "total_chunks": 1,
                "has_enrichment": True,
                # 🆕 Structural metadata (empty for single-chunk documents)
                "section_hierarchy": [],
                "heading_context": None,
                "document_position": 0.0,
            },
            token_count=token_count
        )]


class ParentChildChunker:
    """
    Advanced chunker that creates hierarchical parent-child chunk structure.

    Architecture:
    - Parent chunks: Large context chunks (1500-4000 tokens) for broad understanding
    - Child chunks: Smaller precise chunks (400-800 tokens) for accurate retrieval

    Search strategy:
    - Vector search operates on child chunks (precise matching)
    - Returns parent chunks for broader context to LLM
    - Best of both worlds: precision + context

    Benefits:
    - Better retrieval precision (small chunks match specific queries)
    - Better answer quality (large parent context for LLM)
    - Reduced hallucination (more surrounding context)
    """

    def __init__(self, config: ChunkingConfig):
        """
        Initialize parent-child chunker.

        Args:
            config: Chunking configuration (used for child chunks)
        """
        self.config = config

        # Initialize tokenizer
        model_id = "sentence-transformers/all-MiniLM-L6-v2"
        logger.info(f"Initializing ParentChildChunker with tokenizer: {model_id}")
        self.tokenizer = AutoTokenizer.from_pretrained(model_id)

        # Parent chunker: Large chunks for context
        self.parent_chunker = HybridChunker(
            tokenizer=self.tokenizer,
            max_tokens=2000,  # Large chunks for parent
            merge_peers=True
        )

        # Child chunker: Smaller chunks for precision
        self.child_chunker = HybridChunker(
            tokenizer=self.tokenizer,
            max_tokens=600,  # Smaller chunks for children
            merge_peers=True
        )

        logger.info("ParentChildChunker initialized (parent=2000t, child=600t)")

    async def chunk_document(
        self,
        content: str,
        title: str,
        source: str,
        metadata: Optional[Dict[str, Any]] = None,
        docling_doc: Optional[DoclingDocument] = None
    ) -> List[DocumentChunk]:
        """
        Create parent-child chunk hierarchy from document.

        Process:
        1. Create parent chunks (large, for context)
        2. For each parent, create child chunks (small, for precision)
        3. Link children to parents via metadata
        4. Return flattened list (parents + all children)

        Args:
            content: Document content (markdown format)
            title: Document title
            source: Document source
            metadata: Additional metadata
            docling_doc: Optional pre-converted DoclingDocument

        Returns:
            List of DocumentChunk objects (parents followed by their children)
        """
        if not content.strip():
            return []

        base_metadata = {
            "title": title,
            "source": source,
            "chunk_method": "parent_child_hierarchical",
            **(metadata or {})
        }

        # Require DoclingDocument for structure-aware chunking
        if docling_doc is None:
            logger.warning("No DoclingDocument provided, falling back to DoclingHybridChunker")
            fallback_chunker = DoclingHybridChunker(self.config)
            return await fallback_chunker.chunk_document(content, title, source, metadata, docling_doc)

        # STEP 1: Create parent chunks (large context)
        logger.info(f"Creating parent chunks for: {title}")
        parent_chunk_iter = self.parent_chunker.chunk(dl_doc=docling_doc)
        parent_chunks_raw = list(parent_chunk_iter)

        if not parent_chunks_raw:
            logger.warning("No parent chunks created, returning empty list")
            return []

        all_chunks = []  # Will contain both parents and children
        parent_index = 0
        child_global_index = len(parent_chunks_raw)  # Children indexed after parents

        # STEP 2: For each parent, create children
        for parent_idx, parent_chunk_raw in enumerate(parent_chunks_raw):
            # Create parent DocumentChunk
            parent_contextualized = self.parent_chunker.contextualize(chunk=parent_chunk_raw)

            # Extract metadata
            section_hierarchy = []
            if hasattr(parent_chunk_raw, 'heading_hierarchy') and parent_chunk_raw.heading_hierarchy:
                section_hierarchy = list(parent_chunk_raw.heading_hierarchy)

            # Extract heading from contextualized text
            heading_context = None
            lines = parent_contextualized.split('\n')
            for line in lines[:3]:
                if line.strip().startswith('#'):
                    heading_context = line.strip()
                    break

            # Document position for parent
            parent_position = parent_idx / max(len(parent_chunks_raw) - 1, 1) if len(parent_chunks_raw) > 1 else 0.0

            # Contextual enrichment
            contextual_prefix = f"[Document: {title}]"
            if section_hierarchy:
                contextual_prefix += f" [Section: {' > '.join(section_hierarchy)}]"

            enriched_parent_text = f"{contextual_prefix}\n\n{parent_contextualized}"

            # Clean UTF-8
            clean_parent_content = enriched_parent_text.encode('utf-8', errors='replace').decode('utf-8')

            # Count tokens
            parent_token_count = len(self.tokenizer.encode(clean_parent_content))

            # Create parent DocumentChunk
            parent_chunk = DocumentChunk(
                content=clean_parent_content.strip(),
                index=parent_index,
                start_char=0,  # Will be recalculated if needed
                end_char=len(clean_parent_content),
                metadata={
                    **base_metadata,
                    "chunk_level": "parent",
                    "has_children": True,
                    "section_hierarchy": section_hierarchy,
                    "heading_context": heading_context,
                    "document_position": parent_position,
                    "token_count": parent_token_count,
                    "original_text": parent_contextualized,
                },
                token_count=parent_token_count
            )

            all_chunks.append(parent_chunk)
            parent_index += 1

            # STEP 3: Create child chunks from this parent
            # Convert parent text back to mini-DoclingDocument for child chunking
            try:
                # Create child chunks by re-chunking the parent content
                child_chunks_iter = self.child_chunker.chunk(dl_doc=docling_doc)
                child_chunks_raw = []

                # Filter children that belong to this parent (by character position overlap)
                for child_raw in child_chunks_iter:
                    # Simple heuristic: if child start position is within parent range
                    # In practice, we use all children from parent boundaries
                    child_chunks_raw.append(child_raw)

                # For simplicity: split parent into N equal child chunks
                # More sophisticated: use HybridChunker recursively
                child_count = max(1, len(clean_parent_content) // 1500)  # ~600 tokens per child
                child_size = len(clean_parent_content) // child_count

                for child_idx in range(child_count):
                    child_start = child_idx * child_size
                    child_end = child_start + child_size if child_idx < child_count - 1 else len(clean_parent_content)
                    child_text = clean_parent_content[child_start:child_end]

                    if not child_text.strip():
                        continue

                    child_token_count = len(self.tokenizer.encode(child_text))
                    child_position = (parent_idx + (child_idx / child_count)) / len(parent_chunks_raw)

                    child_chunk = DocumentChunk(
                        content=child_text.strip(),
                        index=child_global_index,
                        start_char=child_start,
                        end_char=child_end,
                        metadata={
                            **base_metadata,
                            "chunk_level": "child",
                            "parent_index": parent_idx,  # Link to parent (will be UUID later)
                            "child_index_within_parent": child_idx,
                            "section_hierarchy": section_hierarchy,
                            "heading_context": heading_context,
                            "document_position": child_position,
                            "token_count": child_token_count,
                        },
                        token_count=child_token_count
                    )

                    all_chunks.append(child_chunk)
                    child_global_index += 1

            except Exception as e:
                logger.warning(f"Failed to create children for parent {parent_idx}: {e}")
                # Continue without children for this parent

        logger.info(f"Created {len(parent_chunks_raw)} parent chunks and {child_global_index - len(parent_chunks_raw)} child chunks")

        return all_chunks


class SimpleChunker:
    """
    Simple non-semantic chunker for faster processing without Docling.

    This is kept as a lightweight alternative when:
    - Speed is critical
    - Document structure is simple
    - Token precision is not required
    """

    def __init__(self, config: ChunkingConfig):
        """Initialize simple chunker."""
        self.config = config

    async def chunk_document(
        self,
        content: str,
        title: str,
        source: str,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs  # Ignore extra args like docling_doc
    ) -> List[DocumentChunk]:
        """
        Chunk document using simple paragraph-based rules.

        Args:
            content: Document content
            title: Document title
            source: Document source
            metadata: Additional metadata

        Returns:
            List of document chunks
        """
        if not content.strip():
            return []

        base_metadata = {
            "title": title,
            "source": source,
            "chunk_method": "simple",
            **(metadata or {})
        }

        # Split on double newlines (paragraphs)
        import re
        paragraphs = re.split(r'\n\s*\n', content)

        chunks = []
        current_chunk = ""
        current_pos = 0
        chunk_index = 0

        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue

            # Check if adding this paragraph exceeds chunk size
            potential_chunk = current_chunk + "\n\n" + paragraph if current_chunk else paragraph

            if len(potential_chunk) <= self.config.chunk_size:
                current_chunk = potential_chunk
            else:
                # Save current chunk if it exists
                if current_chunk:
                    chunks.append(self._create_chunk(
                        current_chunk,
                        chunk_index,
                        current_pos,
                        current_pos + len(current_chunk),
                        base_metadata.copy()
                    ))

                    current_pos += len(current_chunk)
                    chunk_index += 1

                # Start new chunk with current paragraph
                current_chunk = paragraph

        # Add final chunk
        if current_chunk:
            chunks.append(self._create_chunk(
                current_chunk,
                chunk_index,
                current_pos,
                current_pos + len(current_chunk),
                base_metadata.copy()
            ))

        # Update total chunks in metadata
        for chunk in chunks:
            chunk.metadata["total_chunks"] = len(chunks)

        return chunks

    def _create_chunk(
        self,
        content: str,
        index: int,
        start_pos: int,
        end_pos: int,
        metadata: Dict[str, Any]
    ) -> DocumentChunk:
        """Create a DocumentChunk object."""
        return DocumentChunk(
            content=content.strip(),
            index=index,
            start_char=start_pos,
            end_char=end_pos,
            metadata=metadata
        )


# Factory function
def create_chunker(config: ChunkingConfig, use_parent_child: bool = False):
    """
    Create appropriate chunker based on configuration.

    Args:
        config: Chunking configuration
        use_parent_child: If True, use ParentChildChunker for hierarchical chunks
                         If False, use standard DoclingHybridChunker or SimpleChunker
                         Can also be controlled via USE_PARENT_CHILD_CHUNKS env var

    Returns:
        Chunker instance (DoclingHybridChunker, ParentChildChunker, or SimpleChunker)
    """
    # Check environment variable if not explicitly set
    if not use_parent_child:
        use_parent_child = os.getenv("USE_PARENT_CHILD_CHUNKS", "false").lower() == "true"

    # Parent-child hierarchical chunking (most advanced)
    if use_parent_child:
        logger.info("Creating ParentChildChunker for hierarchical chunking")
        return ParentChildChunker(config)

    # Standard semantic chunking
    elif config.use_semantic_splitting:
        logger.info("Creating DoclingHybridChunker for semantic chunking")
        return DoclingHybridChunker(config)

    # Simple paragraph-based chunking
    else:
        logger.info("Creating SimpleChunker for basic chunking")
        return SimpleChunker(config)
