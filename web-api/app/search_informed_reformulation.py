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
REFORMULATION_LLM_TIMEOUT = float(os.getenv("REFORMULATION_LLM_TIMEOUT", "8"))  # Réduit de 25s
REFORMULATION_HEURISTIC_THRESHOLD = float(os.getenv("REFORMULATION_HEURISTIC_THRESHOLD", "0.65"))  # Aligné avec question_quality

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

# Patterns à exclure des titres de documents (noms de fichiers, versions, mots génériques)
TITLE_EXCLUSION_PATTERNS = [
    r'.*\.(pdf|docx?|xlsx?|pptx?|txt|md|html?)$',  # Extensions de fichiers
    r'.*_V\d+.*',  # Patterns de version (_V25, _V1.2)
    r'.*\.\w+_V\d+.*',  # Patterns comme "Webmail.Administration_V25"
    r'^v?\d+(\.\d+)*$',  # Numéros de version seuls
    r'.*V\d+\.?\d*$',  # Se termine par version (inistration_V25, Admin_V2.1)
    r'^[a-z]*tion_V\d+',  # Mots cassés finissant par "tion_V25" (inistration_V25)
    r'^\d+$',  # Nombres seuls
]

# Mots génériques à exclure (métadonnées et termes non pertinents pour suggestions)
GENERIC_TITLE_WORDS = {
    # Métadonnées de documents
    'document', 'documents', 'fichier', 'fichiers', 'file', 'files',
    'guide', 'manuel', 'manual', 'procedure', 'procédure', 'process',
    'version', 'administration', 'configuration', 'installation',
    # Noms de produits/services génériques
    'webmail', 'outlook', 'office', 'microsoft', 'google', 'gmail',
    # Mots trop génériques pour être utiles
    'cas', 'type', 'mode', 'liste', 'page', 'menu', 'option', 'onglet',
    'bouton', 'clic', 'cliquez', 'sélectionner', 'choisir',
    'suivant', 'précédent', 'exemple', 'note', 'remarque', 'attention',
    'voir', 'figure', 'image', 'tableau', 'section', 'partie', 'chapitre',
}


def is_valid_vocabulary_term(term: str) -> bool:
    """
    Vérifie si un terme extrait est pertinent pour les suggestions.

    Exclut:
    - Mots génériques (Document, Guide, Manuel, Cas, etc.)
    - Noms de fichiers avec extensions
    - Patterns de version (_V25, V1.2, inistration_V25, etc.)
    - Termes contenant des points (sauf acronymes)
    - Mots trop génériques pour être utiles dans une suggestion

    Args:
        term: Le terme à valider

    Returns:
        True si le terme est pertinent pour les suggestions
    """
    term_lower = term.lower()

    # Exclure mots génériques
    if term_lower in GENERIC_TITLE_WORDS:
        return False

    # Exclure patterns de fichiers/versions
    for pattern in TITLE_EXCLUSION_PATTERNS:
        if re.match(pattern, term, re.IGNORECASE):
            return False

    # Exclure si contient un point (probablement nom de fichier)
    # Exception: garder les acronymes comme "B.A.L."
    if '.' in term and not term.isupper():
        return False

    return True


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
        # Générer l'embedding via le service HTTP (même méthode que main.py)
        embeddings_url = os.getenv("EMBEDDINGS_API_URL", "http://ragfab-embeddings:8001")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{embeddings_url}/embed",
                json={"text": question},
                timeout=10.0
            )
            response.raise_for_status()
            embedding = response.json()["embedding"]

        # Convertir en string pour PostgreSQL
        embedding_str = "[" + ",".join(map(str, embedding)) + "]"

        logger.info(f"🔍 Probe search: embedding généré ({len(embedding)} dims), universe_ids={universe_ids}")

        async with db_pool.acquire() as conn:
            if universe_ids:
                # Convertir les UUIDs en liste pour PostgreSQL
                universe_list = [str(uid) for uid in universe_ids]
                logger.info(f"🔍 Probe search: filtrage sur {len(universe_list)} univers: {universe_list}")

                results = await conn.fetch("""
                    SELECT c.content, c.metadata, d.title as document_title,
                           1 - (c.embedding <=> $1::vector) as similarity
                    FROM chunks c
                    JOIN documents d ON c.document_id = d.id
                    WHERE d.universe_id = ANY($2::uuid[])
                    ORDER BY c.embedding <=> $1::vector
                    LIMIT $3
                """, embedding_str, universe_list, k)
            else:
                logger.info(f"🔍 Probe search: pas de filtrage univers")
                results = await conn.fetch("""
                    SELECT c.content, c.metadata, d.title as document_title,
                           1 - (c.embedding <=> $1::vector) as similarity
                    FROM chunks c
                    JOIN documents d ON c.document_id = d.id
                    ORDER BY c.embedding <=> $1::vector
                    LIMIT $2
                """, embedding_str, k)

        logger.info(f"✅ Probe search: {len(results)} résultats trouvés")
        return [dict(r) for r in results]

    except Exception as e:
        logger.error(f"❌ Erreur probe search: {e}", exc_info=True)
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

        # 3. Termes des titres (filtrés pour exclure métadonnées)
        title_words = [w for w in title.split() if len(w) > 3 and w.lower() not in FRENCH_STOPWORDS]
        for tw in title_words:
            # Filtrer les termes non pertinents (noms de fichiers, mots génériques)
            if tw.lower() not in question_words and is_valid_vocabulary_term(tw):
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
    # ET qui passent le filtre de validité (pas de métadonnées/noms de fichiers)
    ranked_terms = []
    seen = set()
    for term, count in term_counts.most_common(20):  # Plus de candidats pour compenser filtrage
        if term not in seen:
            # Retrouver la forme originale (avec casse)
            original_form = next((t for t in extracted_terms if t.lower() == term), term)
            # Filtrer les termes non pertinents (métadonnées, noms de fichiers, mots génériques)
            if not is_valid_vocabulary_term(original_form):
                continue
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

QUESTION UTILISATEUR: "{question}"

INTENTION DÉTECTÉE: {detected_intent}

DOCUMENTS TROUVÉS:
{document_context}

TERMES CLÉS EXTRAITS: {extracted_terms}

RÈGLES CRITIQUES:
1. PRÉSERVE L'INTENTION: Si l'utilisateur demande "comment configurer", garde "configurer" (pas "comprendre" ou "expliquer")
2. AJOUTE DE LA SPÉCIFICITÉ avec les termes extraits des documents
3. NE CHANGE PAS LE SENS de la question
4. MAX 15 mots par suggestion
5. UTILISE UNIQUEMENT les termes extraits (pas d'invention)

EXEMPLES CORRECTS:
- "comment configurer ?" + termes=[SSO, LDAP] → "Comment configurer le SSO LDAP ?"
- "ça marche pas" + termes=[OAuth, authentification] → "Pourquoi l'authentification OAuth ne fonctionne pas ?"
- "c'est quoi le truc" + termes=[JWT, token] → "Qu'est-ce que le JWT ?"

EXEMPLES INCORRECTS (à éviter):
- "comment configurer ?" → "Qu'est-ce que le SSO ?" (change l'intention configurer→expliquer)
- "ça marche comment" → "Comment fonctionne OAuth ?" si l'utilisateur voulait résoudre un problème

RÉPONDS EN JSON:
{{
  "needs_reformulation": true/false,
  "reasoning": "Explication en 1 phrase",
  "suggestions": [
    {{"text": "Question reformulée", "reason": "Utilise le terme X pour plus de précision"}}
  ]
}}

NE REFORMULE PAS SI:
- La question est déjà spécifique et claire
- Les documents ne suggèrent pas de meilleur vocabulaire
- L'intention ne peut pas être déterminée"""


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

        # Détecter l'intention pour préserver le sens
        intent_type, preserve_verb, intent_label = detect_intent(question)
        detected_intent = f"{intent_label}"
        if preserve_verb:
            detected_intent += f" (préserver le verbe: {preserve_verb})"

        logger.debug(f"🎯 Intention détectée: {intent_type} -> {intent_label}")

        # Construire le prompt
        document_context = "\n---\n".join(vocabulary.context_snippets) if vocabulary.context_snippets else "Aucun document trouvé"
        extracted_terms = ", ".join(vocabulary.terms) if vocabulary.terms else "Aucun terme extrait"

        prompt = LLM_GENERIC_PROMPT.format(
            question=question,
            detected_intent=detected_intent,
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
# Détection d'Intention (pour préservation dans reformulations)
# ============================================================================

# Patterns d'intention avec action associée
INTENT_PATTERNS = {
    "howto_configure": {
        "patterns": [
            r"comment\s+(configurer|paramétrer|régler|ajuster|modifier\s+les?\s+paramètres?)",
            r"(configuration|paramétrage)\s+de",
        ],
        "label": "Configuration/Paramétrage",
        "preserve_verb": "configurer"
    },
    "howto_create": {
        "patterns": [
            r"comment\s+(créer|ajouter|mettre\s+en\s+place|installer|générer)",
            r"(création|ajout|installation)\s+d",
        ],
        "label": "Création/Installation",
        "preserve_verb": "créer"
    },
    "howto_fix": {
        "patterns": [
            r"comment\s+(réparer|corriger|résoudre|fixer|débugger)",
            r"(ne\s+(marche|fonctionne)\s+(pas|plus))",
            r"(erreur|problème|bug|échec)\s+(avec|de|sur)",
            r"ça\s+(marche|fonctionne)\s+(pas|plus)",
        ],
        "label": "Résolution de problème",
        "preserve_verb": "résoudre"
    },
    "howto_use": {
        "patterns": [
            r"comment\s+(utiliser|employer|se\s+servir\s+de)",
            r"(utilisation|usage)\s+de",
        ],
        "label": "Utilisation",
        "preserve_verb": "utiliser"
    },
    "explain": {
        "patterns": [
            r"c['']?est\s+quoi",
            r"qu['']?est[- ]ce\s+que",
            r"(définition|signification)\s+de",
            r"à\s+quoi\s+sert",
        ],
        "label": "Explication/Définition",
        "preserve_verb": None
    },
    "locate": {
        "patterns": [
            r"où\s+(trouver|est|se\s+trouve)",
            r"dans\s+quelle?\s+(section|partie|menu)",
        ],
        "label": "Localisation",
        "preserve_verb": "trouver"
    },
    "compare": {
        "patterns": [
            r"(différence|comparaison)\s+entre",
            r"(quel|quelle)\s+est\s+(la\s+différence|mieux)",
        ],
        "label": "Comparaison",
        "preserve_verb": None
    },
}


def detect_intent(question: str) -> Tuple[str, Optional[str], str]:
    """
    Détecte l'intention de la question pour préserver le sens dans les reformulations.

    Returns:
        (intent_type, preserve_verb, human_label)
        - intent_type: clé technique (howto_configure, explain, etc.)
        - preserve_verb: verbe à préserver dans les reformulations (ou None)
        - human_label: description lisible pour le prompt LLM
    """
    question_lower = question.lower()

    for intent_type, config in INTENT_PATTERNS.items():
        for pattern in config["patterns"]:
            if re.search(pattern, question_lower, re.IGNORECASE):
                return (
                    intent_type,
                    config.get("preserve_verb"),
                    config["label"]
                )

    # Intention générique si aucun pattern ne matche
    return ("generic", None, "Question générale")


# ============================================================================
# Fallback: Suggestions basées sur termes extraits (Amélioré)
# ============================================================================

# Patterns de questions françaises pour reformulation intelligente
QUESTION_PATTERNS = {
    "comment": {
        "patterns": [
            "Comment {action} {term} ?",
            "Quelle est la procédure pour {action} avec {term} ?",
            "Comment fonctionne {term} ?",
        ],
        "verbs": ["faire", "configurer", "utiliser", "créer", "modifier", "gérer"]
    },
    "pourquoi": {
        "patterns": [
            "Pourquoi {term} {verb} ?",
            "Quelle est la raison de {term} ?",
            "Pour quelle raison {term} est {adjective} ?",
        ],
        "verbs": ["fonctionne", "est nécessaire", "doit être", "a été conçu"]
    },
    "quoi": {
        "patterns": [
            "Qu'est-ce que {term} ?",
            "Quelle est la définition de {term} ?",
            "À quoi sert {term} ?",
        ],
        "verbs": []
    },
    "ou": {
        "patterns": [
            "Où trouver {term} ?",
            "Dans quelle section est {term} ?",
            "Où se situe {term} dans le système ?",
        ],
        "verbs": []
    },
    "generic": {
        "patterns": [
            "Pouvez-vous expliquer {term} ?",
            "Quelles sont les informations sur {term} ?",
            "Comment {term} fonctionne-t-il ?",
        ],
        "verbs": []
    }
}


def detect_question_type(question: str) -> str:
    """Détecte le type de question pour choisir le bon pattern de reformulation."""
    question_lower = question.lower().strip()

    if question_lower.startswith("comment"):
        return "comment"
    elif question_lower.startswith("pourquoi"):
        return "pourquoi"
    elif "quoi" in question_lower or "qu'est" in question_lower or "c'est quoi" in question_lower:
        return "quoi"
    elif question_lower.startswith("où") or question_lower.startswith("ou "):
        return "ou"
    else:
        return "generic"


def extract_action_from_question(question: str) -> Optional[str]:
    """Extrait l'action principale de la question si présente."""
    question_lower = question.lower()

    # Verbes d'action courants
    action_verbs = [
        "faire", "configurer", "utiliser", "créer", "modifier", "supprimer",
        "ajouter", "gérer", "installer", "désinstaller", "activer", "désactiver",
        "réparer", "corriger", "améliorer", "optimiser", "résoudre", "remettre"
    ]

    for verb in action_verbs:
        if verb in question_lower:
            return verb

    return None


def generate_term_based_suggestions(
    question: str,
    vocabulary: ExtractedVocabulary
) -> List[ReformulationSuggestion]:
    """
    Génère des suggestions intelligentes basées sur les termes extraits.
    Utilisé comme fallback si le LLM timeout.

    Améliorations par rapport à la version basique:
    1. Détection du type de question (comment, pourquoi, quoi, etc.)
    2. Extraction de l'action de la question originale
    3. Génération de reformulations naturelles avec les termes extraits
    4. Suggestions variées (pas juste "concernant X")

    Args:
        question: Question originale
        vocabulary: Vocabulaire extrait

    Returns:
        Liste de suggestions (max 3)
    """
    if not vocabulary.terms:
        return []

    suggestions = []
    question_lower = question.lower()
    question_type = detect_question_type(question)
    action = extract_action_from_question(question)

    # Filtrer les termes non présents dans la question
    relevant_terms = [t for t in vocabulary.terms if t.lower() not in question_lower]

    if not relevant_terms:
        # Si tous les termes sont déjà dans la question, suggérer des clarifications
        if vocabulary.terms:
            term = vocabulary.terms[0]
            source_doc = vocabulary.term_sources.get(term, "documents trouvés")
            suggestions.append(ReformulationSuggestion(
                text=f"Pouvez-vous préciser votre question concernant {term} ?",
                type="clarification",
                reason="Besoin de précision sur le contexte",
                source_document=source_doc
            ))
        return suggestions

    patterns = QUESTION_PATTERNS.get(question_type, QUESTION_PATTERNS["generic"])["patterns"]

    for i, term in enumerate(relevant_terms[:3]):
        source_doc = vocabulary.term_sources.get(term, "documents trouvés")

        if i == 0:
            # Première suggestion: reformulation directe avec le terme le plus pertinent
            if question_type == "comment" and action:
                suggestion_text = f"Comment {action} {term} ?"
                reason = f"Reformulation avec le terme '{term}' des documents"
            elif question_type == "quoi":
                suggestion_text = f"Qu'est-ce que {term} et comment ça fonctionne ?"
                reason = f"Clarification du concept '{term}'"
            elif question_type == "pourquoi":
                suggestion_text = f"Pourquoi {term} est-il important ?"
                reason = f"Question sur l'importance de '{term}'"
            else:
                suggestion_text = f"Comment fonctionne {term} ?"
                reason = f"Question sur le fonctionnement de '{term}'"

            suggestions.append(ReformulationSuggestion(
                text=suggestion_text,
                type="vocabulary",
                reason=reason,
                source_document=source_doc
            ))

        elif i == 1:
            # Deuxième suggestion: question de définition/explication
            suggestion_text = f"Pouvez-vous expliquer {term} et son utilisation ?"
            suggestions.append(ReformulationSuggestion(
                text=suggestion_text,
                type="clarification",
                reason=f"Demande d'explication sur '{term}'",
                source_document=source_doc
            ))

        elif i == 2:
            # Troisième suggestion: question pratique
            suggestion_text = f"Quelles sont les étapes pour utiliser {term} ?"
            suggestions.append(ReformulationSuggestion(
                text=suggestion_text,
                type="expansion",
                reason=f"Question pratique sur '{term}'",
                source_document=source_doc
            ))

    logger.info(f"📝 Fallback: {len(suggestions)} suggestions générées (type={question_type}, action={action})")
    return suggestions[:3]


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
    "detect_intent",
    "INTENT_PATTERNS",
    "REFORMULATION_ENABLED",
    "REFORMULATION_HEURISTIC_THRESHOLD",
]
