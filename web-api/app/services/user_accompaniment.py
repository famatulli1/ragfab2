"""
Service d'accompagnement utilisateur pour amélioration des questions

Ce service crée des notifications pédagogiques pour aider les utilisateurs
à mieux formuler leurs questions et utiliser le système RAG.
"""

import os
import logging
from typing import Dict, Any, Optional
from uuid import UUID
import asyncpg

logger = logging.getLogger(__name__)


class UserAccompanimentService:
    """Service d'accompagnement et notifications utilisateurs"""

    def __init__(self, db_pool: asyncpg.Pool):
        self.db = db_pool
        self.notifications_enabled = os.getenv("THUMBS_DOWN_AUTO_NOTIFICATIONS", "true").lower() == "true"
        logger.info(f"UserAccompanimentService initialized (notifications_enabled={self.notifications_enabled})")

    async def create_question_improvement_notification(
        self,
        validation_id: UUID
    ) -> Optional[UUID]:
        """
        Crée une notification pédagogique pour aider l'utilisateur à améliorer ses questions

        Args:
            validation_id: UUID de la validation thumbs_down

        Returns:
            UUID de la notification créée, ou None si désactivé
        """
        if not self.notifications_enabled:
            logger.info(f"Notifications disabled, skipping for validation {validation_id}")
            return None

        try:
            # Récupérer détails de la validation
            validation = await self._get_validation_details(validation_id)

            if not validation:
                logger.error(f"Validation {validation_id} not found")
                return None

            # Classification finale (admin override ou IA)
            final_classification = validation['admin_override'] or validation['ai_classification']

            # Ne créer notification que pour bad_question
            if final_classification != 'bad_question':
                logger.debug(f"Skipping notification for classification={final_classification}")
                return None

            # Construire message personnalisé
            message = self._build_notification_message(validation)

            # Créer notification
            notification_id = await self._create_notification(
                user_id=validation['user_id'],
                validation_id=validation_id,
                title="💡 Conseil pour améliorer vos questions",
                message=message
            )

            logger.info(f"✅ Notification {notification_id} created for user {validation['user_id']}")
            return notification_id

        except Exception as e:
            logger.error(f"❌ Error creating notification for validation {validation_id}: {e}", exc_info=True)
            return None

    async def create_quality_feedback_notification(
        self,
        validation_id: UUID
    ) -> Optional[UUID]:
        """
        Crée une notification de feedback qualité pour missing_sources ou bad_answer

        Args:
            validation_id: UUID de la validation thumbs_down

        Returns:
            UUID de la notification créée, ou None
        """
        if not self.notifications_enabled:
            return None

        try:
            validation = await self._get_validation_details(validation_id)
            if not validation:
                return None

            final_classification = validation['admin_override'] or validation['ai_classification']

            # Notification uniquement pour missing_sources ou bad_answer
            if final_classification not in ['missing_sources', 'bad_answer']:
                return None

            # Message selon classification
            if final_classification == 'missing_sources':
                title = "🔍 Amélioration de la base documentaire"
                message = f"""Bonjour {validation['first_name'] or validation['username']},

Merci pour votre retour sur la question : "{validation['user_question'][:100]}..."

Nous avons identifié que l'information recherchée n'était pas disponible dans notre base documentaire.
Nous allons enrichir nos sources pour mieux répondre à ce type de question à l'avenir.

Merci de votre contribution à l'amélioration du système !

L'équipe RAGFab"""

            else:  # bad_answer
                title = "⚠️ Qualité de la réponse en cours d'amélioration"
                message = f"""Bonjour {validation['first_name'] or validation['username']},

Nous avons pris en compte votre retour négatif concernant la réponse à votre question : "{validation['user_question'][:100]}..."

Notre équipe analyse le problème pour améliorer la qualité des réponses du système.

Merci de votre patience et de votre contribution !

L'équipe RAGFab"""

            # Créer notification
            notification_id = await self._create_notification(
                user_id=validation['user_id'],
                validation_id=validation_id,
                title=title,
                message=message,
                notification_type='quality_feedback'
            )

            logger.info(f"✅ Quality feedback notification {notification_id} created for user {validation['user_id']}")
            return notification_id

        except Exception as e:
            logger.error(f"❌ Error creating quality feedback notification: {e}", exc_info=True)
            return None

    async def _get_validation_details(self, validation_id: UUID) -> Optional[Dict[str, Any]]:
        """Récupère les détails d'une validation"""
        async with self.db.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT
                    v.id,
                    v.user_id,
                    v.user_question,
                    v.assistant_response,
                    v.ai_classification,
                    v.ai_confidence,
                    v.ai_reasoning,
                    v.suggested_reformulation,
                    v.missing_info_details,
                    v.admin_override,
                    u.username,
                    u.email as user_email,
                    u.first_name,
                    u.last_name
                FROM thumbs_down_validations v
                JOIN users u ON v.user_id = u.id
                WHERE v.id = $1
            """, validation_id)

            return dict(row) if row else None

    def _build_notification_message(self, validation: Dict[str, Any]) -> str:
        """Construit le message de notification personnalisé"""

        user_name = validation['first_name'] or validation['username']
        question = validation['user_question']
        reformulation = validation['suggested_reformulation']
        reasoning = validation['ai_reasoning']

        # Conseils génériques selon le raisonnement IA
        tips = self._get_question_tips(reasoning)

        message = f"""Bonjour {user_name},

Nous avons remarqué que votre question "{question}" n'a peut-être pas donné le résultat attendu.

**Pourquoi ?**
{reasoning}

**Conseils pour améliorer vos questions** :
{tips}
"""

        # Ajouter reformulation si disponible
        if reformulation:
            message += f"""
**Suggestion de reformulation** :
"{reformulation}"

N'hésitez pas à réessayer avec cette formulation !
"""

        message += """
Besoin d'aide ? N'hésitez pas à contacter un administrateur.

L'équipe RAGFab"""

        return message

    def _get_question_tips(self, reasoning: str) -> str:
        """Génère des conseils basés sur le raisonnement IA"""

        reasoning_lower = reasoning.lower()

        tips = []

        # Détecter types de problèmes
        if any(word in reasoning_lower for word in ['orthographe', 'faute', 'erreur']):
            tips.append("✓ Vérifiez l'orthographe de vos mots-clés")

        if any(word in reasoning_lower for word in ['vague', 'imprécis', 'ambigu']):
            tips.append("✓ Soyez plus précis dans votre question")
            tips.append("✓ Ajoutez du contexte (qui, quoi, où, quand)")

        if any(word in reasoning_lower for word in ['grammaire', 'structure', 'formulation']):
            tips.append("✓ Utilisez des phrases complètes et structurées")

        if any(word in reasoning_lower for word in ['manque', 'incomplet']):
            tips.append("✓ Incluez tous les détails nécessaires")

        # Conseils génériques si aucun problème spécifique détecté
        if not tips:
            tips = [
                "✓ Utilisez des phrases complètes et claires",
                "✓ Évitez les abréviations non standard",
                "✓ Soyez spécifique dans votre demande",
                "✓ Vérifiez l'orthographe avant d'envoyer"
            ]

        return "\n".join(tips)

    async def _create_notification(
        self,
        user_id: UUID,
        validation_id: UUID,
        title: str,
        message: str,
        notification_type: str = 'question_improvement'
    ) -> UUID:
        """Crée une notification dans la base de données"""

        async with self.db.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO user_notifications (
                    user_id,
                    validation_id,
                    type,
                    title,
                    message,
                    is_read
                ) VALUES ($1, $2, $3, $4, $5, false)
                RETURNING id
            """, user_id, validation_id, notification_type, title, message)

            return row['id']

    async def get_unread_notifications_count(self, user_id: UUID) -> int:
        """Récupère le nombre de notifications non lues pour un utilisateur"""
        async with self.db.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT COUNT(*) as count
                FROM user_notifications
                WHERE user_id = $1 AND is_read = false
            """, user_id)

            return row['count'] if row else 0

    async def mark_notification_as_read(self, notification_id: UUID, user_id: UUID) -> bool:
        """Marque une notification comme lue"""
        async with self.db.acquire() as conn:
            result = await conn.execute("""
                UPDATE user_notifications
                SET is_read = true
                WHERE id = $1 AND user_id = $2
            """, notification_id, user_id)

            return result != "UPDATE 0"

    async def get_user_notifications(
        self,
        user_id: UUID,
        unread_only: bool = False,
        limit: int = 20
    ) -> list:
        """Récupère les notifications d'un utilisateur"""
        async with self.db.acquire() as conn:
            query = """
                SELECT
                    id,
                    validation_id,
                    type,
                    title,
                    message,
                    is_read,
                    created_at
                FROM user_notifications
                WHERE user_id = $1
            """

            if unread_only:
                query += " AND is_read = false"

            query += " ORDER BY created_at DESC LIMIT $2"

            rows = await conn.fetch(query, user_id, limit)

            return [dict(row) for row in rows]
