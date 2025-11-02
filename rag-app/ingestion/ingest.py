"""
Main ingestion script for processing markdown documents into vector DB and knowledge graph.
"""

import os
import asyncio
import logging
import json
import glob
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import argparse

import asyncpg
from dotenv import load_dotenv

from .chunker import ChunkingConfig, create_chunker, DocumentChunk
from .embedder import create_embedder
from .image_processor import create_image_processor, ImageMetadata

# Import utilities
try:
    from ..utils.db_utils import initialize_database, close_database, db_pool
    from ..utils.models import IngestionConfig, IngestionResult
except ImportError:
    # For direct execution or testing
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from utils.db_utils import initialize_database, close_database, db_pool
    from utils.models import IngestionConfig, IngestionResult

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class DocumentIngestionPipeline:
    """Pipeline for ingesting documents into vector DB and knowledge graph."""
    
    def __init__(
        self,
        config: IngestionConfig,
        documents_folder: str = "documents",
        clean_before_ingest: bool = True
    ):
        """
        Initialize ingestion pipeline.

        Args:
            config: Ingestion configuration
            documents_folder: Folder containing markdown documents
            clean_before_ingest: Whether to clean existing data before ingestion (default: True)
        """
        self.config = config
        self.documents_folder = documents_folder
        self.clean_before_ingest = clean_before_ingest
        
        # Initialize components
        self.chunker_config = ChunkingConfig(
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
            max_chunk_size=config.max_chunk_size,
            use_semantic_splitting=config.use_semantic_chunking
        )
        
        self.chunker = create_chunker(self.chunker_config)
        self.embedder = create_embedder()
        self.image_processor = create_image_processor()  # None if VLM disabled

        self._initialized = False
    
    async def initialize(self):
        """Initialize database connections."""
        if self._initialized:
            return
        
        logger.info("Initializing ingestion pipeline...")
        
        # Initialize database connections
        await initialize_database()
        
        self._initialized = True
        logger.info("Ingestion pipeline initialized")
    
    async def close(self):
        """Close database connections."""
        if self._initialized:
            await close_database()
            self._initialized = False
    
    async def ingest_documents(
        self,
        progress_callback: Optional[callable] = None
    ) -> List[IngestionResult]:
        """
        Ingest all documents from the documents folder.
        
        Args:
            progress_callback: Optional callback for progress updates
        
        Returns:
            List of ingestion results
        """
        if not self._initialized:
            await self.initialize()
        
        # Clean existing data if requested
        if self.clean_before_ingest:
            await self._clean_databases()
        
        # Find all supported document files
        document_files = self._find_document_files()

        if not document_files:
            logger.warning(f"No supported document files found in {self.documents_folder}")
            return []

        logger.info(f"Found {len(document_files)} document files to process")

        results = []

        for i, file_path in enumerate(document_files):
            try:
                logger.info(f"Processing file {i+1}/{len(document_files)}: {file_path}")

                result = await self._ingest_single_document(file_path)
                results.append(result)

                if progress_callback:
                    progress_callback(i + 1, len(document_files))
                
            except Exception as e:
                logger.error(f"Failed to process {file_path}: {e}")
                results.append(IngestionResult(
                    document_id="",
                    title=os.path.basename(file_path),
                    chunks_created=0,
                    entities_extracted=0,
                    relationships_created=0,
                    processing_time_ms=0,
                    errors=[str(e)]
                ))
        
        # Log summary
        total_chunks = sum(r.chunks_created for r in results)
        total_errors = sum(len(r.errors) for r in results)
        
        logger.info(f"Ingestion complete: {len(results)} documents, {total_chunks} chunks, {total_errors} errors")
        
        return results
    
    async def _ingest_single_document(self, file_path: str) -> IngestionResult:
        """
        Ingest a single document.

        Args:
            file_path: Path to the document file

        Returns:
            Ingestion result
        """
        start_time = datetime.now()

        # Read document (returns tuple: content, docling_doc, images)
        # Images are now extracted BEFORE chunking and enriched into markdown
        document_content, docling_doc, images = await self._read_document(file_path)
        document_title = self._extract_title(document_content, file_path)
        document_source = os.path.relpath(file_path, self.documents_folder)

        # Extract metadata from content
        document_metadata = self._extract_document_metadata(document_content, file_path)

        logger.info(f"Processing document: {document_title}")

        # Chunk the document - pass DoclingDocument for HybridChunker
        chunks = await self.chunker.chunk_document(
            content=document_content,
            title=document_title,
            source=document_source,
            metadata=document_metadata,
            docling_doc=docling_doc  # Pass DoclingDocument for HybridChunker
        )

        if not chunks:
            logger.warning(f"No chunks created for {document_title}")
            return IngestionResult(
                document_id="",
                title=document_title,
                chunks_created=0,
                entities_extracted=0,
                relationships_created=0,
                processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                errors=["No chunks created"]
            )

        logger.info(f"Created {len(chunks)} document chunks")

        # Create synthetic chunks for images to make them searchable
        if images:
            image_chunks = self._create_image_chunks(
                images=images,
                document_title=document_title,
                document_source=document_source
            )
            if image_chunks:
                chunks.extend(image_chunks)
                logger.info(f"✨ Added {len(image_chunks)} synthetic image chunks (total: {len(chunks)})")

        logger.info(f"Final chunk count: {len(chunks)} chunks")
        
        # Entity extraction removed (graph-related functionality)
        entities_extracted = 0
        
        # Generate embeddings
        embedded_chunks = await self.embedder.embed_chunks(chunks)
        logger.info(f"Generated embeddings for {len(embedded_chunks)} chunks")

        # Images were already extracted and injected into markdown during _read_document()
        # The images list already contains metadata from extraction
        logger.info(f"Ready to save document with {len(images)} images")

        # Save to PostgreSQL (including images)
        document_id = await self._save_to_postgres(
            document_title,
            document_source,
            document_content,
            embedded_chunks,
            document_metadata,
            images
        )

        logger.info(f"Saved document to PostgreSQL with ID: {document_id}")
        
        # Knowledge graph functionality removed
        relationships_created = 0
        graph_errors = []
        
        # Calculate processing time
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        return IngestionResult(
            document_id=document_id,
            title=document_title,
            chunks_created=len(chunks),
            entities_extracted=entities_extracted,
            relationships_created=relationships_created,
            processing_time_ms=processing_time,
            errors=graph_errors
        )
    
    def _find_document_files(self) -> List[str]:
        """Find all supported document files in the documents folder."""
        if not os.path.exists(self.documents_folder):
            logger.error(f"Documents folder not found: {self.documents_folder}")
            return []

        # Supported file patterns - Docling + text formats + audio
        patterns = [
            "*.md", "*.markdown", "*.txt",  # Text formats
            "*.pdf",  # PDF
            "*.docx", "*.doc",  # Word
            "*.pptx", "*.ppt",  # PowerPoint
            "*.xlsx", "*.xls",  # Excel
            "*.html", "*.htm",  # HTML
            "*.mp3", "*.wav", "*.m4a", "*.flac",  # Audio formats
        ]
        files = []

        for pattern in patterns:
            # Chercher à la racine du dossier
            files.extend(glob.glob(os.path.join(self.documents_folder, pattern)))
            # Chercher dans les sous-dossiers
            files.extend(glob.glob(os.path.join(self.documents_folder, "**", pattern), recursive=True))

        # Supprimer les doublons et trier
        return sorted(list(set(files)))

    def _create_image_chunks(
        self,
        images: List[ImageMetadata],
        document_title: str,
        document_source: str
    ) -> List[DocumentChunk]:
        """
        Create synthetic chunks for image descriptions and OCR text.
        Each image becomes a searchable chunk in the RAG system.

        Args:
            images: List of ImageMetadata objects with descriptions and OCR
            document_title: Title of the parent document
            document_source: Source path of the parent document

        Returns:
            List of DocumentChunk objects for images
        """
        image_chunks = []

        for idx, image in enumerate(images):
            description = getattr(image, 'description', '') or ''
            ocr_text = getattr(image, 'ocr_text', '') or ''
            page_num = getattr(image, 'page_number', 1)

            if not description and not ocr_text:
                continue  # Skip images with no content

            # Build chunk content with document context for better searchability
            # Extract title keywords for context enrichment
            title_keywords = document_title.replace('+', ' ').replace('_', ' ')

            content_parts = [
                f"[Document: {document_title}]",  # Add document context
                f"[Image {idx+1} depuis la page {page_num}]"
            ]
            if description:
                content_parts.append(f"Description: {description}")
            if ocr_text:
                content_parts.append(f"Texte extrait: {ocr_text}")

            # Add contextual keywords from document title
            content_parts.append(f"Contexte: {title_keywords}")

            chunk_content = "\n".join(content_parts)

            # Estimate token count (approximation if tokenizer not available)
            try:
                token_count = len(self.chunker.tokenizer.encode(chunk_content))
            except:
                token_count = len(chunk_content.split())  # Fallback

            # Create DocumentChunk
            image_chunk = DocumentChunk(
                content=chunk_content,
                index=1000 + idx,  # High index to appear after document chunks
                start_char=0,
                end_char=len(chunk_content),
                token_count=token_count,
                metadata={
                    "title": document_title,
                    "source": document_source,
                    "chunk_method": "synthetic_image",
                    "page_number": page_num,
                    "image_index": idx,
                    "is_image_chunk": True
                }
            )

            image_chunks.append(image_chunk)

        return image_chunks

    async def _read_document(
        self,
        file_path: str,
        image_processor: Optional[Any] = None,
        ocr_engine: Optional[str] = None
    ) -> tuple[str, Optional[Any], List[dict]]:
        """
        Read document content from file - supports multiple formats via Docling.
        Extracts images for VLM analysis (if enabled).

        Args:
            file_path: Path to the document file
            image_processor: Optional ImageProcessor instance (overrides self.image_processor)
                            Allows per-job VLM engine selection
            ocr_engine: Optional OCR engine for Docling ('rapidocr', 'easyocr', 'tesseract')
                       If None, uses environment default or RapidOCR

        Returns:
            Tuple of (markdown_content, docling_document, images)
            docling_document is None for text files and audio files
            images is a list of extracted image metadata
        """
        file_ext = os.path.splitext(file_path)[1].lower()

        # Use provided image processor or fall back to pipeline's default
        processor = image_processor if image_processor is not None else self.image_processor

        # Use provided OCR engine or environment default
        selected_ocr = ocr_engine or os.getenv("DOCLING_OCR_ENGINE", "rapidocr")

        # Audio formats - transcribe with Whisper ASR
        audio_formats = ['.mp3', '.wav', '.m4a', '.flac']
        if file_ext in audio_formats:
            content = self._transcribe_audio(file_path)
            return (content, None, [])  # No DoclingDocument or images for audio

        # Docling-supported formats (convert to markdown)
        docling_formats = ['.pdf', '.docx', '.doc', '.pptx', '.ppt', '.xlsx', '.xls', '.html', '.htm']

        if file_ext in docling_formats:
            try:
                from docling.document_converter import DocumentConverter
                from docling.datamodel.pipeline_options import PdfPipelineOptions

                logger.info(
                    f"Converting {file_ext} file using Docling with OCR engine: {selected_ocr} "
                    f"({os.path.basename(file_path)})"
                )

                # OCR Engine Factory - configure Docling based on selected engine
                pipeline_options = PdfPipelineOptions()
                converter_configured = False

                if selected_ocr == "rapidocr":
                    try:
                        from docling.backend.rapidocr_backend import RapidOcrOptions
                        pipeline_options.ocr_options = RapidOcrOptions()
                        converter = DocumentConverter(pipeline_options=pipeline_options)
                        logger.debug("✅ Using RapidOCR engine (~2x faster than EasyOCR)")
                        converter_configured = True
                    except ImportError:
                        logger.warning(
                            "RapidOCR not available. Install with: pip install rapidocr-onnxruntime. "
                            "Falling back to EasyOCR."
                        )

                elif selected_ocr == "tesseract":
                    try:
                        from docling.backend.tesseract_ocr_backend import TesseractOcrOptions
                        pipeline_options.ocr_options = TesseractOcrOptions()
                        converter = DocumentConverter(pipeline_options=pipeline_options)
                        logger.debug("✅ Using Tesseract engine (best for high-quality scans)")
                        converter_configured = True
                    except ImportError:
                        logger.warning(
                            "Tesseract not available. Install with: apt-get install tesseract-ocr. "
                            "Falling back to EasyOCR."
                        )

                elif selected_ocr == "easyocr":
                    # EasyOCR is Docling's default, no special config needed
                    converter = DocumentConverter()
                    logger.debug("✅ Using EasyOCR engine (Docling default, multilingual)")
                    converter_configured = True

                else:
                    logger.warning(f"Unknown OCR engine '{selected_ocr}', falling back to EasyOCR")

                # Fallback to default EasyOCR if specific engine failed to configure
                if not converter_configured:
                    converter = DocumentConverter()
                    logger.debug("Using EasyOCR engine (fallback)")

                result = converter.convert(file_path)

                # Export to markdown (contains <!-- image --> placeholders)
                markdown_content = result.document.export_to_markdown()
                logger.info(f"Successfully converted {os.path.basename(file_path)} to markdown")

                # Extract and analyze images BEFORE chunking
                extracted_images = []
                if processor and result.document:
                    logger.info("📷 Extraction des images AVANT chunking pour enrichir le contenu...")
                    try:
                        # Generate job_id from file path
                        job_id = f"doc_{os.path.basename(file_path).replace(' ', '_')[:50]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

                        extracted_images = await processor.extract_images_from_document(
                            docling_doc=result.document,
                            job_id=job_id,
                            pdf_path=file_path
                        )

                        if extracted_images:
                            logger.info(f"✅ {len(extracted_images)} images extraites et analysées")
                            # Image content will be made searchable via synthetic chunks (see _create_image_chunks)

                    except Exception as e:
                        logger.warning(f"⚠️ Échec de l'extraction d'images: {e}")
                        # Continue without images - not critical

                # Return enriched markdown, DoclingDocument, and extracted images
                return (markdown_content, result.document, extracted_images)

            except Exception as e:
                logger.error(f"Failed to convert {file_path} with Docling: {e}")
                # Fall back to raw text if Docling fails
                logger.warning(f"Falling back to raw text extraction for {file_path}")
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        return (f.read(), None, [])
                except:
                    return (f"[Error: Could not read file {os.path.basename(file_path)}]", None, [])

        # Text-based formats (read directly)
        else:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return (f.read(), None, [])
            except UnicodeDecodeError:
                # Try with different encoding
                with open(file_path, 'r', encoding='latin-1') as f:
                    return (f.read(), None, [])

    def _transcribe_audio(self, file_path: str) -> str:
        """Transcribe audio file using Whisper ASR via Docling."""
        try:
            from pathlib import Path
            from docling.document_converter import DocumentConverter, AudioFormatOption
            from docling.datamodel.pipeline_options import AsrPipelineOptions
            from docling.datamodel import asr_model_specs
            from docling.datamodel.base_models import InputFormat
            from docling.pipeline.asr_pipeline import AsrPipeline

            # Use Path object - Docling expects this
            audio_path = Path(file_path).resolve()
            logger.info(f"Transcribing audio file using Whisper Turbo: {audio_path.name}")
            logger.info(f"Audio file absolute path: {audio_path}")

            # Verify file exists
            if not audio_path.exists():
                raise FileNotFoundError(f"Audio file not found: {audio_path}")

            # Configure ASR pipeline with Whisper Turbo model
            pipeline_options = AsrPipelineOptions()
            pipeline_options.asr_options = asr_model_specs.WHISPER_TURBO

            converter = DocumentConverter(
                format_options={
                    InputFormat.AUDIO: AudioFormatOption(
                        pipeline_cls=AsrPipeline,
                        pipeline_options=pipeline_options,
                    )
                }
            )

            # Transcribe the audio file - pass Path object
            result = converter.convert(audio_path)

            # Export to markdown with timestamps
            markdown_content = result.document.export_to_markdown()
            logger.info(f"Successfully transcribed {os.path.basename(file_path)}")
            return markdown_content

        except Exception as e:
            logger.error(f"Failed to transcribe {file_path} with Whisper ASR: {e}")
            return f"[Error: Could not transcribe audio file {os.path.basename(file_path)}]"

    def _extract_title(self, content: str, file_path: str) -> str:
        """Extract title from document content or filename."""
        # Try to find markdown title
        lines = content.split('\n')
        for line in lines[:10]:  # Check first 10 lines
            line = line.strip()
            if line.startswith('# '):
                return line[2:].strip()
        
        # Fallback to filename
        return os.path.splitext(os.path.basename(file_path))[0]
    
    def _extract_document_metadata(self, content: str, file_path: str) -> Dict[str, Any]:
        """Extract metadata from document content."""
        metadata = {
            "file_path": file_path,
            "file_size": len(content),
            "ingestion_date": datetime.now().isoformat()
        }
        
        # Try to extract YAML frontmatter
        if content.startswith('---'):
            try:
                import yaml
                end_marker = content.find('\n---\n', 4)
                if end_marker != -1:
                    frontmatter = content[4:end_marker]
                    yaml_metadata = yaml.safe_load(frontmatter)
                    if isinstance(yaml_metadata, dict):
                        metadata.update(yaml_metadata)
            except ImportError:
                logger.warning("PyYAML not installed, skipping frontmatter extraction")
            except Exception as e:
                logger.warning(f"Failed to parse frontmatter: {e}")
        
        # Extract some basic metadata from content
        lines = content.split('\n')
        metadata['line_count'] = len(lines)
        metadata['word_count'] = len(content.split())
        
        return metadata
    
    async def _save_to_postgres(
        self,
        title: str,
        source: str,
        content: str,
        chunks: List[DocumentChunk],
        metadata: Dict[str, Any],
        images: List[ImageMetadata] = None
    ) -> str:
        """Save document, chunks, and images to PostgreSQL."""
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                # Insert document
                document_result = await conn.fetchrow(
                    """
                    INSERT INTO documents (title, source, content, metadata)
                    VALUES ($1, $2, $3, $4)
                    RETURNING id::text
                    """,
                    title,
                    source,
                    content,
                    json.dumps(metadata)
                )

                document_id = document_result["id"]

                # Insert chunks (first pass - without prev/next and parent relationships)
                chunk_id_map = {}  # Map chunk index to UUID for linking
                parent_indices = []  # Track which chunks are parents and their indices

                for chunk in chunks:
                    # Convert embedding to PostgreSQL vector string format
                    embedding_data = None
                    if hasattr(chunk, 'embedding') and chunk.embedding:
                        # PostgreSQL vector format: '[1.0,2.0,3.0]' (no spaces after commas)
                        embedding_data = '[' + ','.join(map(str, chunk.embedding)) + ']'

                    # 🆕 Extract structural metadata from chunk.metadata
                    section_hierarchy = chunk.metadata.get("section_hierarchy", [])
                    heading_context = chunk.metadata.get("heading_context")
                    document_position = chunk.metadata.get("document_position", 0.0)

                    # 🆕 Extract chunk_level (parent/child) from metadata
                    chunk_level = chunk.metadata.get("chunk_level", None)  # Default: None for hybrid chunks

                    # 🆕 Extract bbox (bounding box) from metadata
                    bbox_data = chunk.metadata.get("bbox")  # None if not available

                    chunk_result = await conn.fetchrow(
                        """
                        INSERT INTO chunks (
                            document_id, content, embedding, chunk_index, metadata, token_count,
                            section_hierarchy, heading_context, document_position, chunk_level,
                            bbox
                        )
                        VALUES ($1::uuid, $2, $3::vector, $4, $5, $6, $7, $8, $9, $10::chunk_level_enum, $11)
                        RETURNING id::text
                        """,
                        document_id,
                        chunk.content,
                        embedding_data,
                        chunk.index,
                        json.dumps(chunk.metadata),
                        chunk.token_count,
                        json.dumps(section_hierarchy),  # 🆕 Section hierarchy
                        heading_context,  # 🆕 Heading context
                        document_position,  # 🆕 Document position
                        chunk_level,  # 🆕 Chunk level (parent/child)
                        json.dumps(bbox_data) if bbox_data else None  # 🆕 Bounding box for PDF highlighting
                    )

                    chunk_id_map[chunk.index] = chunk_result["id"]

                    # Track parent chunks for parent-child linking
                    if chunk_level == "parent":
                        parent_indices.append(chunk.index)

                # 🆕 Second pass: Link chunks with prev/next relationships (for flat chunks)
                if len(chunks) > 1 and not parent_indices:  # Only if not using parent-child
                    for i, chunk in enumerate(chunks):
                        # Use chunk.index to access chunk_id_map, not enumerate index i
                        current_chunk_index = chunk.index
                        prev_chunk_index = chunks[i - 1].index if i > 0 else None
                        next_chunk_index = chunks[i + 1].index if i < len(chunks) - 1 else None

                        prev_chunk_id = chunk_id_map.get(prev_chunk_index) if prev_chunk_index is not None else None
                        next_chunk_id = chunk_id_map.get(next_chunk_index) if next_chunk_index is not None else None

                        if prev_chunk_id or next_chunk_id:
                            await conn.execute(
                                """
                                UPDATE chunks
                                SET prev_chunk_id = $2::uuid, next_chunk_id = $3::uuid
                                WHERE id = $1::uuid
                                """,
                                chunk_id_map[current_chunk_index],
                                prev_chunk_id,
                                next_chunk_id
                            )

                    logger.info(f"Linked {len(chunks)} chunks with prev/next relationships")

                # 🆕 Third pass: Link child chunks to parent chunks (for hierarchical chunks)
                if parent_indices:
                    # Build map from parent_index to parent UUID
                    parent_uuid_map = {idx: chunk_id_map[idx] for idx in parent_indices}

                    for chunk in chunks:
                        if chunk.metadata.get("chunk_level") == "child":
                            parent_idx = chunk.metadata.get("parent_index")
                            if parent_idx is not None and parent_idx in parent_uuid_map:
                                parent_uuid = parent_uuid_map[parent_idx]

                                await conn.execute(
                                    """
                                    UPDATE chunks
                                    SET parent_chunk_id = $2::uuid
                                    WHERE id = $1::uuid
                                    """,
                                    chunk_id_map[chunk.index],
                                    parent_uuid
                                )

                    logger.info(f"Linked {len(chunks) - len(parent_indices)} child chunks to {len(parent_indices)} parents")

                # Insert images if any
                if images:
                    for image in images:
                        # Find corresponding chunk (match by page number or proximity)
                        chunk_id = self._find_chunk_for_image(image, chunks, chunk_id_map)

                        await conn.execute(
                            """
                            INSERT INTO document_images (
                                document_id, chunk_id, image_path, image_base64,
                                image_format, image_size_bytes, page_number, position,
                                description, ocr_text, confidence_score, metadata
                            )
                            VALUES (
                                $1::uuid, $2::uuid, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12
                            )
                            """,
                            document_id,
                            chunk_id,
                            image.image_path,
                            image.image_base64,
                            image.image_format,
                            image.image_size_bytes,
                            image.page_number,
                            json.dumps(image.position),
                            image.description,
                            image.ocr_text,
                            image.confidence_score,
                            json.dumps(image.metadata) if image.metadata else '{}'
                        )

                    logger.info(f"Saved {len(images)} images to database")

                return document_id

    def _find_chunk_for_image(
        self,
        image: ImageMetadata,
        chunks: List[DocumentChunk],
        chunk_id_map: Dict[int, str]
    ) -> Optional[str]:
        """
        Find the most appropriate chunk for an image based on page number and position.

        Args:
            image: Image metadata
            chunks: List of document chunks
            chunk_id_map: Mapping of chunk index to UUID

        Returns:
            Chunk UUID or None
        """
        # Simple heuristic: match by page number if available in chunk metadata
        for chunk in chunks:
            chunk_page = chunk.metadata.get("page_number")
            if chunk_page == image.page_number:
                return chunk_id_map.get(chunk.index)

        # Fallback: return first chunk (images will be accessible via document anyway)
        if chunks:
            return chunk_id_map.get(chunks[0].index)

        return None
    
    async def _clean_databases(self):
        """Clean existing data from databases."""
        logger.warning("Cleaning existing data from databases...")
        
        # Clean PostgreSQL
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("DELETE FROM chunks")
                await conn.execute("DELETE FROM documents")
        
        logger.info("Cleaned PostgreSQL database")

async def main():
    """Main function for running ingestion."""
    parser = argparse.ArgumentParser(description="Ingest documents into vector DB")
    parser.add_argument("--documents", "-d", default="documents", help="Documents folder path")
    parser.add_argument("--no-clean", action="store_true", help="Skip cleaning existing data before ingestion (default: cleans automatically)")
    parser.add_argument("--chunk-size", type=int, default=1000, help="Chunk size for splitting documents")
    parser.add_argument("--chunk-overlap", type=int, default=200, help="Chunk overlap size")
    parser.add_argument("--no-semantic", action="store_true", help="Disable semantic chunking")
    # Graph-related arguments removed
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Create ingestion configuration
    config = IngestionConfig(
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        use_semantic_chunking=not args.no_semantic
    )

    # Create and run pipeline - clean by default unless --no-clean is specified
    pipeline = DocumentIngestionPipeline(
        config=config,
        documents_folder=args.documents,
        clean_before_ingest=not args.no_clean  # Clean by default
    )
    
    def progress_callback(current: int, total: int):
        print(f"Progress: {current}/{total} documents processed")
    
    try:
        start_time = datetime.now()
        
        results = await pipeline.ingest_documents(progress_callback)
        
        end_time = datetime.now()
        total_time = (end_time - start_time).total_seconds()
        
        # Print summary
        print("\n" + "="*50)
        print("INGESTION SUMMARY")
        print("="*50)
        print(f"Documents processed: {len(results)}")
        print(f"Total chunks created: {sum(r.chunks_created for r in results)}")
        # Graph-related stats removed
        print(f"Total errors: {sum(len(r.errors) for r in results)}")
        print(f"Total processing time: {total_time:.2f} seconds")
        print()
        
        # Print individual results
        for result in results:
            status = "✓" if not result.errors else "✗"
            print(f"{status} {result.title}: {result.chunks_created} chunks")
            
            if result.errors:
                for error in result.errors:
                    print(f"  Error: {error}")
        
    except KeyboardInterrupt:
        print("\nIngestion interrupted by user")
    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        raise
    finally:
        await pipeline.close()


if __name__ == "__main__":
    asyncio.run(main())