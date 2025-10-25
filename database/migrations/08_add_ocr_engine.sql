-- Migration 08: Add OCR engine selection for document ingestion
-- Description: Allows per-job OCR engine choice (RapidOCR, EasyOCR, Tesseract)
-- Date: 2025-01-25
-- Related: Dual-dropdown OCR + VLM selection system

-- Add ocr_engine column to ingestion_jobs table
ALTER TABLE ingestion_jobs
ADD COLUMN IF NOT EXISTS ocr_engine VARCHAR(50) DEFAULT 'rapidocr';

-- Update existing jobs to use RapidOCR (current default)
UPDATE ingestion_jobs
SET ocr_engine = 'rapidocr'
WHERE ocr_engine IS NULL;

-- Create index for filtering by OCR engine
CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_ocr_engine
    ON ingestion_jobs(ocr_engine);

-- Add informative comment
COMMENT ON COLUMN ingestion_jobs.ocr_engine IS 'OCR engine used for document parsing: rapidocr (default, fast), easyocr (multilingual), tesseract (high-quality scans)';

-- Verify migration
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ingestion_jobs' AND column_name = 'ocr_engine'
    ) THEN
        RAISE NOTICE '✅ Migration 08 applied successfully: ocr_engine column added to ingestion_jobs';
    ELSE
        RAISE EXCEPTION '❌ Migration 08 failed: ocr_engine column not found';
    END IF;
END $$;
