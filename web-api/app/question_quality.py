"""
Module d'analyse de qualité des questions pour RAGFab.

Ce module fournit:
- Heuristiques rapides de détection de questions vagues (<5ms)
- Analyse LLM approfondie si nécessaire (~500ms)
- Génération de suggestions de reformulation
- Détection de vocabulaire métier manquant

Architecture dual-path:
- Fast path (score >= 0.7): Direct vers recherche RAG
- Slow path (score < 0.7): Analyse LLM + suggestions

Author: RAGFab Team
Date: 2025-01-25
"""

import logging
import os
import re
import json
import hashlib
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Tuple
from functools import lru_cache
from uuid import UUID
import httpx

logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

QUESTION_QUALITY_ENABLED = os.getenv("QUESTION_QUALITY_ENABLED", "true").lower() == "true"
QUESTION_QUALITY_PHASE = os.getenv("QUESTION_QUALITY_PHASE", "shadow")  # shadow | soft | interactive
HEURISTIC_THRESHOLD = float(os.getenv("QUESTION_QUALITY_HEURISTIC_THRESHOLD", "0.7"))
LLM_CONFIDENCE_THRESHOLD = float(os.getenv("QUESTION_QUALITY_LLM_CONFIDENCE_THRESHOLD", "0.75"))
LLM_TIMEOUT = float(os.getenv("QUESTION_QUALITY_LLM_TIMEOUT", "5"))


# ============================================================================
# Enums & Dataclasses
# ============================================================================

class QuestionClassification(str, Enum):
    """Classification du problème détecté dans la question."""
    CLEAR = "clear"                         # Question bien formulée
    TOO_VAGUE = "too_vague"                 # Trop générale
    WRONG_VOCABULARY = "wrong_vocabulary"   # Termes incorrects/non-métier
    MISSING_CONTEXT = "missing_context"     # Références floues (ça, celui-là)
    OUT_OF_SCOPE = "out_of_scope"           # Hors périmètre documentaire


@dataclass
class QuestionSuggestion:
    """Une suggestion de reformulation."""
    text: str
    type: str  # 'reformulation' | 'clarification' | 'domain_term'
    reason: Optional[str] = None


@dataclass
class QualityAnalysisResult:
    """Résultat de l'analyse de qualité d'une question."""
    classification: QuestionClassification
    confidence: float  # 0.0 - 1.0
    heuristic_score: float  # Score des heuristiques (0.0 - 1.0)
    suggestions: List[QuestionSuggestion] = field(default_factory=list)
    detected_terms: List[str] = field(default_factory=list)  # Termes domaine détectés
    suggested_terms: List[str] = field(default_factory=list)  # Termes suggérés
    reasoning: Optional[str] = None  # Explication courte
    analyzed_by: str = "heuristics"  # 'heuristics' | 'llm'

    def to_dict(self) -> Dict:
        """Convertit en dictionnaire pour la réponse API."""
        return {
            "classification": self.classification.value,
            "confidence": self.confidence,
            "heuristic_score": self.heuristic_score,
            "suggestions": [
                {"text": s.text, "type": s.type, "reason": s.reason}
                for s in self.suggestions
            ],
            "detected_terms": self.detected_terms,
            "suggested_terms": self.suggested_terms,
            "reasoning": self.reasoning,
            "analyzed_by": self.analyzed_by
        }


# ============================================================================
# Patterns de Détection (Français)
# ============================================================================

# Red flags: indicateurs de question problématique
RED_FLAG_PATTERNS = [
    # Questions mono-mot ou très courtes
    (r"^(comment|pourquoi|quoi|ou|quand)\s*\?*$", "question_monoword", 0.5),
    # "c'est quoi X" sans contexte
    (r"^c['']?est\s+quoi\s+\w+\s*\?*$", "cest_quoi_vague", 0.4),
    # Trop vague
    (r"^(ca|ça)\s+(marche|fonctionne|se passe)\s*(comment)?\s*\?*$", "ca_vague", 0.5),
    # Début par conjonction (suite implicite)
    (r"^(et|ou|mais|donc)\s+", "starts_conjunction", 0.3),
    # Pronoms seuls
    (r"^(celui|celle|ceux|celles)[-\s]?(ci|la|là)?\s*\?*$", "pronouns_only", 0.5),
    # Multiples espaces (potentiel copier-coller mal formaté)
    (r"\s{3,}", "multiple_spaces", 0.1),
    # Questions ultra-courtes
    (r"^.{1,10}\?*$", "ultra_short", 0.3),
]

# Green flags: indicateurs de bonne question
GREEN_FLAG_PATTERNS = [
    # Termes métier Sillage
    (r"\b(sillage|sipsdm|bis_lme)\b", "sillage_term", 0.2),
    # Termes techniques DB
    (r"\b(bdd|base\s+de\s+donn[ée]es?|table|schema)\b", "db_term", 0.15),
    # Termes médicaux/hospitaliers
    (r"\b(patient|dossier|maternit[ée]|obst[ée]trique)\b", "medical_term", 0.15),
    # Lien mère-enfant spécifique
    (r"\b(lien\s+m[eè]re|m[eè]re[-\s]enfant|ipp|iep)\b", "lien_mere_enfant", 0.25),
    # Procédures
    (r"\b(proc[ée]dure|protocole|[ée]tape|processus)\b", "procedure_term", 0.1),
    # Questions structurées
    (r"^(comment|quelle?\s+est|o[uù]\s+(est|se\s+trouve|trouver))\s+.{15,}", "structured_question", 0.15),
    # Références numériques (IDs, numéros)
    (r"\b(n[°o]?\s*\d+|ref\.?\s*\d+|id\s*[:=]?\s*\d+)\b", "has_reference", 0.1),
]

# Vocabulaire utilisateur → vocabulaire métier
VOCABULARY_CORRECTIONS = {
    # Expressions courantes → termes techniques
    "rattacher la maman": "créer le lien mère-enfant",
    "rattacher maman": "créer lien mère-enfant",
    "rattacher le bébé": "créer le lien mère-enfant",
    "lier maman bébé": "créer lien mère-enfant",
    "lier la mère": "créer le lien mère-enfant",
    "maman et bébé": "lien mère-enfant",
    # Termes génériques → spécifiques
    "base de données": "BDD Sillage",
    "le logiciel": "Sillage",
    "l'application": "Sillage",
    "le système": "Sillage",
}

# Stopwords français pour le scoring
FRENCH_STOPWORDS = {
    "le", "la", "les", "un", "une", "des", "du", "de", "d",
    "et", "ou", "mais", "donc", "car", "ni", "que", "qui",
    "ce", "cette", "ces", "mon", "ma", "mes", "ton", "ta", "tes",
    "son", "sa", "ses", "notre", "nos", "votre", "vos", "leur", "leurs",
    "je", "tu", "il", "elle", "nous", "vous", "ils", "elles", "on",
    "me", "te", "se", "lui", "y", "en",
    "à", "au", "aux", "avec", "pour", "par", "sur", "sous", "dans",
    "est", "sont", "a", "ont", "fait", "faire", "être", "avoir",
    "comment", "pourquoi", "quand", "où", "quoi", "quel", "quelle",
}


# ============================================================================
# Fonctions Heuristiques (Fast Path)
# ============================================================================

def normalize_question(question: str) -> str:
    """Normalise une question pour comparaison/cache."""
    normalized = question.lower().strip()
    normalized = re.sub(r'\s+', ' ', normalized)
    normalized = re.sub(r'[^\w\s]', '', normalized)
    return normalized


def compute_length_score(question: str) -> float:
    """
    Score basé sur la longueur de la question.
    Optimal: 5-30 mots
    """
    words = question.split()
    word_count = len(words)

    if word_count < 3:
        return 0.2
    elif word_count < 5:
        return 0.5
    elif word_count <= 30:
        return 1.0
    elif word_count <= 50:
        return 0.7
    else:
        return 0.4


def compute_structure_score(question: str) -> float:
    """
    Score basé sur la structure grammaticale.
    Vérifie présence sujet + verbe + contexte.
    """
    words = question.lower().split()

    # Trop court pour avoir une structure
    if len(words) < 3:
        return 0.3

    # Présence d'un verbe interrogatif/d'action
    question_verbs = {"comment", "pourquoi", "quand", "où", "quel", "quelle", "quels", "quelles"}
    action_verbs = {"faire", "créer", "modifier", "supprimer", "ajouter", "configurer", "activer", "désactiver"}

    has_question_word = any(w in question_verbs for w in words[:3])
    has_action_verb = any(v in question for v in action_verbs)

    score = 0.5

    if has_question_word:
        score += 0.25

    if has_action_verb:
        score += 0.25

    # Bonus si question se termine par "?"
    if question.strip().endswith("?"):
        score += 0.1

    return min(1.0, score)


def compute_vocabulary_score(question: str) -> Tuple[float, List[str], List[str]]:
    """
    Score basé sur le vocabulaire métier détecté.
    Retourne (score, termes_detectes, termes_suggeres)
    """
    question_lower = question.lower()
    detected_terms = []
    suggested_terms = []

    # Vérifier green flags (vocabulaire métier)
    domain_score = 0.0
    for pattern, term_type, bonus in GREEN_FLAG_PATTERNS:
        if re.search(pattern, question_lower, re.IGNORECASE):
            match = re.search(pattern, question_lower, re.IGNORECASE)
            if match:
                detected_terms.append(match.group())
            domain_score += bonus

    # Vérifier si vocabulaire utilisateur peut être amélioré
    for user_term, domain_term in VOCABULARY_CORRECTIONS.items():
        if user_term in question_lower:
            suggested_terms.append(domain_term)

    # Score de base si pas de termes métier
    if not detected_terms and not suggested_terms:
        # Question générique
        base_score = 0.4
    elif suggested_terms and not detected_terms:
        # Utilise vocabulaire utilisateur, pas métier
        base_score = 0.5
    else:
        # Utilise vocabulaire métier
        base_score = 0.7 + min(0.3, domain_score)

    return (min(1.0, base_score), detected_terms, suggested_terms)


def compute_specificity_score(question: str) -> float:
    """
    Score basé sur la spécificité de la question.
    Vérifie présence d'entités nommées, IDs, dates, etc.
    """
    score = 0.5

    # Présence de nombres/IDs
    if re.search(r'\d{3,}', question):
        score += 0.2  # Numéros significatifs

    # Présence de noms propres (majuscules)
    proper_nouns = re.findall(r'\b[A-Z][a-z]+\b', question)
    if proper_nouns:
        score += min(0.2, len(proper_nouns) * 0.1)

    # Présence de termes techniques entre guillemets
    if re.search(r'["«»\'].*?["«»\']', question):
        score += 0.1

    # Pénalité pour pronoms vagues
    vague_pronouns = ["ça", "ca", "celui", "celle", "ceux", "celles", "ceci", "cela"]
    if any(p in question.lower().split() for p in vague_pronouns):
        score -= 0.2

    return max(0.0, min(1.0, score))


def apply_pattern_modifiers(question: str, base_score: float) -> Tuple[float, List[str]]:
    """
    Applique les modificateurs red/green flags au score.
    Retourne (score_modifie, raisons)
    """
    question_lower = question.lower()
    score = base_score
    reasons = []

    # Red flags (pénalités)
    for pattern, flag_type, penalty in RED_FLAG_PATTERNS:
        if re.search(pattern, question_lower, re.IGNORECASE):
            score *= (1 - penalty)
            reasons.append(f"red_flag:{flag_type}")

    # Green flags sont déjà comptés dans vocabulary_score
    # mais on peut ajouter des bonus supplémentaires

    return (max(0.0, min(1.0, score)), reasons)


def quick_quality_check(question: str) -> Tuple[float, Dict]:
    """
    Vérification rapide de qualité via heuristiques (<5ms).

    Args:
        question: Question utilisateur

    Returns:
        (score, debug_info) où score est entre 0.0 et 1.0
    """
    # Scores individuels
    length_score = compute_length_score(question)
    structure_score = compute_structure_score(question)
    vocab_score, detected_terms, suggested_terms = compute_vocabulary_score(question)
    specificity_score = compute_specificity_score(question)

    # Pondération
    weights = {
        "length": 0.20,
        "structure": 0.25,
        "vocabulary": 0.35,
        "specificity": 0.20
    }

    weighted_score = (
        length_score * weights["length"] +
        structure_score * weights["structure"] +
        vocab_score * weights["vocabulary"] +
        specificity_score * weights["specificity"]
    )

    # Appliquer modificateurs
    final_score, flags = apply_pattern_modifiers(question, weighted_score)

    debug_info = {
        "scores": {
            "length": round(length_score, 3),
            "structure": round(structure_score, 3),
            "vocabulary": round(vocab_score, 3),
            "specificity": round(specificity_score, 3),
            "weighted": round(weighted_score, 3),
            "final": round(final_score, 3)
        },
        "detected_terms": detected_terms,
        "suggested_terms": suggested_terms,
        "flags": flags,
        "word_count": len(question.split())
    }

    return (final_score, debug_info)


# ============================================================================
# Analyse LLM (Slow Path)
# ============================================================================

LLM_ANALYSIS_PROMPT = """Tu es un assistant de contrôle qualité pour un système RAG médical/hospitalier.

QUESTION UTILISATEUR: "{question}"

{context_section}

DOMAINE DE LA BASE DOCUMENTAIRE:
- Documentation technique Sillage (logiciel hospitalier)
- Procédures médicales et hospitalières
- Guides utilisateur et fiches solutions

VOCABULAIRE MÉTIER IMPORTANT:
- "lien mère-enfant" (pas "rattacher maman/bébé")
- "BDD Sillage" / "table BIS_LME" / "schéma SIPSDM"
- "IPP" (Identifiant Patient Permanent)
- "IEP" (Identifiant Épisode Patient)
- "dossier patient" (pas "fiche patient")

CLASSIFIE LA QUESTION parmi:
- clear: Question bien formulée, vocabulaire approprié, prête pour la recherche
- too_vague: Question trop générale, manque de précision (ex: "comment faire ?")
- wrong_vocabulary: Termes incorrects/familiers au lieu du vocabulaire métier (ex: "rattacher maman" → "créer lien mère-enfant")
- missing_context: Utilise des références floues sans contexte ("celui-là", "ça", "cette chose")
- out_of_scope: Question clairement hors périmètre documentaire (météo, recettes, etc.)

RÉPONDS UNIQUEMENT EN JSON (pas de texte avant/après):
{{
  "classification": "clear|too_vague|wrong_vocabulary|missing_context|out_of_scope",
  "confidence": 0.0-1.0,
  "reasoning": "Explication en 1 phrase",
  "suggestions": ["Reformulation 1", "Reformulation 2"],
  "domain_terms_suggested": ["terme_correct1", "terme_correct2"]
}}"""


async def analyze_with_llm(
    question: str,
    context: Optional[Dict] = None,
    heuristic_info: Optional[Dict] = None
) -> QualityAnalysisResult:
    """
    Analyse approfondie via LLM pour les questions ambiguës.

    Args:
        question: Question utilisateur
        context: Contexte conversationnel (optionnel)
        heuristic_info: Info des heuristiques (pour suggestions)

    Returns:
        QualityAnalysisResult avec classification et suggestions
    """
    try:
        from app.utils.generic_llm_provider import get_generic_llm_model

        model = get_generic_llm_model()
        api_url = model.api_url.rstrip('/')

        # Construire section contexte
        context_section = ""
        if context and context.get("current_topic"):
            context_section = f"""CONTEXTE CONVERSATIONNEL:
- Sujet actuel: {context['current_topic']}
- Dernier échange: {context.get('last_exchange', {}).get('user_asked', 'N/A')[:100]}"""

        prompt = LLM_ANALYSIS_PROMPT.format(
            question=question,
            context_section=context_section
        )

        async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
            response = await client.post(
                f"{api_url}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {model.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model.model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 300
                }
            )
            response.raise_for_status()
            result = response.json()

            content = result["choices"][0]["message"]["content"].strip()

            # Parser le JSON
            # Nettoyer le contenu (enlever markdown si présent)
            if content.startswith("```"):
                content = re.sub(r'^```json?\s*', '', content)
                content = re.sub(r'\s*```$', '', content)

            analysis = json.loads(content)

            classification = QuestionClassification(analysis.get("classification", "too_vague"))
            confidence = float(analysis.get("confidence", 0.5))
            reasoning = analysis.get("reasoning", "")
            suggestions_raw = analysis.get("suggestions", [])
            suggested_terms = analysis.get("domain_terms_suggested", [])

            # Convertir suggestions en objets
            suggestions = []
            for i, sugg_text in enumerate(suggestions_raw[:3]):  # Max 3 suggestions
                suggestions.append(QuestionSuggestion(
                    text=sugg_text,
                    type="reformulation",
                    reason=reasoning if i == 0 else None
                ))

            # Utiliser les termes suggérés par heuristiques si LLM n'en fournit pas
            if not suggested_terms and heuristic_info:
                suggested_terms = heuristic_info.get("suggested_terms", [])

            logger.info(
                f"🤖 Analyse LLM: classification={classification.value}, "
                f"confidence={confidence:.2f}, suggestions={len(suggestions)}"
            )

            return QualityAnalysisResult(
                classification=classification,
                confidence=confidence,
                heuristic_score=heuristic_info.get("scores", {}).get("final", 0.5) if heuristic_info else 0.5,
                suggestions=suggestions,
                detected_terms=heuristic_info.get("detected_terms", []) if heuristic_info else [],
                suggested_terms=suggested_terms,
                reasoning=reasoning,
                analyzed_by="llm"
            )

    except json.JSONDecodeError as e:
        logger.warning(f"⚠️ Erreur parsing JSON LLM: {e}")
        return _fallback_result(question, heuristic_info, "json_parse_error")
    except httpx.TimeoutException:
        logger.warning(f"⚠️ Timeout analyse LLM ({LLM_TIMEOUT}s)")
        return _fallback_result(question, heuristic_info, "timeout")
    except Exception as e:
        logger.error(f"❌ Erreur analyse LLM: {e}", exc_info=True)
        return _fallback_result(question, heuristic_info, str(e))


def _fallback_result(
    question: str,
    heuristic_info: Optional[Dict],
    error_reason: str
) -> QualityAnalysisResult:
    """Génère un résultat de fallback basé sur les heuristiques."""
    heuristic_score = heuristic_info.get("scores", {}).get("final", 0.5) if heuristic_info else 0.5
    suggested_terms = heuristic_info.get("suggested_terms", []) if heuristic_info else []

    # Générer une suggestion basique si vocabulaire incorrect
    suggestions = []
    if suggested_terms:
        # Remplacer dans la question
        improved_question = question
        for user_term, domain_term in VOCABULARY_CORRECTIONS.items():
            if user_term in question.lower():
                improved_question = re.sub(
                    re.escape(user_term),
                    domain_term,
                    improved_question,
                    flags=re.IGNORECASE
                )
        if improved_question != question:
            suggestions.append(QuestionSuggestion(
                text=improved_question,
                type="domain_term",
                reason="Vocabulaire métier suggéré"
            ))

    classification = QuestionClassification.CLEAR if heuristic_score >= HEURISTIC_THRESHOLD else QuestionClassification.TOO_VAGUE

    return QualityAnalysisResult(
        classification=classification,
        confidence=heuristic_score,
        heuristic_score=heuristic_score,
        suggestions=suggestions,
        detected_terms=heuristic_info.get("detected_terms", []) if heuristic_info else [],
        suggested_terms=suggested_terms,
        reasoning=f"Fallback heuristique ({error_reason})",
        analyzed_by="heuristics_fallback"
    )


# ============================================================================
# Point d'Entrée Principal
# ============================================================================

async def analyze_question_quality(
    question: str,
    conversation_context: Optional[Dict] = None,
    threshold: float = None
) -> QualityAnalysisResult:
    """
    Point d'entrée principal pour l'analyse de qualité.

    Architecture dual-path:
    1. Fast path: Si heuristiques >= threshold → question OK
    2. Slow path: Si heuristiques < threshold → analyse LLM

    Args:
        question: Question utilisateur
        conversation_context: Contexte conversationnel (optionnel)
        threshold: Seuil pour déclencher LLM (défaut: HEURISTIC_THRESHOLD)

    Returns:
        QualityAnalysisResult avec classification et suggestions
    """
    if not QUESTION_QUALITY_ENABLED:
        # Module désactivé → toujours OK
        return QualityAnalysisResult(
            classification=QuestionClassification.CLEAR,
            confidence=1.0,
            heuristic_score=1.0,
            reasoning="Quality check disabled",
            analyzed_by="disabled"
        )

    if threshold is None:
        threshold = HEURISTIC_THRESHOLD

    # Phase 1: Heuristiques rapides
    heuristic_score, heuristic_info = quick_quality_check(question)

    logger.info(
        f"📊 Heuristiques: score={heuristic_score:.3f}, "
        f"threshold={threshold}, phase={QUESTION_QUALITY_PHASE}"
    )

    # Fast path: question claire
    if heuristic_score >= threshold:
        logger.info(f"✅ Fast path: question OK (score={heuristic_score:.3f})")

        return QualityAnalysisResult(
            classification=QuestionClassification.CLEAR,
            confidence=heuristic_score,
            heuristic_score=heuristic_score,
            detected_terms=heuristic_info.get("detected_terms", []),
            suggested_terms=heuristic_info.get("suggested_terms", []),
            reasoning="Question claire (heuristiques)",
            analyzed_by="heuristics"
        )

    # Slow path: analyse LLM nécessaire
    logger.info(f"🔍 Slow path: analyse LLM (score={heuristic_score:.3f} < {threshold})")

    result = await analyze_with_llm(
        question=question,
        context=conversation_context,
        heuristic_info=heuristic_info
    )

    return result


# ============================================================================
# Utilitaires pour Feedback/Learning
# ============================================================================

def get_cache_key(question: str) -> str:
    """Génère une clé de cache pour une question."""
    normalized = normalize_question(question)
    return hashlib.md5(normalized.encode()).hexdigest()[:16]


async def store_quality_feedback(
    question: str,
    analysis_result: QualityAnalysisResult,
    search_results_count: int,
    max_similarity: float,
    message_id: Optional[str] = None,  # Accepte str ou UUID
    user_rating: Optional[int] = None,
    db_pool = None
) -> None:
    """
    Stocke le feedback de qualité pour apprentissage.

    Args:
        question: Question analysée
        analysis_result: Résultat de l'analyse
        search_results_count: Nombre de résultats de recherche
        max_similarity: Score de similarité max
        message_id: ID du message (optionnel)
        user_rating: Rating utilisateur -1/1 (optionnel)
        db_pool: Pool de connexions DB
    """
    if not db_pool:
        logger.debug("Pas de DB pool pour stocker feedback qualité")
        return

    try:
        # Convertir message_id en UUID si c'est une string
        message_uuid = None
        if message_id:
            message_uuid = UUID(message_id) if isinstance(message_id, str) else message_id

        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO question_quality_feedback (
                    original_question,
                    normalized_question,
                    heuristic_score,
                    llm_classification,
                    results_count,
                    max_similarity,
                    message_id,
                    user_rating
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT DO NOTHING
                """,
                question,
                normalize_question(question),
                analysis_result.heuristic_score,
                analysis_result.classification.value,
                search_results_count,
                max_similarity,
                message_uuid,  # UUID converti
                user_rating
            )
            logger.debug(f"📝 Feedback qualité stocké pour question")
    except Exception as e:
        logger.warning(f"⚠️ Erreur stockage feedback qualité: {e}")


# ============================================================================
# Export pour tests
# ============================================================================

__all__ = [
    "QuestionClassification",
    "QuestionSuggestion",
    "QualityAnalysisResult",
    "analyze_question_quality",
    "quick_quality_check",
    "analyze_with_llm",
    "store_quality_feedback",
    "QUESTION_QUALITY_ENABLED",
    "QUESTION_QUALITY_PHASE",
    "HEURISTIC_THRESHOLD",
]
