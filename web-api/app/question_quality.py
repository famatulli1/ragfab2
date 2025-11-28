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
HEURISTIC_THRESHOLD = float(os.getenv("QUESTION_QUALITY_HEURISTIC_THRESHOLD", "0.65"))  # Réduit de 0.75 pour plus de fast path
LLM_CONFIDENCE_THRESHOLD = float(os.getenv("QUESTION_QUALITY_LLM_CONFIDENCE_THRESHOLD", "0.75"))
LLM_TIMEOUT = float(os.getenv("QUESTION_QUALITY_LLM_TIMEOUT", "3"))  # Réduit de 5s

# Termes techniques connus (ne pas pénaliser les questions courtes les contenant)
KNOWN_TECHNICAL_TERMS = {
    # Authentification & Sécurité
    "sso", "jwt", "oauth", "oauth2", "ldap", "saml", "mfa", "2fa", "totp",
    "api", "apikey", "bearer", "token", "auth", "rbac", "acl",
    # Protocoles & Web
    "http", "https", "rest", "graphql", "grpc", "webhook", "websocket", "ws",
    "ssl", "tls", "cors", "csrf", "xss",
    # Data & Storage
    "sql", "nosql", "json", "xml", "csv", "yaml", "pdf", "xlsx",
    "postgres", "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
    # RAG & AI
    "rag", "llm", "embedding", "embeddings", "vector", "chunk", "chunks",
    "rerank", "reranking", "ocr", "vlm", "nlp", "gpt", "mistral",
    # DevOps & Infra
    "docker", "kubernetes", "k8s", "ci", "cd", "git", "npm", "pip",
    "aws", "azure", "gcp", "s3", "cdn", "dns", "ip", "url", "uri",
    # Formats & Encodages
    "utf8", "base64", "md5", "sha256", "uuid", "guid",
}


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
# Format: (pattern, flag_type, penalty, skip_if_technical)
# skip_if_technical=True → ne pas pénaliser si la question contient un terme technique
RED_FLAG_PATTERNS = [
    # Questions mono-mot ou très courtes
    (r"^(comment|pourquoi|quoi|ou|quand)\s*\?*$", "question_monoword", 0.5, False),
    # "c'est quoi X" sans contexte - SKIP si terme technique (ex: "c'est quoi le JWT?")
    (r"^c['']?est\s+quoi\s+\w+\s*\?*$", "cest_quoi_vague", 0.4, True),
    # Trop vague
    (r"^(ca|ça)\s+(marche|fonctionne|se passe)\s*(comment)?\s*\?*$", "ca_vague", 0.5, False),
    # Début par conjonction (suite implicite)
    (r"^(et|ou|mais|donc)\s+", "starts_conjunction", 0.3, False),
    # Pronoms seuls
    (r"^(celui|celle|ceux|celles)[-\s]?(ci|la|là)?\s*\?*$", "pronouns_only", 0.5, False),
    # Multiples espaces (potentiel copier-coller mal formaté)
    (r"\s{3,}", "multiple_spaces", 0.1, False),
    # Questions ultra-courtes - SKIP si terme technique (ex: "SSO?", "JWT?")
    (r"^.{1,10}\?*$", "ultra_short", 0.3, True),
]


def has_technical_term(question: str) -> bool:
    """
    Détecte si la question contient un terme technique connu.

    Les questions courtes avec des termes techniques (SSO?, JWT?, API?)
    ne doivent pas être pénalisées car elles sont souvent légitimes.
    """
    words = set(re.findall(r'\b\w+\b', question.lower()))
    return bool(words & KNOWN_TECHNICAL_TERMS)

# Green flags: indicateurs de bonne question (STRUCTURELS uniquement)
# Note: Les termes métier sont maintenant extraits dynamiquement via search_informed_reformulation.py
GREEN_FLAG_PATTERNS = [
    # Questions structurées (forme grammaticale correcte)
    (r"^(comment|quelle?\s+est|o[uù]\s+(est|se\s+trouve|trouver))\s+.{15,}", "structured_question", 0.15),
    # Références numériques (IDs, numéros) - générique
    (r"\b(n[°o]?\s*\d+|ref\.?\s*\d+|id\s*[:=]?\s*\d+)\b", "has_reference", 0.1),
    # Termes techniques génériques (procédures, étapes)
    (r"\b(proc[ée]dure|protocole|[ée]tape|processus)\b", "procedure_term", 0.1),
]

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
    Score basé sur la structure de la question (pas de vocabulaire domaine hardcodé).

    Note: L'extraction de vocabulaire métier est maintenant déléguée à
    search_informed_reformulation.py qui extrait dynamiquement depuis les résultats.

    Retourne (score, termes_detectes, termes_suggeres)
    """
    question_lower = question.lower()
    detected_terms = []
    suggested_terms = []  # Rempli dynamiquement par search_informed_reformulation

    # Vérifier green flags (patterns structurels uniquement)
    structure_score = 0.0
    for pattern, term_type, bonus in GREEN_FLAG_PATTERNS:
        if re.search(pattern, question_lower, re.IGNORECASE):
            match = re.search(pattern, question_lower, re.IGNORECASE)
            if match:
                detected_terms.append(match.group())
            structure_score += bonus

    # Score de base: neutre, sera enrichi par probe search
    # Une question générique obtient 0.5, les patterns structurels ajoutent des bonus
    base_score = 0.5 + min(0.3, structure_score)

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

    Les questions contenant des termes techniques connus bénéficient:
    - Skip des pénalités red_flag marquées skip_if_technical
    - Bonus de score +0.15
    """
    question_lower = question.lower()
    score = base_score
    reasons = []

    # Détecter si la question contient un terme technique
    is_technical = has_technical_term(question)

    # Red flags (pénalités)
    for item in RED_FLAG_PATTERNS:
        pattern, flag_type, penalty = item[0], item[1], item[2]
        skip_if_tech = item[3] if len(item) > 3 else False

        # Skip la pénalité si terme technique et pattern le permet
        if skip_if_tech and is_technical:
            continue

        if re.search(pattern, question_lower, re.IGNORECASE):
            score *= (1 - penalty)
            reasons.append(f"red_flag:{flag_type}")

    # Bonus pour questions avec termes techniques
    if is_technical:
        score = min(1.0, score + 0.15)
        reasons.append("green_flag:technical_term")

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

LLM_ANALYSIS_PROMPT = """Tu es un assistant de contrôle qualité pour un système RAG documentaire.

QUESTION UTILISATEUR: "{question}"

{context_section}

ÉVALUE LA QUALITÉ STRUCTURELLE de la question:
- Longueur et précision
- Clarté grammaticale
- Présence de contexte suffisant

CLASSIFIE LA QUESTION parmi:
- clear: Question bien formulée, suffisamment précise pour une recherche documentaire
- too_vague: Question trop générale, manque de précision (ex: "comment faire ?", "c'est quoi le truc")
- missing_context: Utilise des références floues sans contexte ("celui-là", "ça", "cette chose")
- out_of_scope: Question clairement hors périmètre (météo, recettes, blagues, etc.)

Note: Ne pas classifier "wrong_vocabulary" - le vocabulaire métier sera extrait dynamiquement des documents.

RÉPONDS UNIQUEMENT EN JSON (pas de texte avant/après):
{{
  "classification": "clear|too_vague|missing_context|out_of_scope",
  "confidence": 0.0-1.0,
  "reasoning": "Explication en 1 phrase"
}}"""


async def analyze_with_llm(
    question: str,
    context: Optional[Dict] = None,
    heuristic_info: Optional[Dict] = None
) -> QualityAnalysisResult:
    """
    Analyse structurelle via LLM pour les questions ambiguës.

    Note: Ce module analyse uniquement la STRUCTURE de la question.
    Les suggestions de vocabulaire sont générées par search_informed_reformulation.py

    Args:
        question: Question utilisateur
        context: Contexte conversationnel (optionnel)
        heuristic_info: Info des heuristiques

    Returns:
        QualityAnalysisResult avec classification (sans suggestions domaine)
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
                    "max_tokens": 200  # Réponse simplifiée
                }
            )
            response.raise_for_status()
            result = response.json()

            content = result["choices"][0]["message"]["content"].strip()

            # Parser le JSON (nettoyer markdown si présent)
            if content.startswith("```"):
                content = re.sub(r'^```json?\s*', '', content)
                content = re.sub(r'\s*```$', '', content)

            analysis = json.loads(content)

            classification = QuestionClassification(analysis.get("classification", "too_vague"))
            confidence = float(analysis.get("confidence", 0.5))
            reasoning = analysis.get("reasoning", "")

            logger.info(
                f"🤖 Analyse LLM structurelle: classification={classification.value}, "
                f"confidence={confidence:.2f}"
            )

            return QualityAnalysisResult(
                classification=classification,
                confidence=confidence,
                heuristic_score=heuristic_info.get("scores", {}).get("final", 0.5) if heuristic_info else 0.5,
                suggestions=[],  # Suggestions générées par search_informed_reformulation
                detected_terms=heuristic_info.get("detected_terms", []) if heuristic_info else [],
                suggested_terms=[],  # Termes extraits par search_informed_reformulation
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


def _generate_heuristic_suggestions(question: str, suggested_terms: List[str]) -> List[QuestionSuggestion]:
    """
    Génère des suggestions structurelles simples (sans vocabulaire domaine).

    Note: Les suggestions avec vocabulaire métier sont générées par
    search_informed_reformulation.py qui extrait dynamiquement depuis les documents.
    """
    # Ce module ne génère plus de suggestions domaine-spécifiques
    # Les suggestions seront ajoutées par search_informed_reformulation.py
    return []


def _fallback_result(
    question: str,
    heuristic_info: Optional[Dict],
    error_reason: str
) -> QualityAnalysisResult:
    """
    Génère un résultat de fallback basé sur les heuristiques structurelles.

    Note: Les suggestions de vocabulaire seront ajoutées par
    search_informed_reformulation.py si nécessaire.
    """
    heuristic_score = heuristic_info.get("scores", {}).get("final", 0.5) if heuristic_info else 0.5

    # Déterminer classification basée uniquement sur le score structurel
    if heuristic_score >= HEURISTIC_THRESHOLD:
        classification = QuestionClassification.CLEAR
    else:
        classification = QuestionClassification.TOO_VAGUE

    return QualityAnalysisResult(
        classification=classification,
        confidence=heuristic_score,
        heuristic_score=heuristic_score,
        suggestions=[],  # Ajoutées par search_informed_reformulation
        detected_terms=heuristic_info.get("detected_terms", []) if heuristic_info else [],
        suggested_terms=[],  # Extraits par search_informed_reformulation
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
# Cache en Mémoire pour Analyse de Qualité
# ============================================================================

# Cache simple en mémoire (éviction par taille max)
_quality_cache: Dict[str, QualityAnalysisResult] = {}
_CACHE_MAX_SIZE = int(os.getenv("QUESTION_QUALITY_CACHE_SIZE", "500"))
_cache_hits = 0
_cache_misses = 0


async def analyze_question_quality_cached(
    question: str,
    conversation_context: Optional[Dict] = None,
    threshold: float = None
) -> QualityAnalysisResult:
    """
    Version cachée de analyze_question_quality.

    Le cache utilise la question normalisée comme clé.
    TTL géré par redémarrage de l'application.

    Args:
        question: Question utilisateur
        conversation_context: Contexte conversationnel (optionnel)
        threshold: Seuil pour déclencher LLM

    Returns:
        QualityAnalysisResult (depuis cache ou calculé)
    """
    global _cache_hits, _cache_misses

    cache_key = get_cache_key(question)

    # Check cache
    if cache_key in _quality_cache:
        _cache_hits += 1
        logger.debug(f"⚡ Cache HIT: {cache_key[:8]}... (hits={_cache_hits})")
        return _quality_cache[cache_key]

    _cache_misses += 1

    # Calculer le résultat
    result = await analyze_question_quality(
        question=question,
        conversation_context=conversation_context,
        threshold=threshold
    )

    # Éviction simple si cache plein
    if len(_quality_cache) >= _CACHE_MAX_SIZE:
        logger.info(f"🗑️ Cache plein ({_CACHE_MAX_SIZE}), éviction complète")
        _quality_cache.clear()

    # Stocker dans le cache
    _quality_cache[cache_key] = result
    logger.debug(f"💾 Cache MISS -> stored: {cache_key[:8]}... (size={len(_quality_cache)})")

    return result


def get_cache_stats() -> Dict:
    """Retourne les statistiques du cache."""
    total = _cache_hits + _cache_misses
    hit_rate = (_cache_hits / total * 100) if total > 0 else 0
    return {
        "size": len(_quality_cache),
        "max_size": _CACHE_MAX_SIZE,
        "hits": _cache_hits,
        "misses": _cache_misses,
        "hit_rate_percent": round(hit_rate, 1)
    }


def clear_quality_cache() -> int:
    """Vide le cache et retourne le nombre d'entrées supprimées."""
    global _cache_hits, _cache_misses
    count = len(_quality_cache)
    _quality_cache.clear()
    _cache_hits = 0
    _cache_misses = 0
    logger.info(f"🗑️ Cache vidé: {count} entrées supprimées")
    return count


# ============================================================================
# Export pour tests
# ============================================================================

__all__ = [
    "QuestionClassification",
    "QuestionSuggestion",
    "QualityAnalysisResult",
    "analyze_question_quality",
    "analyze_question_quality_cached",
    "quick_quality_check",
    "analyze_with_llm",
    "store_quality_feedback",
    "get_cache_stats",
    "clear_quality_cache",
    "has_technical_term",
    "KNOWN_TECHNICAL_TERMS",
    "QUESTION_QUALITY_ENABLED",
    "QUESTION_QUALITY_PHASE",
    "HEURISTIC_THRESHOLD",
]
