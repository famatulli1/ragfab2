# VLM Image Extraction - Testing Guide

## Implementation Status: ✅ COMPLETE & MIGRATED

All 5 phases of the VLM image extraction feature have been implemented and **migrated to API Vision Générique** (apivlm.mynumih.fr).

## What Was Implemented

### Backend Components
- **Database Schema** (`database/03_images_schema.sql`): PostgreSQL table for storing image metadata, descriptions, OCR text, and base64 data
- **Image Processor** (`rag-app/ingestion/image_processor.py`): Core VLM integration with **FastAPI multipart/form-data** support
- **Ingestion Pipeline** (`rag-app/ingestion/ingest.py`): Modified to extract images during document processing
- **Chunking Integration** (`rag-app/ingestion/chunker.py`): Enhanced to track page numbers for image-chunk linking
- **API Routes** (`web-api/app/routes/images.py`): Endpoints for retrieving image data
- **RAG Search** (`web-api/app/main.py`): Modified to include images in search results

### Frontend Components
- **ImageViewer Component** (`frontend/src/components/ImageViewer.tsx`): Displays image thumbnails with click-to-enlarge modal
- **Type Definitions** (`frontend/src/types/index.ts`): Added ImageData interface and updated Source interface
- **Chat Integration** (`frontend/src/pages/ChatPage.tsx`): Displays images inline in chat responses

## Configuration Required

### Step 1: Use API Vision Générique (Recommended)

**The project is now configured to use the custom FastAPI VLM service:**

- **API URL**: https://apivlm.mynumih.fr
- **Model**: OpenGVLab/InternVL3_5-8B (optimized for document analysis)
- **No API key required**
- **Format**: FastAPI multipart/form-data (not OpenAI format)
- **Endpoints**:
  - `/extract-and-describe` - Combined description + OCR (default)
  - `/describe-image` - Description only
  - `/extract-text` - OCR only
  - `/health` - Health check
  - `/config` - Current configuration

**Performance**: ~10-15s per image

### Step 2: Configure Environment Variables

Edit your `.env` file or set environment variables in Coolify:

```bash
# Enable VLM processing
VLM_ENABLED=true

# VLM API configuration (FastAPI format - API Vision Générique)
VLM_API_URL=https://apivlm.mynumih.fr  # No /v1 suffix, direct endpoints
VLM_API_KEY=  # Leave empty, no API key required
VLM_MODEL_NAME=OpenGVLab/InternVL3_5-8B  # Informational only
VLM_TIMEOUT=60.0  # 60s should be sufficient for InternVL3_5-8B

# VLM prompt (used by /extract-and-describe endpoint)
VLM_PROMPT="Décris cette image en détail en français. Extrais tout le texte visible."

# Image storage
IMAGE_STORAGE_PATH=/app/uploads/images  # Default location
IMAGE_MAX_SIZE_MB=10  # Max size per image
IMAGE_QUALITY=85  # JPEG quality (1-100)
IMAGE_OUTPUT_FORMAT=png  # Output format
```

### Step 3: Restart Services

```bash
# Rebuild and restart ingestion worker (needs VLM config)
docker-compose build ingestion-worker
docker-compose up -d ingestion-worker

# Restart API (for image routes)
docker-compose restart ragfab-api

# Check logs
docker-compose logs -f ingestion-worker
docker-compose logs -f ragfab-api
```

## Testing Workflow

### 1. Verify VLM Service
```bash
# Test VLM API health
curl https://apivlm.mynumih.fr/health

# Test VLM API config
curl https://apivlm.mynumih.fr/config

# Test with a sample image (multipart/form-data format)
curl -X POST https://apivlm.mynumih.fr/extract-and-describe \
  -F "image=@/path/to/test_image.png" \
  -F "temperature=0.1"

# Expected response format:
# {
#   "description": "Description de l'image...",
#   "ocr_text": "Texte extrait de l'image...",
#   "confidence": 0.95
# }
```

### 2. Upload Test Document
```bash
# Access admin interface
open http://localhost:3000/admin

# Login: admin / admin
# Upload a PDF with images (diagrams, charts, screenshots)
```

### 3. Monitor Ingestion
```bash
# Watch worker logs for VLM processing
docker-compose logs -f ingestion-worker

# Expected log output:
# 📷 Extraction de 3 images du document...
# 🔍 Analyse VLM pour image-1.png...
# ✅ Image analysée avec succès (description: 85 chars, OCR: 142 chars)
# 💾 Sauvegarde de 3 images dans la base de données
```

### 4. Verify Database
```bash
# Check images were stored
docker-compose exec postgres psql -U raguser -d ragdb -c "
SELECT
  d.title,
  COUNT(di.id) as image_count,
  AVG(LENGTH(di.description)) as avg_desc_length,
  AVG(LENGTH(di.ocr_text)) as avg_ocr_length
FROM documents d
LEFT JOIN document_images di ON d.id = di.document_id
GROUP BY d.id, d.title
ORDER BY d.created_at DESC
LIMIT 5;
"
```

### 5. Test Chat Interface
```bash
# Open chat
open http://localhost:3000

# Ask a question about content that appears in an image
# Example: "What is shown in the architecture diagram?"

# Expected behavior:
# - RAG search returns chunks from the page containing the image
# - Images appear as thumbnails below the source content
# - Click thumbnail to view full-size image with description and OCR text
# - Modal shows zoom controls and download button
```

## Troubleshooting

### VLM Not Processing Images

**Check 1: VLM service status**
```bash
# Test VLM API connectivity
curl http://localhost:8003/health

# Check worker logs for VLM errors
docker-compose logs ingestion-worker | grep -i vlm
```

**Check 2: Environment variables**
```bash
# Verify VLM_ENABLED is set
docker-compose exec ingestion-worker env | grep VLM

# If not set, add to docker-compose.yml or .env
```

**Check 3: Image detection**
```bash
# Check if images were detected by Docling
docker-compose logs ingestion-worker | grep -i "image"

# Expected: "📷 Extraction de X images du document"
# If not present, PDF may not contain detectable images
```

### Images Not Appearing in Chat

**Check 1: Database**
```bash
# Verify images are stored
docker-compose exec postgres psql -U raguser -d ragdb -c "
SELECT COUNT(*) FROM document_images;
"
```

**Check 2: API response**
```bash
# Check if API includes images in search results
# Open browser DevTools Network tab
# Look for /api/chat response
# Verify sources[].images array is populated
```

**Check 3: Frontend console**
```bash
# Open browser console (F12)
# Look for errors related to ImageViewer component
# Verify images array is received and rendered
```

### Performance Issues

**Problem: VLM processing is slow**

Solution: Adjust model and concurrency
```bash
# Use faster model
VLM_MODEL_NAME=ibm-granite/SmolDocling-256M-Instruct  # ~6s/image

# Increase timeout if needed
VLM_TIMEOUT=180.0

# Reduce image dimensions
IMAGE_MAX_DIMENSION=1024  # Smaller = faster processing
```

**Problem: High memory usage**

Solution: Limit image processing
```bash
# Increase minimum area threshold (skip small images)
IMAGE_MIN_AREA=50000  # Only process larger, more meaningful images

# Reduce quality
IMAGE_QUALITY=75

# Limit concurrent ingestion jobs
# (only run one ingestion at a time)
```

## Expected Performance

### VLM Processing Times
- **SmolDocling-256M**: ~6 seconds per image
- **Qwen2.5-VL-3B**: ~23 seconds per image
- **LLaVA-7B**: ~15 seconds per image
- **GPT-4 Vision**: ~5-10 seconds per image (API latency)

### Document with 5 Images
- Detection: ~1-2 seconds (Docling)
- VLM analysis: ~30-120 seconds (depends on model)
- Storage: ~1-2 seconds
- **Total**: ~32-125 seconds per document

### Database Impact
- Typical image with base64: ~200-500 KB per row
- Document with 10 images: ~2-5 MB additional storage
- Negligible impact on query performance (images loaded only for returned chunks)

## Current VLM Provider

### API Vision Générique (apivlm.mynumih.fr)
- **Model**: OpenGVLab/InternVL3_5-8B
- **Backend**: vLLM server for optimized inference
- **Performance**: ~10-15s per image
- **Quality**: Excellent for document analysis and OCR
- **Cost**: Free (internal service, no API key needed)
- **Endpoints**:
  - `/extract-and-describe` - Combined description + OCR (default)
  - `/describe-image` - Description only
  - `/extract-text` - OCR only
- **Documentation**: https://apivlm.mynumih.fr/docs

### Why InternVL3_5-8B?
- Specifically optimized for document understanding
- Excellent multilingual support (including French)
- Strong OCR capabilities for technical documents
- Balance between speed and quality
- Lower resource requirements than larger models

## API Endpoints Added

### Get Images for Chunk
```bash
GET /api/chunks/{chunk_id}/images
Authorization: Bearer {token}

Response: [
  {
    "id": "uuid",
    "page_number": 3,
    "position": {"x": 0.1, "y": 0.2, "width": 0.8, "height": 0.6},
    "description": "Architecture diagram showing microservices...",
    "ocr_text": "Frontend → API Gateway → Services",
    "image_base64": "iVBORw0KGgo..."
  }
]
```

### Get Images for Document
```bash
GET /api/documents/{document_id}/images
Authorization: Bearer {token}

Response: [ImageMetadata] # Full metadata including paths, timestamps
```

### Get Single Image
```bash
GET /api/images/{image_id}
Authorization: Bearer {token}

Response: ImageMetadata # Complete image data
```

## Next Steps After Testing

Once testing is successful, consider:

1. **Optimize VLM prompts** for your specific document types
2. **Tune image thresholds** (min area, quality) based on your content
3. **Monitor storage usage** and implement cleanup policies if needed
4. **Evaluate VLM model options** for best speed/quality trade-off
5. **Add image search** (similarity search on image embeddings)
6. **Implement image caching** for frequently accessed images
7. **Add user preferences** for image display (grid size, modal behavior)

## Support

For issues or questions:
- Check logs: `docker-compose logs -f ingestion-worker ragfab-api`
- Review CLAUDE.md section "VLM (Vision Language Model) System"
- Verify environment variables are set correctly
- Test VLM API endpoint directly before blaming the integration

---

**Implementation Date**: 2025-01-08
**Status**: ✅ Ready for Testing
**All Phases Completed**: Infrastructure, Ingestion, Backend, Frontend, Documentation
