-- Migration 07: Add VLM engine selection to ingestion jobs
-- Purpose: Allow users to choose between PaddleOCR-VL and InternVL per document
-- Description: Adds vlm_engine column to track which VLM engine was used for image extraction
-- Date: 2025-01-25

-- Add vlm_engine column with default value
ALTER TABLE ingestion_jobs
ADD COLUMN IF NOT EXISTS vlm_engine VARCHAR(50) DEFAULT 'paddleocr-vl';

-- Add comment for documentation
COMMENT ON COLUMN ingestion_jobs.vlm_engine IS
  'VLM engine used for image extraction: paddleocr-vl (local, fast), internvl (API, rich descriptions), or none (no image extraction)';

-- Update existing jobs to use default engine
UPDATE ingestion_jobs
SET vlm_engine = 'paddleocr-vl'
WHERE vlm_engine IS NULL;

-- Create index for filtering by engine (useful for analytics)
CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_vlm_engine
  ON ingestion_jobs(vlm_engine);

-- Log success
DO $$
BEGIN
    RAISE NOTICE '✅ Migration 07 applied: vlm_engine column added to ingestion_jobs';
    RAISE NOTICE '   Default engine: paddleocr-vl';
    RAISE NOTICE '   Supported engines: paddleocr-vl, internvl, none';
END $$;
