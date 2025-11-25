"""
Module de reformulation de questions basé sur les résultats de recherche.

Ce module fournit une approche GÉNÉRIQUE pour suggérer des reformulations
en extrayant le vocabulaire dynamiquement depuis les documents trouvés,
sans patterns hardcodés.

Architecture:
1. Probe Search: Recherche rapide (k=3) pour obtenir du contexte
2. Extraction: Vocabulaire dynamique depuis les documents
3. LLM Suggestions: Génération avec contexte documentaire
4. Fallback: Suggestions basées sur termes extraits si timeout

Author: RAGFab Team
Date: 2025-01-25
"""

import logging
import re
import json
import asyncio
from collections import Counter
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from uuid import UUID
import httpx

logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

import os

REFORMULATION_ENABLED = os.getenv("REFORMULATION_ENABLED", "true").lower() == "true"
REFORMULATION_PROBE_K = int(os.getenv("REFORMULATION_PROBE_K", "3"))
REFORMULATION_LLM_TIMEOUT = float(os.getenv("REFORMULATION_LLM_TIMEOUT", "10"))
REFORMULATION_HEURISTIC_THRESHOLD = float(os.getenv("REFORMULATION_HEURISTIC_THRESHOLD", "0.7"))

# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class ExtractedVocabulary:
    """Vocabulaire extrait dynamiquement des résultats de recherche."""
    terms: List[str] = field(default_factory=list)
    context_snippets: List[str] = field(default_factory=list)
    term_sources: Dict[str, str] = field(default_factory=dict)  # term -> document_title


@dataclass
class ReformulationSuggestion:
    """Une suggestion de reformulation."""
    text: str
    type: str  # 'vocabulary' | 'clarification' | 'expansion'
    reason: str
    source_document: Optional[str] = None


@dataclass
class ReformulationResult:
    """Résultat de l'analyse de reformulation."""
    needs_reformulation: bool
    suggestions: List[ReformulationSuggestion] = field(default_factory=list)
    extracted_terms: List[str] = field(default_factory=list)
    reasoning: Optional[str] = None
    analyzed_by: str = "probe_search"  # 'probe_search' | 'llm' | 'fallback' | 'disabled'

    def to_dict(self) -> Dict:
        """Convertit en dictionnaire pour la réponse API."""
        return {
            "needs_reformulation": self.needs_reformulation,
            "suggestions": [
                {
                    "text": s.text,
                    "type": s.type,
                    "reason": s.reason,
                    "source_document": s.source_document
                }
                for s in self.suggestions
            ],
            "extracted_terms": self.extracted_terms,
            "reasoning": self.reasoning,
            "analyzed_by": self.analyzed_by
        }


# ============================================================================
# Heuristiques Structurelles (Générique, sans vocabulaire domaine)
# ============================================================================

# Patterns structurels seulement - PAS de termes de domaine
STRUCTURAL_RED_FLAGS = [
    # Questions mono-mot
    (r"^(comment|pourquoi|quoi|ou|quand)\s*\?*$", "question_monoword", 0.5),
    # Début par conjonction (suite implicite)
    (r"^(et|ou|mais|donc)\s+", "starts_conjunction", 0.3),
    # Pronoms seuls
    (r"^(celui|celle|ceux|celles)[-\s]?(ci|la|là)?\s*\?*$", "pronouns_only", 0.5),
    # Questions ultra-courtes
    (r"^.{1,10}\?*$", "ultra_short", 0.3),
    # Pronoms flous sans contexte
    (r"^(ça|ca|cela)\s+", "vague_pronoun_start", 0.4),
    # "c'est quoi" très court
    (r"^c['']?est\s+quoi\s+\w{1,10}\s*\?*$", "cest_quoi_short", 0.3),
]

# Stopwords français
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


def compute_structural_score(question: str) -> float:
    """
    Calcule un score basé uniquement sur la structure de la question.
    PAS de vocabulaire de domaine - purement structurel.

    Returns:
        Score entre 0.0 et 1.0 (plus haut = meilleure structure)
    """
    question_lower = question.lower().strip()
    words = question_lower.split()
    word_count = len(words)

    # Score de longueur
    if word_count < 3:
        length_score = 0.3
    elif word_count < 5:
        length_score = 0.6
    elif word_count <= 30:
        length_score = 1.0
    elif word_count <= 50:
        length_score = 0.8
    else:
        length_score = 0.5

    # Score de structure grammaticale
    structure_score = 0.5
    question_words = {"comment", "pourquoi", "quand", "où", "quel", "quelle", "quels", "quelles"}
    action_verbs = {"faire", "créer", "modifier", "supprimer", "ajouter", "configurer", "trouver", "chercher"}

    if any(w in question_words for w in words[:3]):
        structure_score += 0.25
    if any(v in question_lower for v in action_verbs):
        structure_score += 0.25
    if question.strip().endswith("?"):
        structure_score += 0.1

    structure_score = min(1.0, structure_score)

    # Score de spécificité (sans vocabulaire domaine)
    specificity_score = 0.5
    # Présence de nombres significatifs
    if re.search(r'\d{3,}', question):
        specificity_score += 0.2
    # Présence de noms propres
    proper_nouns = re.findall(r'\b[A-Z][a-z]+\b', question)
    if proper_nouns:
        specificity_score += min(0.2, len(proper_nouns) * 0.1)
    # Termes entre guillemets
    if re.search(r'["«»\'].*?["«»\']', question):
        specificity_score += 0.1
    # Pénalité pour pronoms vagues
    vague_pronouns = ["ça", "ca", "celui", "celle", "ceux", "celles", "ceci", "cela"]
    if any(p in words for p in vague_pronouns):
        specificity_score -= 0.2

    specificity_score = max(0.0, min(1.0, specificity_score))

    # Score combiné
    base_score = (
        length_score * 0.30 +
        structure_score * 0.35 +
        specificity_score * 0.35
    )

    # Appliquer red flags structurels
    for pattern, flag_type, penalty in STRUCTURAL_RED_FLAGS:
        if re.search(pattern, question_lower, re.IGNORECASE):
            base_score *= (1 - penalty)
            logger.debug(f"Red flag '{flag_type}' détecté, pénalité {penalty}")

    return max(0.0, min(1.0, base_score))


# ============================================================================
# Probe Search (Recherche Rapide)
# ============================================================================

async def probe_search(
    question: str,
    db_pool,
    universe_ids: Optional[List[UUID]] = None,
    k: int = None
) -> List[dict]:
    """
    Recherche rapide pour extraire du contexte documentaire.

    - k résultats seulement (défaut: REFORMULATION_PROBE_K)
    - Pas de reranking
    - Pas de chunks adjacents
    - Target: <100ms

    Args:
        question: Question utilisateur
        db_pool: Pool de connexions DB
        universe_ids: Filtrage par univers
        k: Nombre de résultats (défaut: config)

    Returns:
        Liste de résultats avec content, document_title, similarity
    """
    if k is None:
        k = REFORMULATION_PROBE_K

    try:
        # Import local pour éviter circular import
        from app.utils.embeddings import get_embedding

        # Générer embedding de la question
        embedding = await get_embedding(question)

        async with db_pool.acquire() as conn:
            if universe_ids:
                results = await conn.fetch("""
                    SELECT c.content, c.metadata, d.title as document_title,
                           1 - (c.embedding <=> $1::vector) as similarity
                    FROM chunks c
                    JOIN documents d ON c.document_id = d.id
                    WHERE d.universe_id = ANY($2::uuid[])
                    ORDER BY c.embedding <=> $1::vector
                    LIMIT $3
                """, embedding, universe_ids, k)
            else:
                results = await conn.fetch("""
                    SELECT c.content, c.metadata, d.title as document_title,
                           1 - (c.embedding <=> $1::vector) as similarity
                    FROM chunks c
                    JOIN documents d ON c.document_id = d.id
                    ORDER BY c.embedding <=> $1::vector
                    LIMIT $2
                """, embedding, k)

        return [dict(r) for r in results]

    except Exception as e:
        logger.error(f"Erreur probe search: {e}", exc_info=True)
        return []


# ============================================================================
# Extraction Dynamique de Vocabulaire
# ============================================================================

def extract_vocabulary_from_search_results(
    search_results: List[dict],
    user_question: str
) -> ExtractedVocabulary:
    """
    Extrait le vocabulaire pertinent des documents trouvés.

    Méthodes d'extraction:
    1. Termes capitalisés (noms propres, systèmes, acronymes)
    2. Termes répétés dans plusieurs résultats (haute fréquence)
    3. Termes des titres de documents (souvent clés)
    4. Termes proches des mots de la question (contexte sémantique)

    Args:
        search_results: Résultats de probe_search
        user_question: Question originale

    Returns:
        ExtractedVocabulary avec termes classés par pertinence
    """
    if not search_results:
        return ExtractedVocabulary()

    extracted_terms = []
    term_sources = {}
    question_words = set(user_question.lower().split()) - FRENCH_STOPWORDS

    for result in search_results:
        content = result.get("content", "")
        title = result.get("document_title", "")

        # 1. Termes capitalisés (systèmes, noms propres, acronymes)
        capitalized = re.findall(r'\b[A-Z][a-zA-Z]{2,}(?:\s+[A-Z][a-zA-Z]+)*\b', content)
        for term in capitalized:
            if term.lower() not in question_words and len(term) > 2:
                extracted_terms.append(term)
                if term not in term_sources:
                    term_sources[term] = title

        # 2. Acronymes (tout en majuscules, 2-6 lettres)
        acronyms = re.findall(r'\b[A-Z]{2,6}\b', content)
        for acro in acronyms:
            if acro.lower() not in question_words:
                extracted_terms.append(acro)
                if acro not in term_sources:
                    term_sources[acro] = title

        # 3. Termes des titres (souvent les plus pertinents)
        title_words = [w for w in title.split() if len(w) > 3 and w.lower() not in FRENCH_STOPWORDS]
        for tw in title_words:
            if tw.lower() not in question_words:
                extracted_terms.append(tw)
                if tw not in term_sources:
                    term_sources[tw] = title

        # 4. Termes proches des mots de la question (contexte)
        for word in question_words:
            if len(word) > 3:
                content_lower = content.lower()
                for match in re.finditer(re.escape(word), content_lower):
                    start = max(0, match.start() - 50)
                    end = min(len(content), match.end() + 50)
                    context = content[start:end]
                    # Extraire mots significatifs du contexte
                    nearby_words = re.findall(r'\b\w{4,}\b', context)
                    for nw in nearby_words:
                        if nw.lower() not in question_words and nw.lower() not in FRENCH_STOPWORDS:
                            extracted_terms.append(nw)
                            if nw not in term_sources:
                                term_sources[nw] = title

    # Compter et classer les termes
    term_counts = Counter(t.lower() for t in extracted_terms)

    # Garder les termes qui apparaissent au moins 2 fois (ou 1 fois si capitalisé/acronyme)
    ranked_terms = []
    seen = set()
    for term, count in term_counts.most_common(15):
        if term not in seen:
            # Retrouver la forme originale (avec casse)
            original_form = next((t for t in extracted_terms if t.lower() == term), term)
            if count >= 2 or (original_form.isupper() and len(original_form) <= 6):
                ranked_terms.append(original_form)
                seen.add(term)

    # Context snippets pour le LLM
    context_snippets = [r.get("content", "")[:300] for r in search_results[:3]]

    return ExtractedVocabulary(
        terms=ranked_terms[:10],
        context_snippets=context_snippets,
        term_sources={k: v for k, v in term_sources.items() if k.lower() in seen}
    )


# ============================================================================
# Génération de Suggestions via LLM
# ============================================================================

LLM_GENERIC_PROMPT = """Tu reformules des questions pour améliorer la recherche documentaire.

QUESTION UTILISATEUR:
"{question}"

DOCUMENTS TROUVÉS (pour comprendre le vocabulaire du domaine):
{document_context}

TERMES FRÉQUENTS DANS CES DOCUMENTS:
{extracted_terms}

TÂCHE:
Analyse si la question peut être améliorée pour la recherche. Si oui, propose 1-3 reformulations qui:
- Utilisent les termes des documents ci-dessus (pas d'invention)
- Gardent le sens original de la question
- Sont plus précises pour une recherche documentaire

RÉPONDS EN JSON:
{{
  "needs_reformulation": true/false,
  "reasoning": "Explication courte",
  "suggestions": [
    {{"text": "Question reformulée", "reason": "Pourquoi cette reformulation"}}
  ]
}}

IMPORTANT: Si la question est déjà claire ou si les documents ne suggèrent pas de meilleur vocabulaire, retourne needs_reformulation=false."""


async def generate_llm_suggestions(
    question: str,
    vocabulary: ExtractedVocabulary,
    timeout: float = None
) -> Tuple[bool, List[ReformulationSuggestion], str]:
    """
    Génère des suggestions de reformulation via LLM avec contexte documentaire.

    Args:
        question: Question originale
        vocabulary: Vocabulaire extrait des documents
        timeout: Timeout en secondes (défaut: config)

    Returns:
        (needs_reformulation, suggestions, reasoning)
    """
    if timeout is None:
        timeout = REFORMULATION_LLM_TIMEOUT

    try:
        from app.utils.generic_llm_provider import get_generic_llm_model

        model = get_generic_llm_model()
        api_url = model.api_url.rstrip('/')

        # Construire le prompt
        document_context = "\n---\n".join(vocabulary.context_snippets) if vocabulary.context_snippets else "Aucun document trouvé"
        extracted_terms = ", ".join(vocabulary.terms) if vocabulary.terms else "Aucun terme extrait"

        prompt = LLM_GENERIC_PROMPT.format(
            question=question,
            document_context=document_context,
            extracted_terms=extracted_terms
        )

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{api_url}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {model.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model.model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                    "max_tokens": 500
                }
            )
            response.raise_for_status()
            result = response.json()

        content = result["choices"][0]["message"]["content"].strip()

        # Parser JSON (gérer les code blocks markdown)
        if content.startswith("```"):
            content = re.sub(r'^```json?\s*', '', content)
            content = re.sub(r'\s*```$', '', content)

        analysis = json.loads(content)

        needs_reformulation = analysis.get("needs_reformulation", False)
        reasoning = analysis.get("reasoning", "")

        suggestions = []
        for s in analysis.get("suggestions", [])[:3]:
            suggestions.append(ReformulationSuggestion(
                text=s.get("text", ""),
                type="llm_suggestion",
                reason=s.get("reason", ""),
                source_document=None
            ))

        logger.info(
            f"🤖 LLM reformulation: needs={needs_reformulation}, "
            f"suggestions={len(suggestions)}"
        )

        return (needs_reformulation, suggestions, reasoning)

    except json.JSONDecodeError as e:
        logger.warning(f"Erreur parsing JSON LLM: {e}")
        return (False, [], f"Erreur parsing: {e}")

    except httpx.TimeoutException:
        logger.warning(f"Timeout LLM ({timeout}s)")
        raise  # Propager pour utiliser fallback

    except Exception as e:
        logger.error(f"Erreur LLM suggestions: {e}", exc_info=True)
        return (False, [], f"Erreur: {e}")


# ============================================================================
# Fallback: Suggestions basées sur termes extraits
# ============================================================================

def generate_term_based_suggestions(
    question: str,
    vocabulary: ExtractedVocabulary
) -> List[ReformulationSuggestion]:
    """
    Génère des suggestions simples basées sur les termes extraits.
    Utilisé comme fallback si le LLM timeout.

    Args:
        question: Question originale
        vocabulary: Vocabulaire extrait

    Returns:
        Liste de suggestions (max 2)
    """
    if not vocabulary.terms:
        return []

    suggestions = []
    question_lower = question.lower()
    question_clean = question.rstrip("?").strip()

    for term in vocabulary.terms[:3]:
        if term.lower() not in question_lower:
            source_doc = vocabulary.term_sources.get(term, "documents trouvés")

            # Créer une reformulation simple
            suggestion_text = f"{question_clean} concernant {term} ?"

            suggestions.append(ReformulationSuggestion(
                text=suggestion_text,
                type="vocabulary",
                reason=f"Terme '{term}' trouvé dans les documents",
                source_document=source_doc
            ))

    return suggestions[:2]


# ============================================================================
# Point d'Entrée Principal
# ============================================================================

async def analyze_and_suggest_reformulation(
    question: str,
    db_pool,
    universe_ids: Optional[List[UUID]] = None,
    conversation_context: Optional[Dict] = None
) -> ReformulationResult:
    """
    Point d'entrée principal pour l'analyse de reformulation.

    Flow:
    1. Score structurel (heuristiques génériques)
    2. Si score bas → Probe search
    3. Extraction vocabulaire dynamique
    4. LLM suggestions (avec timeout)
    5. Fallback sur termes si timeout

    Args:
        question: Question utilisateur
        db_pool: Pool de connexions DB
        universe_ids: Filtrage par univers
        conversation_context: Contexte conversationnel (optionnel)

    Returns:
        ReformulationResult avec suggestions éventuelles
    """
    if not REFORMULATION_ENABLED:
        return ReformulationResult(
            needs_reformulation=False,
            reasoning="Reformulation désactivée",
            analyzed_by="disabled"
        )

    # 1. Score structurel
    structural_score = compute_structural_score(question)
    logger.info(f"📊 Score structurel: {structural_score:.3f}, seuil: {REFORMULATION_HEURISTIC_THRESHOLD}")

    # Fast path si question structurellement OK
    if structural_score >= REFORMULATION_HEURISTIC_THRESHOLD:
        logger.info(f"✅ Fast path: question structurellement OK")
        return ReformulationResult(
            needs_reformulation=False,
            reasoning="Question structurellement claire",
            analyzed_by="heuristics"
        )

    # 2. Probe search pour obtenir du contexte
    logger.info(f"🔍 Probe search (k={REFORMULATION_PROBE_K})")
    probe_results = await probe_search(
        question=question,
        db_pool=db_pool,
        universe_ids=universe_ids
    )

    if not probe_results:
        logger.warning("⚠️ Probe search: aucun résultat")
        return ReformulationResult(
            needs_reformulation=False,
            reasoning="Aucun document trouvé pour contexte",
            analyzed_by="probe_search"
        )

    # 3. Extraction vocabulaire dynamique
    vocabulary = extract_vocabulary_from_search_results(probe_results, question)
    logger.info(f"📚 Vocabulaire extrait: {len(vocabulary.terms)} termes")

    # 4. LLM suggestions avec timeout
    try:
        needs_reformulation, suggestions, reasoning = await asyncio.wait_for(
            generate_llm_suggestions(question, vocabulary),
            timeout=REFORMULATION_LLM_TIMEOUT
        )

        return ReformulationResult(
            needs_reformulation=needs_reformulation,
            suggestions=suggestions,
            extracted_terms=vocabulary.terms,
            reasoning=reasoning,
            analyzed_by="llm"
        )

    except asyncio.TimeoutError:
        logger.warning(f"⏱️ Timeout LLM ({REFORMULATION_LLM_TIMEOUT}s), fallback sur termes")

        # 5. Fallback: suggestions basées sur termes extraits
        suggestions = generate_term_based_suggestions(question, vocabulary)

        return ReformulationResult(
            needs_reformulation=len(suggestions) > 0,
            suggestions=suggestions,
            extracted_terms=vocabulary.terms,
            reasoning="Suggestions basées sur vocabulaire extrait (timeout LLM)",
            analyzed_by="fallback"
        )


# ============================================================================
# Export
# ============================================================================

__all__ = [
    "ReformulationResult",
    "ReformulationSuggestion",
    "ExtractedVocabulary",
    "analyze_and_suggest_reformulation",
    "compute_structural_score",
    "probe_search",
    "extract_vocabulary_from_search_results",
    "generate_llm_suggestions",
    "generate_term_based_suggestions",
    "REFORMULATION_ENABLED",
    "REFORMULATION_HEURISTIC_THRESHOLD",
]
