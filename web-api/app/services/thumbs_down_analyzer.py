"""
Service d'analyse IA pour la validation des thumbs down

Ce service analyse automatiquement les thumbs down avec un LLM pour classifier
les problèmes et déterminer les actions appropriées.
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from uuid import UUID
import asyncpg
import httpx

logger = logging.getLogger(__name__)


class ThumbsDownAnalyzer:
    """Analyse IA des thumbs down pour classification et recommandations"""

    def __init__(self, db_pool: asyncpg.Pool):
        self.db = db_pool
        self.confidence_threshold = float(os.getenv("THUMBS_DOWN_CONFIDENCE_THRESHOLD", "0.7"))

        # LLM Configuration
        self.llm_provider = os.getenv("THUMBS_DOWN_LLM_PROVIDER", os.getenv("RAG_PROVIDER", "mistral"))
        self.llm_api_url = os.getenv("LLM_API_URL", "https://api.mistral.ai")
        self.llm_api_key = os.getenv("LLM_API_KEY", "")
        self.llm_model = os.getenv("LLM_MODEL_NAME", "mistral-small-latest")
        self.llm_timeout = float(os.getenv("LLM_TIMEOUT", "60.0"))

        logger.info(f"ThumbsDownAnalyzer initialized with provider={self.llm_provider}, model={self.llm_model}")

    async def analyze_thumbs_down(self, rating_id: UUID) -> Dict[str, Any]:
        """
        Analyse complète d'un thumbs down avec classification IA

        Args:
            rating_id: UUID du rating à analyser

        Returns:
            Dict avec validation_id, classification, confidence, needs_review
        """
        try:
            # 1. Récupérer contexte complet du rating
            context = await self._get_rating_context(rating_id)

            if not context:
                logger.error(f"Rating {rating_id} not found or invalid")
                return {"error": "Rating not found"}

            # 2. Construire prompt pour LLM
            prompt = self._build_analysis_prompt(context)

            # 3. Appeler LLM pour classification
            logger.info(f"Analyzing thumbs down {rating_id} with {self.llm_provider}")
            response = await self._call_llm(prompt)

            # 4. Parser réponse JSON du LLM
            classification = response.get('classification', 'unrealistic_expectations')
            confidence = float(response.get('confidence', 0.5))
            reasoning = response.get('reasoning', 'Analyse IA non disponible')
            suggested_reformulation = response.get('suggested_reformulation')
            missing_info_details = response.get('missing_info')

            # 5. Déterminer si révision admin nécessaire
            needs_review = (
                confidence < self.confidence_threshold or
                classification == 'unrealistic_expectations'
            )

            # 6. Enregistrer analyse dans la base
            validation_id = await self._save_validation(
                rating_id=rating_id,
                context=context,
                classification=classification,
                confidence=confidence,
                reasoning=reasoning,
                suggested_reformulation=suggested_reformulation,
                missing_info_details=missing_info_details,
                needs_review=needs_review
            )

            logger.info(f"✅ Analysis completed: validation_id={validation_id}, classification={classification}, confidence={confidence:.2f}, needs_review={needs_review}")

            return {
                'validation_id': str(validation_id),
                'classification': classification,
                'confidence': confidence,
                'needs_review': needs_review,
                'reasoning': reasoning
            }

        except Exception as e:
            logger.error(f"❌ Error analyzing thumbs down {rating_id}: {e}", exc_info=True)
            return {"error": str(e)}

    async def _get_rating_context(self, rating_id: UUID) -> Optional[Dict[str, Any]]:
        """Récupère le contexte complet d'un rating pour l'analyse"""
        async with self.db.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT
                    mr.id as rating_id,
                    mr.message_id,
                    mr.user_id,
                    mr.rating,
                    mr.feedback as user_feedback,
                    u.username,
                    u.email as user_email,
                    u.first_name,
                    u.last_name,
                    m.role as message_role,
                    m.content as message_content,
                    m.sources,
                    c.id as conversation_id,
                    c.title as conversation_title,
                    -- Récupérer le message user précédent (la question)
                    (
                        SELECT content
                        FROM messages pm
                        WHERE pm.conversation_id = c.id
                          AND pm.role = 'user'
                          AND pm.created_at < m.created_at
                        ORDER BY pm.created_at DESC
                        LIMIT 1
                    ) as user_question
                FROM message_ratings mr
                JOIN messages m ON mr.message_id = m.id
                JOIN conversations c ON m.conversation_id = c.id
                JOIN users u ON mr.user_id = u.id
                WHERE mr.id = $1
            """, rating_id)

            if not row:
                return None

            return dict(row)

    def _build_analysis_prompt(self, context: Dict[str, Any]) -> str:
        """Construit le prompt pour le LLM avec le contexte complet"""

        sources_summary = "Aucune source utilisée"
        if context.get('sources'):
            try:
                sources = json.loads(context['sources']) if isinstance(context['sources'], str) else context['sources']
                sources_summary = f"{len(sources)} chunks utilisés"
            except:
                sources_summary = "Sources non analysables"

        return f"""Tu es un expert en analyse de qualité RAG et accompagnement utilisateur.

Analyse ce thumbs down et classifie-le dans UNE SEULE catégorie parmi les 4 suivantes :

**CONTEXTE** :
- Utilisateur : {context.get('username', 'Unknown')} ({context.get('first_name', '')} {context.get('last_name', '')})
- Email : {context.get('user_email', 'N/A')}
- Question utilisateur : "{context.get('user_question', 'Question non disponible')}"
- Réponse système : "{context.get('message_content', '')[:500]}..." (tronquée)
- Sources utilisées : {sources_summary}
- Feedback textuel : "{context.get('user_feedback') or 'Aucun feedback fourni'}"

**CATÉGORIES DE CLASSIFICATION** :

1. **bad_question** : Question mal formulée
   - Critères : Orthographe incorrecte, grammaire incorrecte, question trop vague/ambiguë, manque de contexte
   - Indicateurs : Fautes d'orthographe, mots manquants, formulation incompréhensible
   - Action recommandée : Accompagner l'utilisateur pour reformuler
   - Si tu choisis cette catégorie, fournis obligatoirement une suggested_reformulation

2. **bad_answer** : Réponse incorrecte/incomplète
   - Critères : Le système a fourni une mauvaise réponse malgré des sources correctes
   - Indicateurs : Erreur de synthèse, hallucination, réponse partielle alors que l'info existe dans les sources
   - Action recommandée : Analyse du prompt ou du modèle LLM

3. **missing_sources** : Sources pertinentes absentes
   - Critères : L'information demandée n'a pas été trouvée car elle n'est pas indexée
   - Indicateurs : "Je ne trouve pas d'information", sources non pertinentes, aucune source
   - Action recommandée : Marquer le document pour réingestion
   - Si tu choisis cette catégorie, fournis obligatoirement missing_info avec précisions

4. **unrealistic_expectations** : Attentes hors scope
   - Critères : L'utilisateur demande quelque chose qui n'est pas dans la base documentaire
   - Indicateurs : Questions sur des sujets non couverts, demande d'opinions personnelles, créativité
   - Action recommandée : Expliquer à l'utilisateur les limites du système

**INSTRUCTIONS IMPORTANTES** :
- Analyse principalement la QUESTION et la RÉPONSE, pas uniquement le feedback utilisateur
- Le feedback peut être vide, ne te base pas uniquement dessus
- Si la question contient des fautes d'orthographe évidentes → bad_question
- Si la réponse dit "je ne trouve pas" ou sources vides → missing_sources
- Si la réponse est incorrecte malgré de bonnes sources → bad_answer
- Si la question est hors scope documentaire → unrealistic_expectations

**FORMAT DE RÉPONSE ATTENDU (JSON strict)** :
{{
  "classification": "bad_question|bad_answer|missing_sources|unrealistic_expectations",
  "confidence": 0.0-1.0,
  "reasoning": "Explication détaillée de ta classification (2-3 phrases)",
  "suggested_reformulation": "Reformulation suggérée (OBLIGATOIRE si bad_question, sinon null)",
  "missing_info": "Détails sur l'info manquante (OBLIGATOIRE si missing_sources, sinon null)"
}}

**EXEMPLES** :

Exemple 1 - bad_question :
{{
  "classification": "bad_question",
  "confidence": 0.95,
  "reasoning": "La question contient des fautes d'orthographe ('proceduree', 'telletravail') et est mal structurée, ce qui rend difficile la compréhension de l'intention.",
  "suggested_reformulation": "Quelle est la procédure pour demander le télétravail ?",
  "missing_info": null
}}

Exemple 2 - missing_sources :
{{
  "classification": "missing_sources",
  "confidence": 0.85,
  "reasoning": "La réponse indique 'Je ne trouve pas d'information sur ce sujet' et aucune source n'est fournie. L'utilisateur cherche une info spécifique sur un logiciel interne.",
  "suggested_reformulation": null,
  "missing_info": "Documentation du logiciel PeopleDoc pour gestion des absences"
}}

Réponds UNIQUEMENT avec le JSON, sans texte additionnel avant ou après."""

    async def _call_llm(self, prompt: str) -> Dict[str, Any]:
        """Appelle le LLM pour analyser le thumbs down"""

        try:
            async with httpx.AsyncClient(timeout=self.llm_timeout) as client:
                # Construction de la requête OpenAI-compatible
                headers = {
                    "Content-Type": "application/json",
                }

                if self.llm_api_key:
                    headers["Authorization"] = f"Bearer {self.llm_api_key}"

                payload = {
                    "model": self.llm_model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "Tu es un expert en analyse de qualité RAG. Réponds toujours en JSON strict."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.1,  # Température basse pour réponses déterministes
                    "max_tokens": 500
                }

                response = await client.post(
                    f"{self.llm_api_url}/v1/chat/completions",
                    headers=headers,
                    json=payload
                )

                response.raise_for_status()
                data = response.json()

                # Extraire le contenu de la réponse
                content = data['choices'][0]['message']['content']

                # Parser le JSON (nettoyer markdown si présent)
                content = content.strip()
                if content.startswith("```json"):
                    content = content[7:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()

                result = json.loads(content)

                logger.debug(f"LLM response: {result}")

                return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON response: {e}")
            # Fallback avec classification par défaut
            return {
                "classification": "unrealistic_expectations",
                "confidence": 0.3,
                "reasoning": f"Erreur de parsing JSON: {str(e)}",
                "suggested_reformulation": null,
                "missing_info": null
            }
        except httpx.HTTPError as e:
            logger.error(f"HTTP error calling LLM: {e}")
            return {
                "classification": "unrealistic_expectations",
                "confidence": 0.3,
                "reasoning": f"Erreur API: {str(e)}",
                "suggested_reformulation": null,
                "missing_info": null
            }
        except Exception as e:
            logger.error(f"Unexpected error calling LLM: {e}", exc_info=True)
            return {
                "classification": "unrealistic_expectations",
                "confidence": 0.3,
                "reasoning": f"Erreur inattendue: {str(e)}",
                "suggested_reformulation": null,
                "missing_info": null
            }

    def _determine_admin_action(self, classification: str, confidence: float) -> str:
        """
        Détermine automatiquement l'action admin basée sur la classification et la confiance

        Logique :
        - bad_question avec confiance >= seuil → contact_user (accompagner l'utilisateur)
        - missing_sources avec confiance >= seuil → mark_for_reingestion (réingérer document)
        - bad_answer → pending (nécessite révision manuelle par admin)
        - out_of_scope → ignore (thumbs down légitime, aucune action)
        - Toute classification avec confiance < seuil → pending (révision manuelle)

        Args:
            classification: Type de problème détecté (bad_question, missing_sources, etc.)
            confidence: Score de confiance de l'IA (0.0-1.0)

        Returns:
            Action admin recommandée ('contact_user', 'mark_for_reingestion', 'ignore', 'pending')
        """
        # Si confiance faible, toujours requiert révision manuelle
        if confidence < self.confidence_threshold:
            return 'pending'

        # Logique basée sur classification avec haute confiance
        if classification == 'bad_question':
            return 'contact_user'  # Utilisateur a mal formulé sa question
        elif classification == 'missing_sources':
            return 'mark_for_reingestion'  # Document manque d'informations
        elif classification == 'out_of_scope':
            return 'ignore'  # Question hors périmètre, thumbs down légitime
        elif classification == 'bad_answer':
            return 'pending'  # Réponse incorrecte, nécessite investigation humaine
        else:
            # Classification inconnue ou unrealistic_expectations
            return 'pending'

    async def _save_validation(
        self,
        rating_id: UUID,
        context: Dict[str, Any],
        classification: str,
        confidence: float,
        reasoning: str,
        suggested_reformulation: Optional[str],
        missing_info_details: Optional[str],
        needs_review: bool
    ) -> UUID:
        """Enregistre l'analyse dans thumbs_down_validations"""

        # Déterminer automatiquement l'action admin basée sur classification et confiance
        admin_action = self._determine_admin_action(classification, confidence)

        logger.info(f"💡 Auto-action déterminée: {admin_action} (classification={classification}, confidence={confidence:.2f})")

        async with self.db.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO thumbs_down_validations (
                    message_id,
                    rating_id,
                    user_id,
                    user_question,
                    assistant_response,
                    sources_used,
                    user_feedback,
                    ai_classification,
                    ai_confidence,
                    ai_reasoning,
                    suggested_reformulation,
                    missing_info_details,
                    needs_admin_review,
                    admin_action
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                ON CONFLICT (message_id) DO UPDATE
                SET ai_classification = $8,
                    ai_confidence = $9,
                    ai_reasoning = $10,
                    suggested_reformulation = $11,
                    missing_info_details = $12,
                    needs_admin_review = $13,
                    admin_action = $14,
                    created_at = CURRENT_TIMESTAMP
                RETURNING id
            """,
                context['message_id'],
                rating_id,
                context['user_id'],
                context.get('user_question', ''),
                context.get('message_content', ''),
                json.dumps(context.get('sources')) if context.get('sources') else None,
                context.get('user_feedback'),
                classification,
                confidence,
                reasoning,
                suggested_reformulation,
                missing_info_details,
                needs_review,
                admin_action
            )

            validation_id = row['id']

            # Si action automatique = mark_for_reingestion, synchroniser immédiatement
            if admin_action == 'mark_for_reingestion':
                logger.info(f"🔄 Auto-syncing validation {validation_id} to document_quality_scores")

                try:
                    # Sync vers document_quality_scores
                    result = await conn.execute("""
                        INSERT INTO document_quality_scores (
                            document_id,
                            needs_reingestion,
                            reingestion_reason,
                            updated_at
                        )
                        SELECT DISTINCT
                            c.document_id,
                            true AS needs_reingestion,
                            $2 AS reingestion_reason,
                            NOW() AS updated_at
                        FROM thumbs_down_validations v
                        CROSS JOIN LATERAL jsonb_array_elements(v.sources_used) as source
                        JOIN chunks c ON c.id = (source->>'chunk_id')::UUID
                        WHERE v.id = $1
                            AND v.sources_used IS NOT NULL
                            AND jsonb_typeof(v.sources_used) = 'array'

                        ON CONFLICT (document_id) DO UPDATE
                        SET
                            needs_reingestion = true,
                            updated_at = NOW(),
                            reingestion_reason = COALESCE(
                                document_quality_scores.reingestion_reason || ' | ',
                                ''
                            ) || EXCLUDED.reingestion_reason
                    """, validation_id, f"AI auto-classification: {classification} (confidence={confidence:.2f})")

                    # Extraire nombre de documents synchronisés
                    status = result.split()
                    count = int(status[-1]) if status else 0

                    if count > 0:
                        logger.info(f"✅ Auto-synced {count} document(s) from validation {validation_id}")
                    else:
                        logger.warning(f"⚠️ No documents found to sync from validation {validation_id}")

                except Exception as sync_error:
                    # Ne pas bloquer si sync échoue (graceful degradation)
                    logger.error(f"❌ Error auto-syncing validation {validation_id}: {sync_error}")

            return validation_id
