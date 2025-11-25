"""
Glossaire de vocabulaire métier pour RAGFab.

Ce module fournit:
- Correspondances vocabulaire utilisateur → vocabulaire métier
- Patterns de détection de termes domaine
- Fonctions d'extraction et de suggestion de vocabulaire

Le glossaire peut être enrichi automatiquement depuis les documents
ou manuellement par les administrateurs.

Author: RAGFab Team
Date: 2025-01-25
"""

import re
import logging
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# ============================================================================
# Glossaire Métier Sillage
# ============================================================================

# Correspondances: expressions utilisateur → termes métier corrects
VOCABULARY_MAP: Dict[str, str] = {
    # --- Lien mère-enfant ---
    "rattacher la maman": "créer le lien mère-enfant",
    "rattacher maman": "créer le lien mère-enfant",
    "rattacher le bébé": "créer le lien mère-enfant",
    "rattacher bébé": "créer le lien mère-enfant",
    "lier maman bébé": "créer le lien mère-enfant",
    "lier la mère": "créer le lien mère-enfant",
    "maman et bébé": "lien mère-enfant",
    "lien mère bébé": "lien mère-enfant",
    "associer mère enfant": "créer le lien mère-enfant",
    "rattacher mère enfant": "créer le lien mère-enfant",
    "faire le lien maman": "créer le lien mère-enfant",

    # --- Terminologie générale ---
    "base de données": "BDD Sillage",
    "la base": "BDD Sillage",
    "en base": "en BDD",
    "le logiciel": "Sillage",
    "l'application": "Sillage",
    "le système": "Sillage",
    "l'outil": "Sillage",
    "le programme": "Sillage",

    # --- Patient ---
    "fiche patient": "dossier patient",
    "fiche du patient": "dossier patient",
    "le malade": "le patient",
    "la personne": "le patient",

    # --- Identifiants ---
    "numéro patient": "IPP (Identifiant Patient Permanent)",
    "numéro de séjour": "IEP (Identifiant Épisode Patient)",
    "identifiant patient": "IPP",
    "id patient": "IPP",
    "id séjour": "IEP",

    # --- Actions courantes ---
    "supprimer": "désactiver / supprimer",
    "effacer": "supprimer",
    "enlever": "supprimer / retirer",
    "rajouter": "ajouter / créer",
    "mettre": "définir / configurer",
    "changer": "modifier",

    # --- Maternité / Obstétrique ---
    "accouchement": "fiche accouchement",
    "naissance": "fiche naissance / accouchement",
    "maternité": "service maternité / obstétrique",
    "nouveau né": "nouveau-né / enfant",
    "nouveau-né": "nouveau-né",
    "bébé": "enfant / nouveau-né",
    "maman": "mère / patiente",

    # --- Erreurs courantes ---
    "ca marche pas": "dysfonctionnement / erreur",
    "ça marche pas": "dysfonctionnement / erreur",
    "ça bug": "erreur / dysfonctionnement",
    "c'est cassé": "dysfonctionnement",
    "problème": "incident / dysfonctionnement",
}

# Acronymes et leurs significations
ACRONYMS: Dict[str, str] = {
    "IPP": "Identifiant Patient Permanent",
    "IEP": "Identifiant Épisode Patient",
    "IPS": "Identifiant Passage Séjour",
    "BDD": "Base De Données",
    "BIS_LME": "Table du lien mère-enfant (schéma SIPSDM)",
    "SIPSDM": "Schéma de la base Sillage pour données médicales",
    "UF": "Unité Fonctionnelle",
    "UM": "Unité Médicale",
    "FS": "Fiche Solution",
    "KB": "Knowledge Base / Base de connaissances",
}

# Termes métier importants (pour détection)
DOMAIN_TERMS: Set[str] = {
    # Sillage
    "sillage", "sipsdm", "bis_lme", "visuDossier",
    # Identifiants
    "ipp", "iep", "ips", "ippbis", "iepbis", "ipsbis",
    # Tables/Schémas
    "lme_c_ippbis", "lme_c_iepbis", "lme_c_ipsbis",
    # Concepts métier
    "lien mère-enfant", "lien mere-enfant", "dossier patient",
    "fiche solution", "fiche accouchement",
    # Services
    "maternité", "obstétrique", "néonatologie",
    # Actions techniques
    "insert into", "select from", "sql.sh",
}


# ============================================================================
# Catégories de termes
# ============================================================================

@dataclass
class TermCategory:
    """Catégorie de termes métier."""
    name: str
    description: str
    terms: List[str]
    patterns: List[str]  # Regex patterns


TERM_CATEGORIES: Dict[str, TermCategory] = {
    "identifiants": TermCategory(
        name="Identifiants",
        description="Identifiants patients et séjours",
        terms=["IPP", "IEP", "IPS", "IPPBIS", "IEPBIS"],
        patterns=[
            r"\b(ipp|iep|ips)\b",
            r"\b(ippbis|iepbis|ipsbis)\b",
            r"\bLME_C_[A-Z]+\b",
        ]
    ),
    "tables_db": TermCategory(
        name="Tables BDD",
        description="Tables et schémas de la base Sillage",
        terms=["BIS_LME", "SIPSDM", "PAT", "DAD", "PAS"],
        patterns=[
            r"\bBIS_[A-Z]+\b",
            r"\bSIPSDM\b",
            r"\bschema\s+sipsdm\b",
        ]
    ),
    "lien_mere_enfant": TermCategory(
        name="Lien Mère-Enfant",
        description="Gestion du lien entre dossiers mère et enfant",
        terms=["lien mère-enfant", "BIS_LME", "mère", "enfant", "naissance"],
        patterns=[
            r"\blien\s+m[eè]re[-\s]?enfant\b",
            r"\bm[eè]re[-\s]enfant\b",
            r"\bBIS_LME\b",
        ]
    ),
    "maternite": TermCategory(
        name="Maternité/Obstétrique",
        description="Services et processus liés à la maternité",
        terms=["maternité", "obstétrique", "accouchement", "naissance", "nouveau-né"],
        patterns=[
            r"\b(maternit[ée]|obst[ée]trique)\b",
            r"\baccouchement\b",
            r"\bnouveau[-\s]?n[ée]\b",
        ]
    ),
    "sillage": TermCategory(
        name="Sillage",
        description="Logiciel hospitalier et ses composants",
        terms=["Sillage", "visuDossier", "console exploitation"],
        patterns=[
            r"\bsillage\b",
            r"\bvisuDossier\b",
            r"\bconsole\s+d'?exploitation\b",
        ]
    ),
}


# ============================================================================
# Fonctions de détection et suggestion
# ============================================================================

def detect_domain_terms(text: str) -> List[str]:
    """
    Détecte les termes métier présents dans un texte.

    Args:
        text: Texte à analyser

    Returns:
        Liste des termes métier détectés
    """
    text_lower = text.lower()
    detected = []

    # Vérifier termes directs
    for term in DOMAIN_TERMS:
        if term.lower() in text_lower:
            detected.append(term)

    # Vérifier patterns par catégorie
    for category in TERM_CATEGORIES.values():
        for pattern in category.patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            detected.extend(matches)

    # Dédupliquer en préservant l'ordre
    seen = set()
    unique = []
    for term in detected:
        term_lower = term.lower()
        if term_lower not in seen:
            seen.add(term_lower)
            unique.append(term)

    return unique


def suggest_vocabulary_corrections(text: str) -> List[Tuple[str, str]]:
    """
    Suggère des corrections de vocabulaire.

    Args:
        text: Texte à analyser

    Returns:
        Liste de tuples (terme_utilisateur, terme_suggéré)
    """
    text_lower = text.lower()
    suggestions = []

    for user_term, domain_term in VOCABULARY_MAP.items():
        if user_term in text_lower:
            suggestions.append((user_term, domain_term))

    return suggestions


def apply_vocabulary_corrections(text: str) -> Tuple[str, List[Tuple[str, str]]]:
    """
    Applique les corrections de vocabulaire à un texte.

    Args:
        text: Texte original

    Returns:
        (texte_corrigé, liste_des_corrections_appliquées)
    """
    corrections = suggest_vocabulary_corrections(text)
    corrected_text = text

    for user_term, domain_term in corrections:
        # Remplacer de façon case-insensitive
        pattern = re.compile(re.escape(user_term), re.IGNORECASE)
        corrected_text = pattern.sub(domain_term, corrected_text)

    return (corrected_text, corrections)


def get_term_explanation(term: str) -> Optional[str]:
    """
    Retourne l'explication d'un terme ou acronyme.

    Args:
        term: Terme à expliquer

    Returns:
        Explication ou None si non trouvé
    """
    term_upper = term.upper()
    if term_upper in ACRONYMS:
        return ACRONYMS[term_upper]

    # Chercher dans les catégories
    term_lower = term.lower()
    for category in TERM_CATEGORIES.values():
        if term_lower in [t.lower() for t in category.terms]:
            return f"{category.name}: {category.description}"

    return None


def get_related_terms(term: str) -> List[str]:
    """
    Retourne les termes liés à un terme donné.

    Args:
        term: Terme de référence

    Returns:
        Liste des termes liés
    """
    term_lower = term.lower()
    related = []

    # Trouver la catégorie du terme
    for category in TERM_CATEGORIES.values():
        if term_lower in [t.lower() for t in category.terms]:
            # Retourner tous les autres termes de la catégorie
            related = [t for t in category.terms if t.lower() != term_lower]
            break

    return related


def compute_vocabulary_match_score(question: str) -> float:
    """
    Calcule un score de correspondance vocabulaire métier.

    Args:
        question: Question à analyser

    Returns:
        Score entre 0.0 (aucun terme métier) et 1.0 (vocabulaire correct)
    """
    # Détecter termes métier présents
    domain_terms = detect_domain_terms(question)

    # Détecter corrections suggérées
    corrections = suggest_vocabulary_corrections(question)

    # Score de base
    if domain_terms and not corrections:
        # Utilise vocabulaire métier correct
        return 1.0
    elif domain_terms and corrections:
        # Mix de vocabulaire correct et incorrect
        return 0.7
    elif corrections:
        # Utilise uniquement vocabulaire utilisateur (incorret)
        return 0.4
    else:
        # Pas de vocabulaire métier détecté
        return 0.5


# ============================================================================
# Extraction depuis documents (Phase 2)
# ============================================================================

async def extract_vocabulary_from_documents(db_pool) -> Dict[str, int]:
    """
    Extrait le vocabulaire métier depuis les documents ingérés.

    Cette fonction analyse les chunks de documents pour identifier
    les termes fréquemment utilisés qui pourraient enrichir le glossaire.

    Args:
        db_pool: Pool de connexions DB

    Returns:
        Dictionnaire {terme: fréquence}
    """
    # TODO: Implémenter extraction automatique
    # 1. Récupérer les chunks de documents
    # 2. Tokeniser et filtrer stopwords
    # 3. Identifier termes fréquents (TF-IDF ou similaire)
    # 4. Filtrer par seuil de fréquence
    # 5. Retourner termes candidats

    logger.info("📚 Extraction vocabulaire documents - À implémenter")
    return {}


async def suggest_glossary_additions(db_pool) -> List[Dict]:
    """
    Suggère des ajouts au glossaire basés sur l'analyse des documents.

    Returns:
        Liste de suggestions {term, frequency, context_examples}
    """
    # TODO: Implémenter suggestion automatique
    logger.info("💡 Suggestion glossaire - À implémenter")
    return []


# ============================================================================
# Export
# ============================================================================

__all__ = [
    "VOCABULARY_MAP",
    "ACRONYMS",
    "DOMAIN_TERMS",
    "TERM_CATEGORIES",
    "detect_domain_terms",
    "suggest_vocabulary_corrections",
    "apply_vocabulary_corrections",
    "get_term_explanation",
    "get_related_terms",
    "compute_vocabulary_match_score",
    "extract_vocabulary_from_documents",
    "suggest_glossary_additions",
]
