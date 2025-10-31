"""
Routes pour l'analytics et l'amélioration continue du RAG via ratings utilisateurs
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging

from ..auth import get_current_admin_user
from .. import database

router = APIRouter(prefix="/api/analytics", tags=["analytics"])
logger = logging.getLogger(__name__)


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
                COUNT(*) FILTER (WHERE mr.rating = 1) as thumbs_up,
                COUNT(*) FILTER (WHERE mr.rating = -1) as thumbs_down,
                COUNT(*) as total_ratings,
                ROUND(
                    COUNT(*) FILTER (WHERE mr.rating = 1)::numeric /
                    NULLIF(COUNT(*), 0)::numeric * 100, 1
                ) as satisfaction_rate,
                COUNT(DISTINCT mr.feedback) FILTER (WHERE mr.feedback IS NOT NULL AND mr.feedback != '') as feedback_count
            FROM message_ratings mr
            JOIN messages m ON mr.message_id = m.id
            WHERE m.role = 'assistant'
              AND mr.created_at >= NOW() - INTERVAL '%s days'
        """ % days)

        # Distribution par reranking
        reranking_stats = await conn.fetch("""
            SELECT
                c.reranking_enabled,
                COUNT(*) FILTER (WHERE mr.rating = 1) as thumbs_up,
                COUNT(*) FILTER (WHERE mr.rating = -1) as thumbs_down,
                COUNT(*) as total_ratings,
                ROUND(
                    COUNT(*) FILTER (WHERE mr.rating = 1)::numeric /
                    NULLIF(COUNT(*), 0)::numeric * 100, 1
                ) as satisfaction_rate
            FROM conversations c
            JOIN messages m ON c.id = m.conversation_id AND m.role = 'assistant'
            JOIN message_ratings mr ON m.id = mr.message_id
            WHERE mr.created_at >= NOW() - INTERVAL '%s days'
            GROUP BY c.reranking_enabled
        """ % days)

        # Distribution par profondeur conversation
        depth_stats = await conn.fetch("""
            WITH message_positions AS (
                SELECT
                    m.id,
                    mr.rating,
                    ROW_NUMBER() OVER (PARTITION BY m.conversation_id ORDER BY m.created_at) as position
                FROM messages m
                JOIN message_ratings mr ON m.id = mr.message_id
                WHERE m.role = 'assistant'
                  AND mr.created_at >= NOW() - INTERVAL '%s days'
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
                COUNT(*) FILTER (WHERE mr.rating = 1) as thumbs_up,
                COUNT(*) FILTER (WHERE mr.rating = -1) as thumbs_down,
                COUNT(*) as total_ratings,
                ROUND(
                    COUNT(*) FILTER (WHERE mr.rating = 1)::numeric /
                    NULLIF(COUNT(*), 0)::numeric * 100, 1
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
                COUNT(*) FILTER (WHERE mr.rating = 1) as thumbs_up,
                COUNT(*) FILTER (WHERE mr.rating = -1) as thumbs_down,
                COUNT(*) as total_ratings,
                ROUND(
                    COUNT(*) FILTER (WHERE mr.rating = 1)::numeric /
                    NULLIF(COUNT(*), 0)::numeric * 100, 1
                ) as satisfaction_rate,
                COUNT(DISTINCT mr.feedback) FILTER (WHERE mr.feedback IS NOT NULL AND mr.feedback != '') as feedback_count,
                ROUND(
                    COUNT(DISTINCT mr.feedback) FILTER (WHERE mr.feedback IS NOT NULL AND mr.feedback != '')::numeric /
                    NULLIF(COUNT(*), 0)::numeric * 100, 1
                ) as feedback_ratio
            FROM conversations c
            JOIN messages m ON c.id = m.conversation_id AND m.role = 'assistant'
            JOIN message_ratings mr ON m.id = mr.message_id
            WHERE mr.created_at >= NOW() - INTERVAL '%s days'
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
