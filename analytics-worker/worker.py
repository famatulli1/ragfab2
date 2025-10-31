"""
Analytics Worker - Quality Management with Chocolatine AI
Runs nightly at 3 AM to analyze RAG quality and make intelligent recommendations
"""

import asyncio
import asyncpg
import httpx
import os
import json
import logging
from datetime import datetime, time, timedelta
from typing import Optional, List, Dict, Any
from uuid import uuid4

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL")
CHOCOLATINE_API_URL = os.getenv("CHOCOLATINE_API_URL", "https://apigpt.mynumih.fr")
CHOCOLATINE_API_KEY = os.getenv("CHOCOLATINE_API_KEY", "")
CHOCOLATINE_MODEL = os.getenv("CHOCOLATINE_MODEL", "mistral-small-latest")
CHOCOLATINE_TIMEOUT = float(os.getenv("CHOCOLATINE_TIMEOUT", "120.0"))

# Analysis thresholds
BLACKLIST_THRESHOLD = 0.3  # <30% satisfaction
MIN_APPEARANCES = 3  # Minimum ratings for reliability
REINGESTION_THRESHOLD = 0.3  # <30% satisfaction at doc level
MIN_DOC_APPEARANCES = 10  # Minimum ratings for doc-level decisions


class ChocolatineClient:
    """Client for Chocolatine AI API with structured prompts"""

    def __init__(self):
        self.api_url = CHOCOLATINE_API_URL
        self.api_key = CHOCOLATINE_API_KEY
        self.model = CHOCOLATINE_MODEL
        self.timeout = CHOCOLATINE_TIMEOUT

    async def analyze_chunk_quality(
        self,
        chunk_content: str,
        thumbs_up: int,
        thumbs_down: int,
        total_appearances: int,
        feedbacks: List[str]
    ) -> Dict[str, Any]:
        """
        Ask Chocolatine to validate if a chunk should be blacklisted

        Returns:
            {
                "should_blacklist": bool,
                "confidence": float,
                "reasoning": str,
                "recommendations": str
            }
        """
        prompt = f"""Tu es un expert en amélioration de systèmes RAG. Analyse ce chunk problématique :

STATISTIQUES :
- {thumbs_up} 👍 thumbs up
- {thumbs_down} 👎 thumbs down
- {total_appearances} apparitions totales
- Taux satisfaction : {(thumbs_up / (thumbs_up + thumbs_down) * 100):.1f}%

CONTENU DU CHUNK :
{chunk_content[:500]}...

FEEDBACKS UTILISATEURS :
{chr(10).join(f"- {fb}" for fb in feedbacks) if feedbacks else "Aucun feedback textuel"}

QUESTION : Ce chunk mérite-t-il d'être BLACKLISTÉ (exclu des recherches RAG) ?

Réponds UNIQUEMENT en JSON structuré :
{{
    "should_blacklist": true/false,
    "confidence": 0.0-1.0,
    "reasoning": "Explication courte de ta décision",
    "recommendations": "Suggestions concrètes (amélioration contenu, réingestion, etc.)"
}}

CRITÈRES IMPORTANTS :
- Si feedbacks mentionnent "hors sujet", "pas pertinent" → blacklist probable
- Si satisfaction <30% ET feedbacks négatifs cohérents → blacklist
- Si contenu trop générique ou redondant → blacklist
- Si erreurs factuelles ou informations obsolètes → blacklist
- Si simplement mal formulé mais info utile → NE PAS blacklist, suggérer réingestion
"""

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.api_url}/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": "Tu es un expert en amélioration de systèmes RAG. Réponds UNIQUEMENT en JSON valide."},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.3,  # Low temperature for consistent decisions
                        "max_tokens": 500
                    }
                )
                response.raise_for_status()
                result = response.json()

                # Extract JSON from response
                content = result["choices"][0]["message"]["content"]

                # Parse JSON (handle potential markdown wrapping)
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()

                analysis = json.loads(content)
                logger.info(f"✅ Chocolatine analysis: blacklist={analysis['should_blacklist']}, confidence={analysis['confidence']}")
                return analysis

        except Exception as e:
            logger.error(f"❌ Chocolatine API error: {e}")
            # Fallback to conservative decision
            return {
                "should_blacklist": False,
                "confidence": 0.0,
                "reasoning": f"Erreur API Chocolatine, décision conservatrice (pas de blacklist). Erreur: {str(e)}",
                "recommendations": "Réessayer l'analyse plus tard"
            }

    async def analyze_document_quality(
        self,
        document_title: str,
        document_source: str,
        satisfaction_rate: float,
        total_appearances: int,
        problematic_chunks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Ask Chocolatine for document reingestion recommendations

        Returns:
            {
                "needs_reingestion": bool,
                "confidence": float,
                "reasoning": str,
                "reingestion_config": str,
                "alternative_actions": str
            }
        """
        issues_summary = "\n".join([
            f"- Chunk (satisfaction {c['satisfaction_rate']:.1%}): {c['content'][:100]}..."
            for c in problematic_chunks[:5]  # Top 5 worst chunks
        ])

        prompt = f"""Tu es un expert en gestion documentaire pour systèmes RAG. Analyse ce document problématique :

DOCUMENT :
- Titre : {document_title}
- Source : {document_source}
- Satisfaction globale : {satisfaction_rate:.1%}
- Apparitions totales : {total_appearances}

CHUNKS PROBLÉMATIQUES :
{issues_summary}

QUESTION : Ce document doit-il être RÉINGÉRÉ (supprimé puis re-uploadé) ?

Réponds UNIQUEMENT en JSON structuré :
{{
    "needs_reingestion": true/false,
    "confidence": 0.0-1.0,
    "reasoning": "Pourquoi réingérer (ou pas) ?",
    "reingestion_config": "Suggestions config (OCR engine, VLM engine, chunker type)",
    "alternative_actions": "Actions alternatives (supprimer sections, améliorer source, etc.)"
}}

CRITÈRES :
- Si <30% satisfaction ET plusieurs chunks problématiques → réingestion probable
- Si problème de chunking (chunks coupés) → réingestion avec chunker différent
- Si problème OCR (texte mal extrait) → réingestion avec OCR différent
- Si problème d'images manquantes → réingestion avec VLM activé
- Si document obsolète ou erreurs factuelles → suppression complète
"""

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.api_url}/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": "Tu es un expert en gestion documentaire RAG. Réponds UNIQUEMENT en JSON valide."},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.3,
                        "max_tokens": 600
                    }
                )
                response.raise_for_status()
                result = response.json()

                content = result["choices"][0]["message"]["content"]
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()

                analysis = json.loads(content)
                logger.info(f"✅ Chocolatine document analysis: reingest={analysis['needs_reingestion']}, confidence={analysis['confidence']}")
                return analysis

        except Exception as e:
            logger.error(f"❌ Chocolatine API error: {e}")
            return {
                "needs_reingestion": False,
                "confidence": 0.0,
                "reasoning": f"Erreur API Chocolatine. Erreur: {str(e)}",
                "reingestion_config": "N/A",
                "alternative_actions": "Réessayer l'analyse plus tard"
            }


async def run_quality_analysis(
    db_pool: asyncpg.Pool,
    chocolatine: ChocolatineClient,
    run_id: Optional[str] = None,
    started_by: str = "cron"
) -> str:
    """
    Reusable quality analysis function (for both cron and manual trigger)

    Args:
        db_pool: Database connection pool
        chocolatine: Chocolatine API client
        run_id: Optional run ID (if None, creates new one)
        started_by: 'cron' or user_id

    Returns:
        run_id: UUID of the analysis run
    """
    if run_id is None:
        run_id = str(uuid4())

    logger.info(f"🚀 Starting quality analysis (run_id={run_id}, started_by={started_by})")

    async with db_pool.acquire() as conn:
        try:
            # Check if run already exists (from manual trigger)
            existing_run = await conn.fetchrow("""
                SELECT id, status FROM analysis_runs WHERE id = $1
            """, run_id)

            if existing_run:
                # Update existing run to 'running' status
                logger.info(f"📝 Updating existing run {run_id} to 'running'")
                await conn.execute("""
                    UPDATE analysis_runs
                    SET status = 'running', progress = 0, started_at = NOW()
                    WHERE id = $1
                """, run_id)
            else:
                # Create new analysis run record (scheduled runs)
                await conn.execute("""
                    INSERT INTO analysis_runs (id, status, progress, started_by, started_at)
                    VALUES ($1, 'running', 0, $2, NOW())
                """, run_id, started_by)

            # ============================================================
            # STEP 1: Aggregate ratings and calculate basic scores (0-30%)
            # ============================================================
            logger.info("📊 Step 1: Aggregating ratings...")
            await conn.execute("""
                UPDATE analysis_runs SET progress = 10 WHERE id = $1
            """, run_id)

            # Aggregate chunk-level scores (only for existing chunks)
            await conn.execute("""
                INSERT INTO chunk_quality_scores (chunk_id, thumbs_up_count, thumbs_down_count, total_appearances, last_appearance_at, updated_at)
                SELECT
                    (source->>'chunk_id')::uuid as chunk_id,
                    COUNT(*) FILTER (WHERE mr.rating = 1) as thumbs_up,
                    COUNT(*) FILTER (WHERE mr.rating = -1) as thumbs_down,
                    COUNT(*) as total,
                    MAX(mr.created_at) as last_appearance,
                    NOW()
                FROM messages m
                JOIN message_ratings mr ON m.id = mr.message_id
                CROSS JOIN LATERAL jsonb_array_elements(m.sources) as source
                WHERE m.role = 'assistant' AND m.sources IS NOT NULL
                  AND source->>'chunk_id' IS NOT NULL
                  AND EXISTS (
                      SELECT 1 FROM chunks c
                      WHERE c.id = (source->>'chunk_id')::uuid
                  )
                GROUP BY chunk_id
                ON CONFLICT (chunk_id) DO UPDATE SET
                    thumbs_up_count = EXCLUDED.thumbs_up_count,
                    thumbs_down_count = EXCLUDED.thumbs_down_count,
                    total_appearances = EXCLUDED.total_appearances,
                    last_appearance_at = EXCLUDED.last_appearance_at,
                    updated_at = NOW()
            """)

            # Aggregate document-level scores
            await conn.execute("""
                INSERT INTO document_quality_scores (document_id, thumbs_up_count, thumbs_down_count, total_appearances, last_appearance_at, updated_at)
                SELECT
                    c.document_id,
                    SUM(cqs.thumbs_up_count) as thumbs_up,
                    SUM(cqs.thumbs_down_count) as thumbs_down,
                    SUM(cqs.total_appearances) as total,
                    MAX(cqs.last_appearance_at) as last_appearance,
                    NOW()
                FROM chunk_quality_scores cqs
                JOIN chunks c ON cqs.chunk_id = c.id
                GROUP BY c.document_id
                ON CONFLICT (document_id) DO UPDATE SET
                    thumbs_up_count = EXCLUDED.thumbs_up_count,
                    thumbs_down_count = EXCLUDED.thumbs_down_count,
                    total_appearances = EXCLUDED.total_appearances,
                    last_appearance_at = EXCLUDED.last_appearance_at,
                    updated_at = NOW()
            """)

            await conn.execute("""
                UPDATE analysis_runs SET progress = 30 WHERE id = $1
            """, run_id)

            # ============================================================
            # STEP 2: Analyze problematic chunks with Chocolatine (30-70%)
            # ============================================================
            logger.info("🧠 Step 2: Analyzing problematic chunks with Chocolatine...")

            # Fetch chunks with low satisfaction (exclude whitelisted)
            problematic_chunks = await conn.fetch("""
                SELECT
                    cqs.chunk_id,
                    c.content,
                    cqs.thumbs_up_count,
                    cqs.thumbs_down_count,
                    cqs.total_appearances,
                    cqs.satisfaction_rate,
                    cqs.is_whitelisted
                FROM chunk_quality_scores cqs
                JOIN chunks c ON cqs.chunk_id = c.id
                WHERE cqs.satisfaction_rate < $1
                  AND cqs.total_appearances >= $2
                  AND (cqs.is_whitelisted IS NULL OR cqs.is_whitelisted = false)
                  AND (cqs.is_blacklisted IS NULL OR cqs.is_blacklisted = false)
                ORDER BY (cqs.thumbs_down_count * cqs.total_appearances) DESC
                LIMIT 50
            """, BLACKLIST_THRESHOLD, MIN_APPEARANCES)

            chunks_analyzed = 0
            chunks_blacklisted = 0
            total_chunks = len(problematic_chunks)

            for idx, chunk in enumerate(problematic_chunks):
                # Fetch user feedbacks for this chunk
                feedbacks = await conn.fetch("""
                    SELECT DISTINCT mr.feedback
                    FROM messages m
                    JOIN message_ratings mr ON m.id = mr.message_id
                    CROSS JOIN LATERAL jsonb_array_elements(m.sources) as source
                    WHERE (source->>'chunk_id')::uuid = $1
                      AND mr.feedback IS NOT NULL
                      AND mr.feedback != ''
                """, chunk['chunk_id'])

                feedback_texts = [f['feedback'] for f in feedbacks]

                # Call Chocolatine for validation
                analysis = await chocolatine.analyze_chunk_quality(
                    chunk_content=chunk['content'],
                    thumbs_up=chunk['thumbs_up_count'],
                    thumbs_down=chunk['thumbs_down_count'],
                    total_appearances=chunk['total_appearances'],
                    feedbacks=feedback_texts
                )

                # Store decision in audit log
                await conn.execute("""
                    INSERT INTO quality_audit_log
                    (id, chunk_id, action, reason, decided_by, ai_analysis, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6, NOW())
                """,
                    str(uuid4()),
                    chunk['chunk_id'],
                    'blacklist' if analysis['should_blacklist'] else 'analyze',
                    analysis['reasoning'],
                    started_by,
                    json.dumps(analysis)
                )

                # Apply blacklist if recommended with high confidence
                if analysis['should_blacklist'] and analysis['confidence'] >= 0.7:
                    await conn.execute("""
                        UPDATE chunk_quality_scores
                        SET is_blacklisted = true,
                            blacklist_reason = $2,
                            updated_at = NOW()
                        WHERE chunk_id = $1
                    """, chunk['chunk_id'], analysis['reasoning'])
                    chunks_blacklisted += 1
                    logger.info(f"🚫 Chunk blacklisted: {chunk['chunk_id']} (confidence={analysis['confidence']:.2f})")

                chunks_analyzed += 1

                # Update progress (30% → 70%)
                progress = 30 + int((idx + 1) / total_chunks * 40)
                await conn.execute("""
                    UPDATE analysis_runs SET progress = $2 WHERE id = $1
                """, run_id, progress)

            # ============================================================
            # STEP 3: Analyze documents for reingestion (70-100%)
            # ============================================================
            logger.info("📄 Step 3: Analyzing documents for reingestion...")

            problematic_docs = await conn.fetch("""
                SELECT
                    dqs.document_id,
                    d.title,
                    d.source,
                    dqs.satisfaction_rate,
                    dqs.total_appearances
                FROM document_quality_scores dqs
                JOIN documents d ON dqs.document_id = d.id
                WHERE dqs.satisfaction_rate < $1
                  AND dqs.total_appearances >= $2
                  AND (dqs.needs_reingestion IS NULL OR dqs.needs_reingestion = false)
                ORDER BY dqs.satisfaction_rate ASC
                LIMIT 20
            """, REINGESTION_THRESHOLD, MIN_DOC_APPEARANCES)

            documents_flagged = 0
            total_docs = len(problematic_docs)

            for idx, doc in enumerate(problematic_docs):
                # Fetch worst chunks for this document
                worst_chunks = await conn.fetch("""
                    SELECT
                        c.content,
                        cqs.satisfaction_rate
                    FROM chunks c
                    JOIN chunk_quality_scores cqs ON c.id = cqs.chunk_id
                    WHERE c.document_id = $1
                      AND cqs.satisfaction_rate IS NOT NULL
                    ORDER BY cqs.satisfaction_rate ASC
                    LIMIT 5
                """, doc['document_id'])

                chunk_list = [dict(c) for c in worst_chunks]

                # Call Chocolatine for recommendations
                analysis = await chocolatine.analyze_document_quality(
                    document_title=doc['title'],
                    document_source=doc['source'],
                    satisfaction_rate=doc['satisfaction_rate'],
                    total_appearances=doc['total_appearances'],
                    problematic_chunks=chunk_list
                )

                # Store recommendation in audit log
                await conn.execute("""
                    INSERT INTO quality_audit_log
                    (id, document_id, action, reason, decided_by, ai_analysis, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6, NOW())
                """,
                    str(uuid4()),
                    doc['document_id'],
                    'recommend_reingestion' if analysis['needs_reingestion'] else 'document_analysis',
                    analysis['reasoning'],
                    started_by,
                    json.dumps(analysis)
                )

                # Flag document if recommended with high confidence
                if analysis['needs_reingestion'] and analysis['confidence'] >= 0.7:
                    await conn.execute("""
                        UPDATE document_quality_scores
                        SET needs_reingestion = true,
                            reingestion_reason = $2,
                            updated_at = NOW()
                        WHERE document_id = $1
                    """, doc['document_id'], analysis['reasoning'])
                    documents_flagged += 1
                    logger.info(f"⚠️ Document flagged for reingestion: {doc['title']} (confidence={analysis['confidence']:.2f})")

                # Update progress (70% → 100%)
                progress = 70 + int((idx + 1) / total_docs * 30) if total_docs > 0 else 100
                await conn.execute("""
                    UPDATE analysis_runs SET progress = $2 WHERE id = $1
                """, run_id, progress)

            # ============================================================
            # STEP 4: Complete analysis run
            # ============================================================
            await conn.execute("""
                SELECT complete_analysis_run($1, $2, $3, $4)
            """, run_id, chunks_analyzed, chunks_blacklisted, documents_flagged)

            logger.info(f"✅ Analysis complete: {chunks_analyzed} chunks analyzed, {chunks_blacklisted} blacklisted, {documents_flagged} docs flagged")
            return run_id

        except Exception as e:
            logger.error(f"❌ Analysis failed: {e}", exc_info=True)
            await conn.execute("""
                SELECT fail_analysis_run($1, $2)
            """, run_id, str(e))
            raise


async def get_pending_job(db_pool: asyncpg.Pool) -> Optional[Dict[str, Any]]:
    """
    Get the next pending analysis job from the database

    Returns:
        Job record if found, None otherwise
    """
    async with db_pool.acquire() as conn:
        job = await conn.fetchrow("""
            SELECT id, started_by, started_at
            FROM analysis_runs
            WHERE status = 'pending'
            ORDER BY started_at ASC
            LIMIT 1
        """)

        if job:
            return dict(job)
        return None


async def poll_jobs(db_pool: asyncpg.Pool, chocolatine: ChocolatineClient, poll_interval: int = 3):
    """
    Poll for pending analysis jobs and execute them

    Args:
        db_pool: Database connection pool
        chocolatine: Chocolatine API client
        poll_interval: Seconds between polls (default: 3)
    """
    logger.info(f"🔄 Starting job polling (interval: {poll_interval}s)")

    while True:
        try:
            # Check for pending jobs
            job = await get_pending_job(db_pool)

            if job:
                logger.info(f"📥 Found pending job: {job['id']} (triggered by {job['started_by']})")

                # Execute the analysis
                await run_quality_analysis(
                    db_pool=db_pool,
                    chocolatine=chocolatine,
                    run_id=str(job['id']),
                    started_by=str(job['started_by'])
                )

                logger.info(f"✅ Job {job['id']} completed")
            else:
                # No pending jobs, wait before polling again
                await asyncio.sleep(poll_interval)

        except Exception as e:
            logger.error(f"❌ Error in poll loop: {e}", exc_info=True)
            await asyncio.sleep(poll_interval)


async def scheduled_analysis(db_pool: asyncpg.Pool, chocolatine: ChocolatineClient):
    """
    Runs quality analysis at 3 AM every day
    """
    while True:
        now = datetime.now()
        target_time = now.replace(hour=3, minute=0, second=0, microsecond=0)

        # If we passed 3 AM today, schedule for tomorrow
        if now >= target_time:
            target_time = target_time + timedelta(days=1)

        # Calculate sleep duration
        sleep_seconds = (target_time - now).total_seconds()
        logger.info(f"⏰ Next analysis scheduled at {target_time} (in {sleep_seconds/3600:.1f}h)")

        await asyncio.sleep(sleep_seconds)

        try:
            await run_quality_analysis(db_pool, chocolatine, started_by="cron")
        except Exception as e:
            logger.error(f"❌ Scheduled analysis failed: {e}", exc_info=True)


async def main():
    """
    Main entry point for analytics worker

    Runs two parallel tasks:
    1. Job polling: Checks for pending jobs every 3 seconds
    2. Scheduled analysis: Runs at 3 AM daily
    """
    logger.info("🚀 Starting Analytics Worker...")

    # Initialize database connection
    db_pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=2,
        max_size=10,
        command_timeout=60
    )

    # Initialize Chocolatine client
    chocolatine = ChocolatineClient()

    logger.info("✅ Worker initialized successfully")
    logger.info(f"📡 Chocolatine API: {CHOCOLATINE_API_URL}")
    logger.info(f"🤖 Model: {CHOCOLATINE_MODEL}")

    # Run both job polling and scheduled analysis in parallel
    await asyncio.gather(
        poll_jobs(db_pool, chocolatine, poll_interval=3),
        scheduled_analysis(db_pool, chocolatine)
    )


if __name__ == "__main__":
    asyncio.run(main())
