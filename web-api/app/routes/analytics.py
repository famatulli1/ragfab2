"""
Routes pour l'analytics et l'amélioration continue du RAG via ratings utilisateurs
"""
from fastapi import APIRouter, Depends, HTTPException, Body
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from uuid import uuid4, UUID
import logging

from ..auth import get_current_admin_user
from .. import database

router = APIRouter(prefix="/api/analytics", tags=["analytics"])
logger = logging.getLogger(__name__)


# ==============================================================================
# Helper Functions
# ==============================================================================

async def sync_validation_sources_to_quality_scores(
    conn,
    validation_id: UUID,
    needs_reingestion: bool = True,
    reason: str = "Validation marked for reingestion"
):
    """
    Synchronise les sources d'une validation vers document_quality_scores.

    Cette fonction extrait tous les chunk_ids depuis sources_used (JSONB)
    et marque leurs documents respectifs pour réingestion.

    Args:
        conn: Database connection
        validation_id: UUID de la validation thumbs_down
        needs_reingestion: Marquer documents pour réingestion (défaut: True)
        reason: Raison pour l'audit log

    Returns:
        int: Nombre de documents marqués
    """
    try:
        # Extraire les chunk_ids depuis sources_used et marquer documents
        result = await conn.execute("""
            INSERT INTO document_quality_scores (
                document_id,
                needs_reingestion,
                reingestion_reason,
                updated_at
            )
            SELECT DISTINCT
                c.document_id,
                $2 AS needs_reingestion,
                $3 AS reingestion_reason,
                NOW() AS updated_at
            FROM thumbs_down_validations v
            CROSS JOIN LATERAL jsonb_array_elements(v.sources_used) as source
            JOIN chunks c ON c.id = (source->>'chunk_id')::UUID
            WHERE v.id = $1
                AND v.sources_used IS NOT NULL
                AND jsonb_typeof(v.sources_used) = 'array'

            ON CONFLICT (document_id) DO UPDATE
            SET
                needs_reingestion = EXCLUDED.needs_reingestion,
                updated_at = NOW(),
                reingestion_reason = COALESCE(
                    document_quality_scores.reingestion_reason || ' | ',
                    ''
                ) || EXCLUDED.reingestion_reason
        """, validation_id, needs_reingestion, reason)

        # Extraire le nombre de documents modifiés depuis le result status
        # Format: "INSERT 0 X" or "UPDATE X"
        status = result.split()
        count = int(status[-1]) if status else 0

        logger.info(f"✅ {count} document(s) marked for reingestion from validation {validation_id}")
        return count

    except Exception as e:
        logger.error(f"❌ Error syncing validation {validation_id} to quality scores: {e}")
        # Ne pas lever l'exception, juste logger (graceful degradation)
        return 0


@router.get("/ratings/summary")
async def get_ratings_summary(
    days: int = 30,
    current_user: dict = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """
    Résumé global des ratings avec évolution temporelle

    Métriques :
    - Taux satisfaction global
    - Distribution par reranking (avec/sans)
    - Distribution par profondeur conversation
    - Évolution temporelle (7/30 jours)
    """
    async with database.db_pool.acquire() as conn:
        # KPIs globaux
        global_stats = await conn.fetchrow("""
            SELECT
                COUNT(*) FILTER (WHERE mr.rating = 1 AND mr.is_cancelled = false) as thumbs_up,
                COUNT(*) FILTER (WHERE mr.rating = -1 AND mr.is_cancelled = false) as thumbs_down,
                COUNT(*) FILTER (WHERE mr.is_cancelled = false) as total_ratings,
                ROUND(
                    COUNT(*) FILTER (WHERE mr.rating = 1 AND mr.is_cancelled = false)::numeric /
                    NULLIF(COUNT(*) FILTER (WHERE mr.is_cancelled = false), 0)::numeric * 100, 1
                ) as satisfaction_rate,
                COUNT(DISTINCT mr.feedback) FILTER (WHERE mr.feedback IS NOT NULL AND mr.feedback != '' AND mr.is_cancelled = false) as feedback_count
            FROM message_ratings mr
            JOIN messages m ON mr.message_id = m.id
            WHERE m.role = 'assistant'
              AND mr.created_at >= NOW() - INTERVAL '%s days'
        """ % days)

        # Distribution par reranking
        reranking_stats = await conn.fetch("""
            SELECT
                c.reranking_enabled,
                COUNT(*) FILTER (WHERE mr.rating = 1 AND mr.is_cancelled = false) as thumbs_up,
                COUNT(*) FILTER (WHERE mr.rating = -1 AND mr.is_cancelled = false) as thumbs_down,
                COUNT(*) FILTER (WHERE mr.is_cancelled = false) as total_ratings,
                ROUND(
                    COUNT(*) FILTER (WHERE mr.rating = 1 AND mr.is_cancelled = false)::numeric /
                    NULLIF(COUNT(*) FILTER (WHERE mr.is_cancelled = false), 0)::numeric * 100, 1
                ) as satisfaction_rate
            FROM conversations c
            JOIN messages m ON c.id = m.conversation_id AND m.role = 'assistant'
            JOIN message_ratings mr ON m.id = mr.message_id
            WHERE mr.created_at >= NOW() - INTERVAL '%s days'
              AND mr.is_cancelled = false
            GROUP BY c.reranking_enabled
        """ % days)

        # Distribution par profondeur conversation
        depth_stats = await conn.fetch("""
            WITH message_positions AS (
                SELECT
                    m.id,
                    mr.rating,
                    mr.is_cancelled,
                    ROW_NUMBER() OVER (PARTITION BY m.conversation_id ORDER BY m.created_at) as position
                FROM messages m
                JOIN message_ratings mr ON m.id = mr.message_id
                WHERE m.role = 'assistant'
                  AND mr.created_at >= NOW() - INTERVAL '%s days'
                  AND mr.is_cancelled = false
            )
            SELECT
                CASE
                    WHEN position = 1 THEN 'Première question'
                    WHEN position <= 3 THEN 'Follow-ups 2-3'
                    ELSE 'Follow-ups profonds (4+)'
                END as depth_category,
                COUNT(*) FILTER (WHERE rating = 1) as thumbs_up,
                COUNT(*) FILTER (WHERE rating = -1) as thumbs_down,
                COUNT(*) as total_ratings,
                ROUND(
                    COUNT(*) FILTER (WHERE rating = 1)::numeric /
                    NULLIF(COUNT(*), 0)::numeric * 100, 1
                ) as satisfaction_rate
            FROM message_positions
            GROUP BY depth_category
            ORDER BY MIN(position)
        """ % days)

        # Évolution temporelle (par jour)
        temporal_stats = await conn.fetch("""
            SELECT
                DATE(mr.created_at) as date,
                COUNT(*) FILTER (WHERE mr.rating = 1 AND mr.is_cancelled = false) as thumbs_up,
                COUNT(*) FILTER (WHERE mr.rating = -1 AND mr.is_cancelled = false) as thumbs_down,
                COUNT(*) FILTER (WHERE mr.is_cancelled = false) as total_ratings,
                ROUND(
                    COUNT(*) FILTER (WHERE mr.rating = 1 AND mr.is_cancelled = false)::numeric /
                    NULLIF(COUNT(*) FILTER (WHERE mr.is_cancelled = false), 0)::numeric * 100, 1
                ) as satisfaction_rate
            FROM message_ratings mr
            JOIN messages m ON mr.message_id = m.id
            WHERE m.role = 'assistant'
              AND mr.created_at >= NOW() - INTERVAL '%s days'
            GROUP BY DATE(mr.created_at)
            ORDER BY date DESC
        """ % days)

        return {
            "period_days": days,
            "global": dict(global_stats) if global_stats else {},
            "by_reranking": [dict(row) for row in reranking_stats],
            "by_depth": [dict(row) for row in depth_stats],
            "temporal": [dict(row) for row in temporal_stats]
        }


@router.get("/ratings/worst-chunks")
async def get_worst_chunks(
    limit: int = 10,
    min_appearances: int = 3,
    current_user: dict = Depends(get_current_admin_user)
) -> List[Dict[str, Any]]:
    """
    Top chunks avec le plus mauvais taux de satisfaction

    Critères :
    - Minimum X apparitions (significativité statistique)
    - Score impact = (thumbs_down / apparitions) × apparitions
    - Affiche contexte document (titre, section, page)
    """
    async with database.db_pool.acquire() as conn:
        results = await conn.fetch("""
            WITH rated_chunks AS (
                SELECT
                    m.id as message_id,
                    jsonb_array_elements(m.sources) as source,
                    mr.rating
                FROM messages m
                JOIN message_ratings mr ON m.id = mr.message_id
                WHERE m.role = 'assistant' AND m.sources IS NOT NULL
                  AND mr.is_cancelled = false
            ),
            chunk_scores AS (
                SELECT
                    (source->>'chunk_id')::uuid as chunk_id,
                    COUNT(*) FILTER (WHERE rating = 1) as thumbs_up,
                    COUNT(*) FILTER (WHERE rating = -1) as thumbs_down,
                    COUNT(*) as total_appearances
                FROM rated_chunks
                WHERE source->>'chunk_id' IS NOT NULL
                GROUP BY chunk_id
            )
            SELECT
                cs.chunk_id,
                SUBSTRING(c.content, 1, 200) as content_preview,
                c.document_id,
                d.title as document_title,
                d.source as document_source,
                c.metadata->>'section_hierarchy' as section,
                c.metadata->>'page_number' as page_number,
                c.metadata->>'heading_context' as heading,
                cs.thumbs_up,
                cs.thumbs_down,
                cs.total_appearances,
                ROUND(cs.thumbs_down::numeric / NULLIF(cs.total_appearances, 0), 2) as dissatisfaction_rate,
                cs.thumbs_down * cs.total_appearances as impact_score
            FROM chunk_scores cs
            JOIN chunks c ON cs.chunk_id = c.id
            JOIN documents d ON c.document_id = d.id
            WHERE cs.total_appearances >= $1
            ORDER BY impact_score DESC
            LIMIT $2
        """, min_appearances, limit)

        return [dict(row) for row in results]


@router.get("/ratings/worst-documents")
async def get_worst_documents(
    limit: int = 10,
    min_appearances: int = 5,
    current_user: dict = Depends(get_current_admin_user)
) -> List[Dict[str, Any]]:
    """
    Documents avec le taux de satisfaction le plus bas

    Agrège satisfaction de tous les chunks d'un document
    Suggère documents prioritaires pour réingestion
    """
    async with database.db_pool.acquire() as conn:
        results = await conn.fetch("""
            WITH rated_chunks AS (
                SELECT
                    m.id as message_id,
                    jsonb_array_elements(m.sources) as source,
                    mr.rating
                FROM messages m
                JOIN message_ratings mr ON m.id = mr.message_id
                WHERE m.role = 'assistant' AND m.sources IS NOT NULL
                  AND mr.is_cancelled = false
            ),
            chunk_scores AS (
                SELECT
                    (source->>'chunk_id')::uuid as chunk_id,
                    COUNT(*) FILTER (WHERE rating = 1) as thumbs_up,
                    COUNT(*) FILTER (WHERE rating = -1) as thumbs_down,
                    COUNT(*) as total_appearances
                FROM rated_chunks
                WHERE source->>'chunk_id' IS NOT NULL
                GROUP BY chunk_id
            ),
            document_scores AS (
                SELECT
                    c.document_id,
                    SUM(cs.thumbs_up) as doc_thumbs_up,
                    SUM(cs.thumbs_down) as doc_thumbs_down,
                    SUM(cs.total_appearances) as doc_total_appearances,
                    COUNT(DISTINCT c.id) as chunks_with_ratings
                FROM chunk_scores cs
                JOIN chunks c ON cs.chunk_id = c.id
                GROUP BY c.document_id
            )
            SELECT
                ds.document_id,
                d.title,
                d.source,
                d.created_at,
                ds.doc_thumbs_up as thumbs_up,
                ds.doc_thumbs_down as thumbs_down,
                ds.doc_total_appearances as total_appearances,
                ds.chunks_with_ratings,
                (SELECT COUNT(*) FROM chunks WHERE document_id = ds.document_id) as total_chunks,
                ROUND(
                    ds.doc_thumbs_up::numeric /
                    NULLIF((ds.doc_thumbs_up + ds.doc_thumbs_down), 0)::numeric * 100, 1
                ) as satisfaction_rate,
                ROUND(
                    ds.chunks_with_ratings::numeric /
                    (SELECT COUNT(*) FROM chunks WHERE document_id = ds.document_id)::numeric * 100, 1
                ) as coverage_rate
            FROM document_scores ds
            JOIN documents d ON ds.document_id = d.id
            WHERE ds.doc_total_appearances >= $1
            ORDER BY satisfaction_rate ASC NULLS LAST
            LIMIT $2
        """, min_appearances, limit)

        return [dict(row) for row in results]


@router.get("/ratings/by-reranking")
async def get_ratings_by_reranking(
    days: int = 30,
    current_user: dict = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """
    Comparaison détaillée satisfaction avec/sans reranking

    Permet de mesurer l'impact réel du reranking sur la qualité
    Inclut métriques : satisfaction, latence, taux feedback
    """
    async with database.db_pool.acquire() as conn:
        # Stats détaillées par reranking
        stats = await conn.fetch("""
            SELECT
                c.reranking_enabled,
                COUNT(DISTINCT c.id) as conversation_count,
                COUNT(DISTINCT m.id) as message_count,
                COUNT(*) FILTER (WHERE mr.rating = 1 AND mr.is_cancelled = false) as thumbs_up,
                COUNT(*) FILTER (WHERE mr.rating = -1 AND mr.is_cancelled = false) as thumbs_down,
                COUNT(*) FILTER (WHERE mr.is_cancelled = false) as total_ratings,
                ROUND(
                    COUNT(*) FILTER (WHERE mr.rating = 1 AND mr.is_cancelled = false)::numeric /
                    NULLIF(COUNT(*) FILTER (WHERE mr.is_cancelled = false), 0)::numeric * 100, 1
                ) as satisfaction_rate,
                COUNT(DISTINCT mr.feedback) FILTER (WHERE mr.feedback IS NOT NULL AND mr.feedback != '' AND mr.is_cancelled = false) as feedback_count,
                ROUND(
                    COUNT(DISTINCT mr.feedback) FILTER (WHERE mr.feedback IS NOT NULL AND mr.feedback != '' AND mr.is_cancelled = false)::numeric /
                    NULLIF(COUNT(*) FILTER (WHERE mr.is_cancelled = false), 0)::numeric * 100, 1
                ) as feedback_ratio
            FROM conversations c
            JOIN messages m ON c.id = m.conversation_id AND m.role = 'assistant'
            JOIN message_ratings mr ON m.id = mr.message_id
            WHERE mr.created_at >= NOW() - INTERVAL '%s days'
              AND mr.is_cancelled = false
            GROUP BY c.reranking_enabled
            ORDER BY c.reranking_enabled DESC
        """ % days)

        # Calculer différence
        stats_list = [dict(row) for row in stats]

        with_reranking = next((s for s in stats_list if s['reranking_enabled']), None)
        without_reranking = next((s for s in stats_list if not s['reranking_enabled']), None)

        impact = None
        if with_reranking and without_reranking:
            impact = {
                "satisfaction_diff": round(
                    (with_reranking['satisfaction_rate'] or 0) - (without_reranking['satisfaction_rate'] or 0), 1
                ),
                "message_count_diff": with_reranking['message_count'] - without_reranking['message_count'],
                "recommendation": (
                    "Activer reranking par défaut (+{:.1f}% satisfaction)".format(
                        (with_reranking['satisfaction_rate'] or 0) - (without_reranking['satisfaction_rate'] or 0)
                    ) if (with_reranking['satisfaction_rate'] or 0) > (without_reranking['satisfaction_rate'] or 0)
                    else "Reranking n'améliore pas significativement"
                )
            }

        return {
            "period_days": days,
            "stats": stats_list,
            "impact": impact
        }


@router.get("/ratings/with-feedback")
async def get_ratings_with_feedback(
    limit: int = 50,
    rating_value: Optional[int] = None,  # -1 pour thumbs down uniquement
    current_user: dict = Depends(get_current_admin_user)
) -> List[Dict[str, Any]]:
    """
    Liste des messages avec ratings + feedback textuel

    Permet analyse qualitative des problèmes
    Filtrable par type de rating (thumbs down par défaut)
    """
    async with database.db_pool.acquire() as conn:
        query = """
            WITH user_messages AS (
                SELECT
                    conversation_id,
                    id as user_message_id,
                    content as user_content,
                    created_at
                FROM messages
                WHERE role = 'user'
            ),
            assistant_messages AS (
                SELECT
                    m.id,
                    m.conversation_id,
                    m.content,
                    m.sources,
                    m.created_at,
                    mr.rating,
                    mr.feedback,
                    mr.created_at as rating_created_at
                FROM messages m
                JOIN message_ratings mr ON m.id = mr.message_id
                WHERE m.role = 'assistant'
                  AND mr.feedback IS NOT NULL
                  AND mr.feedback != ''
                  AND mr.is_cancelled = false
        """

        params = []
        if rating_value is not None:
            query += " AND mr.rating = $1"
            params.append(rating_value)

        query += """
            ORDER BY mr.created_at DESC
            LIMIT ${}
        """.format(len(params) + 1)
        params.append(limit)

        query += """
            )
            SELECT
                am.id as message_id,
                c.id as conversation_id,
                c.title as conversation_title,
                um.user_content as question,
                SUBSTRING(am.content, 1, 500) as answer_preview,
                am.sources,
                am.rating,
                am.feedback,
                am.created_at as message_date,
                am.rating_created_at as rating_date
            FROM assistant_messages am
            JOIN conversations c ON am.conversation_id = c.id
            LEFT JOIN user_messages um ON am.conversation_id = um.conversation_id
                AND um.created_at < am.created_at
                AND um.created_at >= am.created_at - INTERVAL '5 minutes'
        """

        results = await conn.fetch(query, *params)

        return [dict(row) for row in results]


# ============================================================================
# QUALITY MANAGEMENT ENDPOINTS (Quick Win #4)
# ============================================================================

@router.get("/quality/blacklisted-chunks")
async def get_blacklisted_chunks(
    limit: int = 50,
    current_user: dict = Depends(get_current_admin_user)
) -> List[Dict[str, Any]]:
    """
    Liste des chunks blacklistés avec contexte complet

    Inclut : contenu, statistiques, raison IA, et actions disponibles
    """
    async with database.db_pool.acquire() as conn:
        results = await conn.fetch("""
            SELECT
                cqs.chunk_id,
                SUBSTRING(c.content, 1, 300) as content_preview,
                c.content as full_content,
                c.document_id,
                d.title as document_title,
                d.source as document_source,
                c.metadata->>'section_hierarchy' as section,
                c.metadata->>'page_number' as page_number,
                cqs.thumbs_up_count,
                cqs.thumbs_down_count,
                cqs.total_appearances,
                cqs.satisfaction_rate,
                cqs.blacklist_reason,
                cqs.is_whitelisted,
                cqs.updated_at,
                -- Dernière analyse IA
                (
                    SELECT qa.ai_analysis
                    FROM quality_audit_log qa
                    WHERE qa.chunk_id = cqs.chunk_id
                      AND qa.action IN ('blacklist', 'analyze')
                    ORDER BY qa.created_at DESC
                    LIMIT 1
                ) as last_ai_analysis
            FROM chunk_quality_scores cqs
            JOIN chunks c ON cqs.chunk_id = c.id
            JOIN documents d ON c.document_id = d.id
            WHERE cqs.is_blacklisted = true
            ORDER BY cqs.updated_at DESC
            LIMIT $1
        """, limit)

        return [dict(row) for row in results]


@router.get("/quality/reingestion-recommendations")
async def get_reingestion_recommendations(
    limit: int = 20,
    current_user: dict = Depends(get_current_admin_user)
) -> List[Dict[str, Any]]:
    """
    Documents recommandés pour réingestion par l'IA

    Inclut : statistiques, recommandations Chocolatine, actions
    """
    async with database.db_pool.acquire() as conn:
        results = await conn.fetch("""
            SELECT
                dqs.document_id,
                d.title,
                d.source,
                d.created_at as ingestion_date,
                dqs.thumbs_up_count,
                dqs.thumbs_down_count,
                dqs.total_appearances,
                dqs.satisfaction_rate,
                dqs.reingestion_reason,
                dqs.updated_at,
                -- Nombre de chunks problématiques
                (
                    SELECT COUNT(*)
                    FROM chunks c
                    JOIN chunk_quality_scores cqs ON c.id = cqs.chunk_id
                    WHERE c.document_id = dqs.document_id
                      AND cqs.is_blacklisted = true
                ) as blacklisted_chunks_count,
                -- Dernière analyse IA
                (
                    SELECT qa.ai_analysis
                    FROM quality_audit_log qa
                    WHERE qa.document_id = dqs.document_id
                      AND qa.action IN ('recommend_reingestion', 'document_analysis')
                    ORDER BY qa.created_at DESC
                    LIMIT 1
                ) as last_ai_analysis
            FROM document_quality_scores dqs
            JOIN documents d ON dqs.document_id = d.id
            WHERE dqs.needs_reingestion = true
            ORDER BY dqs.satisfaction_rate ASC, dqs.updated_at DESC
            LIMIT $1
        """, limit)

        return [dict(row) for row in results]


@router.get("/quality/audit-log")
async def get_quality_audit_log(
    limit: int = 100,
    action: Optional[str] = None,
    current_user: dict = Depends(get_current_admin_user)
) -> List[Dict[str, Any]]:
    """
    Historique complet des décisions qualité (IA + humain)

    Filtrable par type d'action
    """
    async with database.db_pool.acquire() as conn:
        query = """
            SELECT
                qa.id,
                qa.chunk_id,
                qa.document_id,
                qa.action,
                qa.reason,
                qa.decided_by,
                qa.ai_analysis,
                qa.created_at,
                -- Contexte chunk si disponible
                CASE WHEN qa.chunk_id IS NOT NULL THEN
                    (SELECT SUBSTRING(c.content, 1, 200) FROM chunks c WHERE c.id = qa.chunk_id)
                END as chunk_preview,
                -- Contexte document si disponible
                CASE WHEN qa.document_id IS NOT NULL THEN
                    (SELECT d.title FROM documents d WHERE d.id = qa.document_id)
                END as document_title
            FROM quality_audit_log qa
        """

        params = []
        if action:
            query += " WHERE qa.action = $1"
            params.append(action)

        query += " ORDER BY qa.created_at DESC LIMIT $" + str(len(params) + 1)
        params.append(limit)

        results = await conn.fetch(query, *params)

        return [dict(row) for row in results]


@router.post("/quality/chunk/{chunk_id}/unblacklist")
async def unblacklist_chunk(
    chunk_id: UUID,
    reason: str = Body(..., embed=True),
    current_user: dict = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """
    Déblacklister un chunk (décision admin)

    Réactive le chunk dans les recherches RAG
    """
    async with database.db_pool.acquire() as conn:
        # Vérifier que le chunk existe et est blacklisté
        chunk = await conn.fetchrow("""
            SELECT cqs.chunk_id, cqs.is_blacklisted
            FROM chunk_quality_scores cqs
            WHERE cqs.chunk_id = $1
        """, chunk_id)

        if not chunk:
            raise HTTPException(status_code=404, detail="Chunk not found in quality scores")

        if not chunk['is_blacklisted']:
            raise HTTPException(status_code=400, detail="Chunk is not blacklisted")

        # Déblacklister
        await conn.execute("""
            UPDATE chunk_quality_scores
            SET is_blacklisted = false,
                blacklist_reason = NULL,
                updated_at = NOW()
            WHERE chunk_id = $1
        """, chunk_id)

        # Logger dans audit log
        await conn.execute("""
            INSERT INTO quality_audit_log
            (id, chunk_id, action, reason, decided_by, created_at)
            VALUES ($1, $2, 'unblacklist', $3, $4, NOW())
        """, str(uuid4()), str(chunk_id), reason, current_user['id'])

        logger.info(f"🔓 Chunk {chunk_id} unblacklisted by admin {current_user['username']}")

        return {
            "success": True,
            "message": "Chunk déblacklisté avec succès",
            "chunk_id": str(chunk_id)
        }


@router.post("/quality/chunk/{chunk_id}/whitelist")
async def whitelist_chunk(
    chunk_id: UUID,
    reason: str = Body(..., embed=True),
    current_user: dict = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """
    Whitelister un chunk (protection permanente)

    Empêche l'IA de le blacklister automatiquement
    """
    async with database.db_pool.acquire() as conn:
        # Vérifier que le chunk existe
        chunk = await conn.fetchrow("""
            SELECT chunk_id FROM chunk_quality_scores WHERE chunk_id = $1
        """, chunk_id)

        if not chunk:
            # Créer l'entrée si elle n'existe pas
            await conn.execute("""
                INSERT INTO chunk_quality_scores
                (chunk_id, is_whitelisted, updated_at)
                VALUES ($1, true, NOW())
            """, chunk_id)
        else:
            # Whitelister (et déblacklister si nécessaire)
            await conn.execute("""
                UPDATE chunk_quality_scores
                SET is_whitelisted = true,
                    is_blacklisted = false,
                    blacklist_reason = NULL,
                    updated_at = NOW()
                WHERE chunk_id = $1
            """, chunk_id)

        # Logger dans audit log
        await conn.execute("""
            INSERT INTO quality_audit_log
            (id, chunk_id, action, reason, decided_by, created_at)
            VALUES ($1, $2, 'whitelist', $3, $4, NOW())
        """, str(uuid4()), str(chunk_id), reason, current_user['id'])

        logger.info(f"⭐ Chunk {chunk_id} whitelisted by admin {current_user['username']}")

        return {
            "success": True,
            "message": "Chunk whitelisté (protégé contre blacklist automatique)",
            "chunk_id": str(chunk_id)
        }


@router.post("/quality/document/{document_id}/ignore-recommendation")
async def ignore_reingestion_recommendation(
    document_id: UUID,
    reason: str = Body(..., embed=True),
    current_user: dict = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """
    Ignorer une recommandation de réingestion (décision admin)

    Marque la recommandation comme traitée/ignorée
    """
    async with database.db_pool.acquire() as conn:
        # Vérifier que le document existe et a une recommandation
        doc = await conn.fetchrow("""
            SELECT document_id, needs_reingestion
            FROM document_quality_scores
            WHERE document_id = $1
        """, document_id)

        if not doc:
            raise HTTPException(status_code=404, detail="Document not found in quality scores")

        if not doc['needs_reingestion']:
            raise HTTPException(status_code=400, detail="Document has no reingestion recommendation")

        # Marquer comme ignoré
        await conn.execute("""
            UPDATE document_quality_scores
            SET needs_reingestion = false,
                reingestion_reason = NULL,
                updated_at = NOW()
            WHERE document_id = $1
        """, document_id)

        # Logger dans audit log
        await conn.execute("""
            INSERT INTO quality_audit_log
            (id, document_id, action, reason, decided_by, created_at)
            VALUES ($1, $2, 'ignore_recommendation', $3, $4, NOW())
        """, str(uuid4()), str(document_id), reason, current_user['id'])

        logger.info(f"❌ Reingestion recommendation ignored for document {document_id} by admin {current_user['username']}")

        return {
            "success": True,
            "message": "Recommandation de réingestion ignorée",
            "document_id": str(document_id)
        }


@router.post("/quality/trigger-analysis")
async def trigger_manual_analysis(
    current_user: dict = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """
    Déclencher une analyse qualité manuellement (ne pas attendre le cron)

    Crée un job pending qui sera détecté par analytics-worker
    """
    run_id = str(uuid4())

    # Créer l'entrée analysis_runs avec status='pending'
    # Le analytics-worker va le détecter et exécuter l'analyse
    async with database.db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO analysis_runs
            (id, status, progress, started_by, started_at)
            VALUES ($1, 'pending', 0, $2, NOW())
        """, run_id, str(current_user['id']))

    logger.info(f"🚀 Manual analysis job created by admin {current_user['username']} (run_id={run_id})")

    return {
        "success": True,
        "message": "Analyse qualité programmée - le worker va la démarrer dans quelques secondes",
        "run_id": run_id
    }


@router.get("/quality/analysis-status/{run_id}")
async def get_analysis_status(
    run_id: UUID,
    current_user: dict = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """
    Récupérer le statut d'une analyse en cours (pour polling frontend)

    Renvoie : status, progress, résultats partiels
    """
    async with database.db_pool.acquire() as conn:
        analysis = await conn.fetchrow("""
            SELECT
                id,
                status,
                progress,
                started_by,
                started_at,
                completed_at,
                duration_seconds,
                chunks_analyzed,
                chunks_blacklisted,
                documents_flagged,
                error_message
            FROM analysis_runs
            WHERE id = $1
        """, run_id)

        if not analysis:
            raise HTTPException(status_code=404, detail="Analysis run not found")

        return dict(analysis)


@router.get("/quality/analysis-history")
async def get_analysis_history(
    limit: int = 50,
    current_user: dict = Depends(get_current_admin_user)
) -> List[Dict[str, Any]]:
    """
    Historique des analyses qualité (auto + manuelles)

    Affiche : date, déclencheur, durée, résultats, statut
    """
    async with database.db_pool.acquire() as conn:
        results = await conn.fetch("""
            SELECT
                ar.id,
                ar.status,
                ar.progress,
                ar.started_by,
                ar.started_at,
                ar.completed_at,
                ar.duration_seconds,
                ar.chunks_analyzed,
                ar.chunks_blacklisted,
                ar.documents_flagged,
                ar.error_message,
                CASE
                    WHEN ar.started_by = 'cron' THEN 'Automatique (3h)'
                    ELSE 'Manuel'
                END as run_type,
                CASE
                    WHEN ar.status = 'completed' THEN 'Terminé'
                    WHEN ar.status = 'failed' THEN 'Échoué'
                    ELSE 'En cours'
                END as status_label
            FROM analysis_runs ar
            ORDER BY ar.started_at DESC
            LIMIT $1
        """, limit)

        return [dict(row) for row in results]


@router.get("/quality/reingestion-count")
async def get_reingestion_count(
    current_user: dict = Depends(get_current_admin_user)
) -> Dict[str, int]:
    """
    Nombre de documents à réingérer (pour badge notification)
    """
    async with database.db_pool.acquire() as conn:
        count = await conn.fetchval("""
            SELECT COUNT(*)
            FROM document_quality_scores
            WHERE needs_reingestion = true
        """)

        return {"count": count or 0}


# ============================================================================
# Thumbs Down Validation Routes
# ============================================================================

@router.get("/thumbs-down/pending-review")
async def get_pending_thumbs_down_validations(
    current_user: dict = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """
    Liste des thumbs down nécessitant révision admin (confidence < 0.7 ou unrealistic_expectations)
    """
    async with database.db_pool.acquire() as conn:
        validations = await conn.fetch("""
            SELECT
                v.id,
                v.message_id,
                v.user_id,
                v.user_question,
                v.assistant_response,
                v.sources_used,
                v.user_feedback,
                v.ai_classification,
                v.ai_confidence,
                v.ai_reasoning,
                v.suggested_reformulation,
                v.missing_info_details,
                v.needs_admin_review,
                v.created_at,
                u.username,
                u.email as user_email,
                u.first_name,
                u.last_name
            FROM thumbs_down_validations v
            JOIN users u ON v.user_id = u.id
            JOIN message_ratings mr ON v.rating_id = mr.id
            WHERE v.needs_admin_review = true
              AND v.validated_at IS NULL
              AND mr.is_cancelled = false
            ORDER BY v.created_at DESC
        """)

        return {
            "pending_validations": [dict(row) for row in validations],
            "count": len(validations)
        }


@router.get("/thumbs-down/all")
async def get_all_thumbs_down_validations(
    classification: Optional[str] = None,
    needs_review: Optional[bool] = None,
    admin_action: Optional[str] = None,
    validated: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: dict = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """
    Liste complète des thumbs down avec filtres avancés

    Filtres :
    - classification: bad_question | bad_answer | missing_sources | unrealistic_expectations
    - needs_review: true/false
    - admin_action: contact_user | mark_for_reingestion | ignore | pending
    - validated: true/false (si admin a validé)
    - limit/offset: pagination
    """
    async with database.db_pool.acquire() as conn:
        # Construction dynamique de la requête avec filtres
        conditions = []
        params = []
        param_count = 0

        if classification:
            param_count += 1
            conditions.append(f"(v.admin_override = ${param_count} OR (v.admin_override IS NULL AND v.ai_classification = ${param_count}))")
            params.append(classification)

        if needs_review is not None:
            param_count += 1
            conditions.append(f"v.needs_admin_review = ${param_count}")
            params.append(needs_review)

        if admin_action:
            param_count += 1
            conditions.append(f"v.admin_action = ${param_count}")
            params.append(admin_action)

        if validated is not None:
            if validated:
                conditions.append("v.validated_at IS NOT NULL")
            else:
                conditions.append("v.validated_at IS NULL")

        # Toujours exclure les ratings annulés
        conditions.append("mr.is_cancelled = false")

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        # Ajouter limit et offset
        param_count += 1
        limit_param = f"${param_count}"
        params.append(limit)
        param_count += 1
        offset_param = f"${param_count}"
        params.append(offset)

        query = f"""
            SELECT
                v.id,
                v.message_id,
                v.user_id,
                v.user_question,
                v.assistant_response,
                v.sources_used,
                v.user_feedback,
                v.ai_classification,
                v.ai_confidence,
                v.ai_reasoning,
                v.suggested_reformulation,
                v.missing_info_details,
                v.needs_admin_review,
                v.admin_override,
                COALESCE(v.admin_override, v.ai_classification) as final_classification,
                v.admin_notes,
                v.admin_action,
                v.validated_by,
                v.validated_at,
                v.created_at,
                u.username,
                u.email as user_email,
                u.first_name,
                u.last_name,
                validator.username as validated_by_username
            FROM thumbs_down_validations v
            JOIN users u ON v.user_id = u.id
            JOIN message_ratings mr ON v.rating_id = mr.id
            LEFT JOIN users validator ON v.validated_by = validator.id
            {where_clause}
            ORDER BY v.created_at DESC
            LIMIT {limit_param} OFFSET {offset_param}
        """

        validations = await conn.fetch(query, *params)

        # Count total pour pagination
        count_query = f"""
            SELECT COUNT(*)
            FROM thumbs_down_validations v
            JOIN message_ratings mr ON v.rating_id = mr.id
            {where_clause}
        """
        total_count = await conn.fetchval(count_query, *params[:-2])  # Exclure limit/offset

        return {
            "validations": [dict(row) for row in validations],
            "total_count": total_count,
            "page_size": limit,
            "offset": offset
        }


@router.post("/thumbs-down/{validation_id}/validate")
async def validate_thumbs_down(
    validation_id: UUID,
    admin_override: Optional[str] = None,
    admin_notes: Optional[str] = None,
    admin_action: str = "pending",
    current_user: dict = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """
    Admin valide/modifie la classification d'un thumbs down

    Body params:
    - admin_override: bad_question | bad_answer | missing_sources | unrealistic_expectations (optionnel)
    - admin_notes: Notes de l'admin (optionnel)
    - admin_action: contact_user | mark_for_reingestion | ignore | pending
    """
    async with database.db_pool.acquire() as conn:
        # Mettre à jour la validation
        result = await conn.fetchrow("""
            UPDATE thumbs_down_validations
            SET admin_override = $1,
                admin_notes = $2,
                admin_action = $3,
                validated_by = $4,
                validated_at = CURRENT_TIMESTAMP
            WHERE id = $5
            RETURNING *
        """, admin_override, admin_notes, admin_action, current_user['id'], validation_id)

        if not result:
            raise HTTPException(status_code=404, detail="Validation not found")

        # Déclencher actions automatiques selon admin_action
        from ..services.user_accompaniment import UserAccompanimentService
        accompaniment = UserAccompanimentService(database.db_pool)

        if admin_action == "contact_user":
            # Créer notification pour l'utilisateur
            await accompaniment.create_question_improvement_notification(validation_id)
            logger.info(f"✅ Notification created for validation {validation_id}")

        elif admin_action == "mark_for_reingestion":
            # Synchroniser vers document_quality_scores
            classification = admin_override or result['ai_classification']
            reason = f"Admin validated as {classification} - marked for reingestion"

            count = await sync_validation_sources_to_quality_scores(
                conn,
                validation_id,
                needs_reingestion=True,
                reason=reason
            )

            if count == 0:
                logger.warning(f"⚠️ No documents found to mark for reingestion from validation {validation_id}")
            else:
                logger.info(f"✅ {count} document(s) marked for reingestion from validation {validation_id}")

        return {"success": True, "validation": dict(result)}


@router.get("/thumbs-down/validation/{validation_id}")
async def get_thumbs_down_validation(
    validation_id: UUID,
    current_user: dict = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """
    Récupère une validation thumbs down par son ID avec tous les détails
    """
    async with database.db_pool.acquire() as conn:
        validation = await conn.fetchrow("""
            SELECT
                v.*,
                u.username,
                u.email as user_email,
                u.first_name,
                u.last_name,
                m.content as message_content
            FROM thumbs_down_validations v
            JOIN users u ON v.user_id = u.id
            LEFT JOIN messages m ON v.message_id = m.id
            WHERE v.id = $1
        """, validation_id)

        if not validation:
            raise HTTPException(status_code=404, detail="Validation not found")

        result = dict(validation)

        # Normaliser sources_used: toujours un array ou null
        if result.get('sources_used'):
            sources = result['sources_used']
            if isinstance(sources, str):
                # String JSON → parsé en Python
                import json
                try:
                    sources = json.loads(sources)
                except (json.JSONDecodeError, TypeError):
                    sources = []  # Fallback sur erreur

            # Assurer que c'est une liste
            if isinstance(sources, list):
                result['sources_used'] = sources
            else:
                result['sources_used'] = []  # Fallback pour dict ou autre type
        else:
            result['sources_used'] = None  # Explicite

        return result


@router.post("/thumbs-down/{validation_id}/cancel")
async def cancel_thumbs_down(
    validation_id: UUID,
    request: Dict[str, str],
    current_user: dict = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """
    Annuler un thumbs down (décision admin)

    Marque le rating comme annulé (soft delete) avec traçabilité complète.
    Le rating et la validation restent en base mais sont exclus des statistiques.

    Body params:
    - cancellation_reason: Raison de l'annulation (obligatoire, ex: "Question mal formulée par utilisateur")

    Returns:
    - success: Boolean
    - message: Confirmation message
    - validation_id: UUID de la validation
    - rating_id: UUID du rating annulé
    - cancelled_by: Username de l'admin
    """
    cancellation_reason = request.get("cancellation_reason", "").strip()

    if not cancellation_reason:
        raise HTTPException(
            status_code=422,
            detail="cancellation_reason is required"
        )

    async with database.db_pool.acquire() as conn:
        # Vérifier que la validation existe et récupérer le rating_id
        validation = await conn.fetchrow("""
            SELECT v.id, v.rating_id, v.message_id, v.user_question, v.user_id
            FROM thumbs_down_validations v
            WHERE v.id = $1
        """, validation_id)

        if not validation:
            raise HTTPException(status_code=404, detail="Validation not found")

        # Vérifier que le rating existe et n'est pas déjà annulé
        rating = await conn.fetchrow("""
            SELECT id, is_cancelled, rating
            FROM message_ratings
            WHERE id = $1
        """, validation['rating_id'])

        if not rating:
            raise HTTPException(status_code=404, detail="Rating not found")

        if rating['is_cancelled']:
            raise HTTPException(
                status_code=400,
                detail="This thumbs down is already cancelled"
            )

        # Marquer le rating comme annulé avec métadonnées audit
        await conn.execute("""
            UPDATE message_ratings
            SET is_cancelled = true,
                cancelled_by = $1,
                cancelled_at = CURRENT_TIMESTAMP,
                cancellation_reason = $2
            WHERE id = $3
        """, current_user['id'], cancellation_reason, validation['rating_id'])

        logger.info(
            f"🚫 Thumbs down cancelled by admin {current_user['username']}: "
            f"rating_id={validation['rating_id']}, validation_id={validation_id}, "
            f"user_id={validation['user_id']}, "
            f"reason='{cancellation_reason}'"
        )

        return {
            "success": True,
            "message": "Thumbs down annulé avec succès",
            "validation_id": str(validation_id),
            "rating_id": str(validation['rating_id']),
            "cancelled_by": current_user['username']
        }


@router.get("/thumbs-down/users-to-contact")
async def get_users_to_contact(
    current_user: dict = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """
    Liste des utilisateurs à accompagner (bad_question avec admin_action=contact_user)
    """
    async with database.db_pool.acquire() as conn:
        users = await conn.fetch("""
            SELECT
                u.id as user_id,
                u.username,
                u.email,
                u.first_name,
                u.last_name,
                COUNT(v.id) as bad_questions_count,
                ARRAY_AGG(v.user_question ORDER BY v.created_at DESC) as recent_questions,
                MAX(v.created_at) as last_bad_question_date,
                ARRAY_AGG(v.id ORDER BY v.created_at DESC) as validation_ids
            FROM thumbs_down_validations v
            JOIN users u ON v.user_id = u.id
            JOIN message_ratings mr ON v.rating_id = mr.id
            WHERE (v.admin_override = 'bad_question' OR
                   (v.admin_override IS NULL AND v.ai_classification = 'bad_question'))
              AND v.admin_action = 'contact_user'
              AND mr.is_cancelled = false
            GROUP BY u.id, u.username, u.email, u.first_name, u.last_name
            ORDER BY bad_questions_count DESC, last_bad_question_date DESC
        """)

        return {
            "users_to_contact": [dict(row) for row in users],
            "total_users": len(users)
        }


@router.get("/thumbs-down/reingestion-candidates")
async def get_reingestion_candidates(
    current_user: dict = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """
    Documents à réingérer basés sur validations missing_sources
    """
    async with database.db_pool.acquire() as conn:
        documents = await conn.fetch("""
            SELECT
                d.id as document_id,
                d.title as document_title,
                d.source,
                COUNT(DISTINCT v.id) as occurrences_count,
                MAX(v.created_at) as last_occurrence,
                ARRAY_AGG(DISTINCT c.id) as chunk_ids,
                ARRAY_AGG(DISTINCT v.user_question) as user_questions
            FROM thumbs_down_validations v
            JOIN message_ratings mr ON v.rating_id = mr.id
            CROSS JOIN LATERAL jsonb_array_elements(v.sources_used) as source
            JOIN chunks c ON c.id = (source->>'chunk_id')::UUID
            JOIN documents d ON c.document_id = d.id
            WHERE (v.admin_override = 'missing_sources' OR
                   (v.admin_override IS NULL AND v.ai_classification = 'missing_sources'))
              AND v.admin_action = 'mark_for_reingestion'
              AND mr.is_cancelled = false
            GROUP BY d.id, d.title, d.source
            ORDER BY occurrences_count DESC, last_occurrence DESC
        """)

        return {
            "documents": [dict(row) for row in documents],
            "total_documents": len(documents)
        }


@router.get("/thumbs-down/stats")
async def get_thumbs_down_stats(
    current_user: dict = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """
    Statistiques globales pour dashboard thumbs down
    """
    async with database.db_pool.acquire() as conn:
        stats = await conn.fetchrow("""
            SELECT
                COUNT(*) as total_thumbs_down,
                COUNT(*) FILTER (WHERE v.needs_admin_review = true AND v.validated_at IS NULL) as pending_review,
                COUNT(*) FILTER (WHERE v.ai_classification = 'bad_question' OR v.admin_override = 'bad_question') as bad_questions,
                COUNT(*) FILTER (WHERE v.ai_classification = 'bad_answer' OR v.admin_override = 'bad_answer') as bad_answers,
                COUNT(*) FILTER (WHERE v.ai_classification = 'missing_sources' OR v.admin_override = 'missing_sources') as missing_sources,
                COUNT(*) FILTER (WHERE v.ai_classification = 'unrealistic_expectations' OR v.admin_override = 'unrealistic_expectations') as unrealistic_expectations,
                AVG(v.ai_confidence) as avg_confidence,
                COUNT(*) FILTER (WHERE v.admin_override IS NOT NULL) as admin_overrides,
                COUNT(*) FILTER (WHERE v.admin_action = 'contact_user') as users_to_contact,
                COUNT(*) FILTER (WHERE v.admin_action = 'mark_for_reingestion') as documents_to_reingest
            FROM thumbs_down_validations v
            JOIN message_ratings mr ON v.rating_id = mr.id
            WHERE mr.is_cancelled = false
        """)

        # Distribution temporelle (7 derniers jours)
        temporal_distribution = await conn.fetch("""
            SELECT
                DATE(v.created_at) as date,
                COUNT(*) as count,
                AVG(v.ai_confidence) as avg_confidence
            FROM thumbs_down_validations v
            JOIN message_ratings mr ON v.rating_id = mr.id
            WHERE v.created_at >= CURRENT_DATE - INTERVAL '7 days'
              AND mr.is_cancelled = false
            GROUP BY DATE(v.created_at)
            ORDER BY date DESC
        """)

        return {
            "summary": dict(stats) if stats else {},
            "temporal_distribution": [dict(row) for row in temporal_distribution]
        }


@router.post("/thumbs-down/analyze")
async def trigger_thumbs_down_analysis(
    rating_id: UUID,
    current_user: dict = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """
    Déclenche manuellement une analyse IA d'un thumbs down (re-analyse)
    """
    from ..services.thumbs_down_analyzer import ThumbsDownAnalyzer

    analyzer = ThumbsDownAnalyzer(database.db_pool)

    try:
        result = await analyzer.analyze_thumbs_down(rating_id)
        return {"success": True, "result": result}
    except Exception as e:
        logger.error(f"Error analyzing thumbs down {rating_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
