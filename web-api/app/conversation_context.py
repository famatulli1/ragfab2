"""
Module de gestion du contexte conversationnel intelligent pour RAGFab.

Ce module fournit des fonctions pour:
- Construire un contexte conversationnel structuré
- Enrichir les queries avec le contexte
- Détecter les changements de sujet
- Créer des system prompts contextuels

Author: RAGFab Optimization Team
Date: 2025-01-24
"""

import logging
import os
from typing import List, Dict, Optional
from uuid import UUID
import httpx
from datetime import datetime

logger = logging.getLogger(__name__)


async def extract_main_topic(messages: List[dict], db_pool) -> str:
    """
    Extrait le sujet principal d'une conversation à partir des messages récents.

    Args:
        messages: Liste des messages (user + assistant) triés du plus récent au plus ancien
        db_pool: Pool de connexions PostgreSQL

    Returns:
        Sujet principal de la conversation (string concis)
    """
    if not messages or len(messages) < 2:
        return "nouvelle conversation"

    # Prendre les 3 premiers échanges (6 messages max)
    recent_msgs = messages[:min(6, len(messages))]

    # Construire un résumé des questions utilisateur
    user_questions = []
    for msg in recent_msgs:
        if msg["role"] == "user":
            user_questions.append(msg["content"][:100])

    if not user_questions:
        return "nouvelle conversation"

    # Utiliser LLM rapide pour extraire topic (appel léger, 50 tokens max)
    try:
        from app.utils.generic_llm_provider import get_generic_llm_model

        model = get_generic_llm_model()
        api_url = model.api_url.rstrip('/')

        topic_prompt = f"""Extrait le sujet principal de cette conversation en 3-5 mots maximum.

Questions posées:
{chr(10).join(f"- {q}" for q in user_questions)}

Sujet (3-5 mots):"""

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{api_url}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {model.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model.model_name,
                    "messages": [{"role": "user", "content": topic_prompt}],
                    "temperature": 0.1,
                    "max_tokens": 50
                }
            )
            response.raise_for_status()
            result = response.json()

            topic = result["choices"][0]["message"]["content"].strip()
            logger.info(f"📌 Sujet extrait: '{topic}'")
            return topic

    except Exception as e:
        logger.warning(f"⚠️ Erreur extraction topic: {e}")
        # Fallback: utiliser première question comme topic
        return user_questions[0][:50] if user_questions else "conversation générale"


async def build_conversation_context(
    conversation_id: UUID,
    db_pool,
    limit: int = 5
) -> Optional[Dict]:
    """
    Construit un contexte conversationnel structuré intelligent.

    Ce contexte enrichit le system prompt sans passer l'historique complet au LLM,
    permettant de maintenir la cohérence conversationnelle tout en forçant le function calling.

    Args:
        conversation_id: ID de la conversation
        db_pool: Pool de connexions PostgreSQL
        limit: Nombre maximum d'échanges à considérer (défaut: 5)

    Returns:
        Dictionnaire avec:
        - current_topic: Sujet principal de la conversation
        - conversation_flow: Liste des échanges récents (question + résumé réponse)
        - all_sources_consulted: Liste de toutes les sources consultées
        - last_exchange: Dernier échange (pour référence rapide)
    """
    try:
        # Récupérer les derniers messages
        async with db_pool.acquire() as conn:
            messages = await conn.fetch(
                """
                SELECT role, content, sources, created_at
                FROM messages
                WHERE conversation_id = $1
                ORDER BY created_at DESC
                LIMIT $2
                """,
                conversation_id,
                limit * 2  # *2 car user+assistant par échange
            )

        if not messages or len(messages) < 2:
            logger.info(f"📭 Pas assez de messages pour construire contexte (conv_id={conversation_id})")
            return None

        # Identifier le sujet principal
        topic = await extract_main_topic(messages, db_pool)

        # Construire le contexte structuré
        context = {
            "current_topic": topic,
            "conversation_flow": [],
            "all_sources_consulted": [],
            "last_exchange": None
        }

        # Parcourir échanges du plus ancien au plus récent
        for i in range(len(messages) - 1, -1, -2):
            if i == 0:
                break  # Dernier message sans paire

            assistant_msg = messages[i]
            user_msg = messages[i - 1] if i > 0 else None

            if not user_msg:
                continue

            # Résumé de la réponse (300 chars max)
            assistant_summary = assistant_msg["content"][:300]
            if len(assistant_msg["content"]) > 300:
                assistant_summary += "..."

            # Sources utilisées dans cette réponse
            sources_used = []
            if assistant_msg["sources"]:
                sources_used = [
                    s.get("document_title", "Document sans titre")
                    for s in assistant_msg["sources"]
                ][:3]  # Max 3 sources par échange

            exchange = {
                "user_asked": user_msg["content"],
                "assistant_answered": assistant_summary,
                "sources_used": sources_used,
                "timestamp": user_msg["created_at"].isoformat()
            }

            context["conversation_flow"].insert(0, exchange)  # Insert au début (ordre chronologique)

            # Agréger toutes les sources consultées
            if assistant_msg["sources"]:
                for source in assistant_msg["sources"]:
                    if source not in context["all_sources_consulted"]:
                        context["all_sources_consulted"].append(source)

            # Sauvegarder le dernier échange
            if context["last_exchange"] is None:
                context["last_exchange"] = exchange

        logger.info(
            f"✅ Contexte construit: topic='{topic}', "
            f"{len(context['conversation_flow'])} échanges, "
            f"{len(context['all_sources_consulted'])} sources"
        )

        return context

    except Exception as e:
        logger.error(f"❌ Erreur construction contexte: {e}", exc_info=True)
        return None


async def create_contextual_system_prompt(context: Optional[Dict], base_prompt: str) -> str:
    """
    Crée un system prompt enrichi avec le contexte conversationnel.

    Args:
        context: Contexte conversationnel (ou None si première question)
        base_prompt: System prompt de base (avec définition des tools)

    Returns:
        System prompt enrichi avec contexte structuré
    """
    if not context:
        # Pas de contexte → retourner prompt de base
        return base_prompt

    # Formater le flux conversationnel
    flow_lines = []
    for i, exchange in enumerate(context["conversation_flow"][-3:], 1):  # 3 derniers échanges
        flow_lines.append(
            f"{i}. **Question**: {exchange['user_asked']}\n"
            f"   **Réponse**: {exchange['assistant_answered']}"
        )
        if exchange["sources_used"]:
            flow_lines.append(f"   **Sources**: {', '.join(exchange['sources_used'])}")

    flow_summary = "\n\n".join(flow_lines)

    # Formater les sources consultées (titres uniques)
    sources_titles = list(set([
        s.get("document_title", "Document")
        for s in context["all_sources_consulted"]
    ]))[:5]  # Max 5 titres

    sources_str = ", ".join(sources_titles) if sources_titles else "Aucune source consultée"

    # Injecter contexte dans le prompt
    contextual_section = f"""
📚 **CONTEXTE DE LA CONVERSATION EN COURS**

**Sujet principal**: {context['current_topic']}

**Échanges précédents** (résumé des 3 derniers):
{flow_summary}

**Documents déjà consultés**: {sources_str}

---

**🎯 NOUVELLE QUESTION DE L'UTILISATEUR** (ci-dessous)

**INSTRUCTIONS CRITIQUES POUR UTILISER LE CONTEXTE**:

1. **COMPRENDRE LA CONTINUITÉ**:
   - Cette question fait probablement suite aux échanges précédents
   - L'utilisateur explore le sujet: "{context['current_topic']}"
   - Il peut faire référence implicite aux réponses précédentes

2. **ENRICHIR LA RECHERCHE**:
   - Si la question est courte/vague (ex: "Comment faire ?", "Et pour ça ?"):
     → Enrichir avec le contexte du sujet principal
     → Exemple: "Comment faire ?" devient "Comment {context['current_topic']}"

   - Si la question fait référence à une réponse précédente:
     → Intégrer les éléments clés de l'échange précédent
     → Exemple: "Et les exceptions ?" devient "Quelles sont les exceptions à {context['current_topic']}"

3. **MAINTENIR LA COHÉRENCE**:
   - Référencer explicitement si c'est une suite de procédure
   - Exemple: "Suite à l'étape précédente (activation Bluetooth), maintenant..."
   - Éviter de répéter des informations déjà données sauf si nécessaire

4. **APPEL DU TOOL OBLIGATOIRE**:
   - Tu DOIS TOUJOURS appeler `search_knowledge_base_tool` avant de répondre
   - La query doit être enrichie du contexte si nécessaire
   - NE PAS juste chercher "ça" ou "celle-ci" → reformuler avec le sujet

---

"""

    # Insérer contexte AVANT les règles absolues du prompt de base
    enriched_prompt = contextual_section + base_prompt

    logger.info(f"📋 System prompt enrichi créé ({len(enriched_prompt)} chars, +{len(contextual_section)} contexte)")

    return enriched_prompt


async def enrich_query_with_context(
    user_message: str,
    context: Optional[Dict]
) -> str:
    """
    Enrichit une query utilisateur avec le contexte conversationnel si nécessaire.

    Détecte les questions courtes ou avec références implicites et les enrichit
    avec le contexte du sujet principal.

    Args:
        user_message: Message utilisateur original
        context: Contexte conversationnel (ou None)

    Returns:
        Query enrichie ou originale si pas besoin d'enrichissement
    """
    if not context:
        return user_message

    # Compter les mots
    word_count = len(user_message.split())

    # Questions très courtes (≤ 5 mots) → probablement des follow-ups
    if word_count <= 5:
        enriched = f"{user_message} (contexte: {context['current_topic']})"
        logger.info(f"🔧 Query enrichie (courte): '{user_message}' → '{enriched}'")
        return enriched

    # Détecter références implicites
    implicit_refs = [
        "comment", "pourquoi", "et si", "et après", "ensuite",
        "ça", "celle", "celui", "le", "la", "cette", "ce",
        "précise", "développe", "détaille", "explique"
    ]

    first_words = user_message.lower().split()[:2]  # 2 premiers mots
    has_implicit_ref = any(word in implicit_refs for word in first_words)

    if has_implicit_ref and context.get("last_exchange"):
        # Ajouter contexte du dernier échange
        last_q = context["last_exchange"]["user_asked"][:80]
        enriched = f"{user_message} (suite de: {last_q})"
        logger.info(f"🔧 Query enrichie (référence): '{user_message}' → '{enriched}'")
        return enriched

    # Question autonome → pas d'enrichissement
    logger.info(f"✅ Query autonome, pas d'enrichissement: '{user_message}'")
    return user_message


async def detect_topic_shift(
    new_message: str,
    context: Optional[Dict],
    db_pool
) -> bool:
    """
    Détecte si l'utilisateur change de sujet dans sa nouvelle question.

    Utilise un appel LLM rapide pour classifier si la question continue
    le même sujet ou introduit un nouveau sujet.

    Args:
        new_message: Nouvelle question de l'utilisateur
        context: Contexte conversationnel actuel
        db_pool: Pool de connexions DB

    Returns:
        True si changement de sujet détecté, False sinon
    """
    if not context:
        # Première question → pas de topic shift
        return False

    current_topic = context["current_topic"]

    try:
        from app.utils.generic_llm_provider import get_generic_llm_model

        model = get_generic_llm_model()
        api_url = model.api_url.rstrip('/')

        classification_prompt = f"""Sujet actuel de la conversation: {current_topic}

Nouvelle question: {new_message}

L'utilisateur change-t-il de sujet ou continue-t-il le même sujet ?
Réponds uniquement: MEME_SUJET ou NOUVEAU_SUJET"""

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{api_url}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {model.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model.model_name,
                    "messages": [{"role": "user", "content": classification_prompt}],
                    "temperature": 0.1,
                    "max_tokens": 10
                }
            )
            response.raise_for_status()
            result = response.json()

            classification = result["choices"][0]["message"]["content"].strip().upper()
            is_new_topic = "NOUVEAU" in classification

            if is_new_topic:
                logger.info(f"🔀 Topic shift détecté: '{current_topic}' → nouveau sujet")
            else:
                logger.info(f"✅ Même sujet: '{current_topic}'")

            return is_new_topic

    except Exception as e:
        logger.warning(f"⚠️ Erreur détection topic shift: {e}")
        # En cas d'erreur, assumer même sujet (plus safe)
        return False
