"""
Module pour Hybrid Search (BM25 + Vector) avec support français
Combine recherche sémantique (embeddings) et recherche par mots-clés (full-text)
"""
import re
import logging
from typing import List, Dict, Optional
from uuid import UUID

from . import database

logger = logging.getLogger(__name__)

# Stopwords français pour preprocessing des requêtes
FRENCH_STOPWORDS = {
    "le", "la", "les", "l", "un", "une", "des",
    "de", "du", "d", "des",
    "à", "au", "aux",
    "et", "ou", "mais", "donc", "or", "ni", "car",
    "ce", "cet", "cette", "ces",
    "mon", "ton", "son", "ma", "ta", "sa", "mes", "tes", "ses",
    "notre", "votre", "leur", "nos", "vos", "leurs",
    "je", "tu", "il", "elle", "on", "nous", "vous", "ils", "elles",
    "me", "te", "se", "lui",
    "qui", "que", "quoi", "dont", "où",
    "dans", "par", "pour", "sur", "avec", "sans", "sous",
    "être", "avoir", "faire", "dire", "aller", "voir", "pouvoir", "vouloir"
}


def preprocess_query_for_tsquery(query: str) -> str:
    """
    Convertit une requête utilisateur en format PostgreSQL tsquery pour recherche full-text.

    Transformations appliquées:
    - Suppression des stopwords français (le, la, de, etc.)
    - Nettoyage caractères spéciaux (préserve - et ')
    - Jointure avec '&' (AND operator)
    - Gestion des acronymes (préservation)

    Exemples:
        "Quelle est la politique de télétravail ?"
        → "politique & télétravail"

        "procédure RTT congés payés"
        → "procédure & RTT & congés & payés"

        "l'entreprise et les employés"
        → "entreprise & employés"

    Args:
        query: Question utilisateur en français

    Returns:
        Requête formatée pour to_tsquery('french', ...)
    """
    # Convertir en minuscules
    query_lower = query.lower()

    # Remplacer apostrophes typographiques par apostrophe standard
    query_lower = query_lower.replace("'", "'").replace("'", "'")

    # Nettoyer caractères spéciaux (sauf tirets et apostrophes)
    query_lower = re.sub(r"[^\w\s'-]", " ", query_lower)

    # Tokeniser
    tokens = query_lower.split()

    # Filtrer stopwords ET tokens vides
    filtered = []
    for token in tokens:
        # Nettoyer le token
        token = token.strip("'-")

        # Garder si:
        # 1. Pas un stopword
        # 2. OU est un acronyme (2+ lettres majuscules consécutives dans original)
        # 3. ET token non vide
        is_acronym = bool(re.search(r'\b[A-Z]{2,}\b', token.upper()))

        if token and (token not in FRENCH_STOPWORDS or is_acronym):
            filtered.append(token)

    # Si tous les tokens sont filtrés, retourner au moins 1 token
    if not filtered and tokens:
        # Prendre le token le plus long (probablement le plus significatif)
        filtered = [max(tokens, key=len).strip("'-")]

    # Joindre avec '&' (AND operator PostgreSQL)
    result = " & ".join(filtered) if filtered else ""

    # Log pour debugging
    if result != query_lower:
        logger.debug(f"Query preprocessing: '{query}' → '{result}'")

    return result


def adaptive_alpha(query: str) -> float:
    """
    Ajuste dynamiquement le poids alpha selon le type de question.

    Alpha = 0.0 : 100% keyword search (BM25)
    Alpha = 0.5 : Équilibré (50% vector, 50% keyword)
    Alpha = 1.0 : 100% vector search (semantic)

    Stratégies:
    - Acronymes (RTT, CDI) → alpha=0.3 (privilégie keyword)
    - Noms propres (PeopleDoc) → alpha=0.3 (privilégie keyword)
    - Questions conceptuelles (pourquoi, comment) → alpha=0.7 (privilégie sémantique)
    - Par défaut → alpha=0.5 (équilibré)

    Args:
        query: Question utilisateur

    Returns:
        Alpha optimal (0.0 à 1.0)
    """
    query_lower = query.lower()

    # Détecter acronymes (2+ lettres majuscules consécutives)
    if re.search(r'\b[A-Z]{2,}\b', query):
        logger.debug(f"Acronyme détecté, alpha=0.3 (keyword bias)")
        return 0.3

    # Détecter noms propres (mots avec majuscule après le premier mot)
    words = query.split()
    if len(words) > 1:
        proper_nouns = [w for w in words[1:] if w and w[0].isupper()]
        if proper_nouns:
            logger.debug(f"Nom propre détecté ({proper_nouns}), alpha=0.3 (keyword bias)")
            return 0.3

    # Questions conceptuelles
    conceptual_keywords = [
        "pourquoi", "comment", "expliquer", "signifie", "définition",
        "différence", "comparer", "avantage", "inconvénient", "principe"
    ]
    if any(keyword in query_lower for keyword in conceptual_keywords):
        logger.debug(f"Question conceptuelle détectée, alpha=0.7 (semantic bias)")
        return 0.7

    # Questions très courtes (<5 mots) souvent recherchent terme exact
    if len(words) <= 4:
        logger.debug(f"Question courte ({len(words)} mots), alpha=0.4 (léger keyword bias)")
        return 0.4

    # Par défaut: équilibré
    logger.debug(f"Alpha par défaut=0.5 (équilibré)")
    return 0.5


async def hybrid_search(
    query: str,
    query_embedding: List[float],
    k: int = 5,
    alpha: Optional[float] = None,
    use_adaptive_alpha: bool = True,
    use_hierarchical: bool = False
) -> List[Dict]:
    """
    Recherche hybride combinant similarité vectorielle (E5-Large) et mots-clés (BM25).

    Utilise la fonction PostgreSQL match_chunks_hybrid() qui implémente:
    - Vector search via pgvector (cosine similarity)
    - Keyword search via tsvector + GIN index (BM25-like)
    - RRF (Reciprocal Rank Fusion) pour combiner les résultats

    Args:
        query: Question utilisateur en français
        query_embedding: Embedding de la question (vecteur 1024 dimensions)
        k: Nombre de résultats à retourner (défaut: 5)
        alpha: Poids entre vector (1.0) et keyword (0.0). Si None, utilise adaptive
        use_adaptive_alpha: Si True et alpha=None, calcule alpha optimal automatiquement
        use_hierarchical: Si True, cherche dans chunks enfants et retourne parents

    Returns:
        Liste de chunks avec scores (similarity, bm25_score, combined_score) et métadonnées complètes

    Raises:
        Exception: Si erreur PostgreSQL ou embedding invalide
    """
    # Déterminer alpha optimal
    if alpha is None:
        if use_adaptive_alpha:
            alpha = adaptive_alpha(query)
        else:
            alpha = 0.5  # Défaut équilibré

    # Valider alpha range
    alpha = max(0.0, min(1.0, alpha))

    # Préprocesser query pour full-text search
    processed_query = preprocess_query_for_tsquery(query)

    # Si query vide après preprocessing, fallback sur query originale
    if not processed_query:
        processed_query = query.lower()
        logger.warning(f"⚠️ Query vide après preprocessing, fallback sur query originale")

    logger.info(f"🔀 Hybrid search: query='{query}' → tsquery='{processed_query}', alpha={alpha:.2f}, k={k}")

    # Convertir embedding liste Python en chaîne PostgreSQL vector
    embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"

    try:
        async with database.db_pool.acquire() as conn:
            # Appeler fonction PostgreSQL match_chunks_hybrid
            results = await conn.fetch("""
                SELECT
                    id,
                    content,
                    similarity,
                    bm25_score,
                    combined_score,
                    metadata,
                    document_id,
                    chunk_index,
                    prev_chunk_id,
                    next_chunk_id,
                    section_hierarchy,
                    heading_context,
                    document_position,
                    chunk_level,
                    parent_chunk_id
                FROM match_chunks_hybrid($1::vector, $2, $3, $4, $5)
            """,
            embedding_str,     # $1: query_embedding vector(1024) as string
            processed_query,   # $2: query_text preprocessed
            k,                 # $3: match_count
            alpha,             # $4: alpha weight
            use_hierarchical   # $5: use_hierarchical boolean
            )

        # Formater résultats
        formatted_results = []
        for row in results:
            formatted_results.append({
                "chunk_id": str(row["id"]),
                "content": row["content"],
                "scores": {
                    "vector_similarity": float(row["similarity"]),
                    "bm25_score": float(row["bm25_score"]),
                    "combined_score": float(row["combined_score"]),
                    "alpha_used": alpha
                },
                "metadata": row["metadata"] or {},
                "document_id": str(row["document_id"]),
                "chunk_index": row["chunk_index"],
                "adjacent": {
                    "prev_chunk_id": str(row["prev_chunk_id"]) if row["prev_chunk_id"] else None,
                    "next_chunk_id": str(row["next_chunk_id"]) if row["next_chunk_id"] else None,
                },
                "structure": {
                    "section_hierarchy": row["section_hierarchy"] or [],
                    "heading_context": row["heading_context"],
                    "document_position": float(row["document_position"]) if row["document_position"] else None,
                },
                "parent_child": {
                    "chunk_level": row["chunk_level"],
                    "parent_chunk_id": str(row["parent_chunk_id"]) if row["parent_chunk_id"] else None,
                }
            })

        # Log statistiques
        if formatted_results:
            avg_similarity = sum(r["scores"]["vector_similarity"] for r in formatted_results) / len(formatted_results)
            avg_bm25 = sum(r["scores"]["bm25_score"] for r in formatted_results) / len(formatted_results)
            avg_combined = sum(r["scores"]["combined_score"] for r in formatted_results) / len(formatted_results)

            logger.info(
                f"✅ Hybrid search: {len(formatted_results)} résultats | "
                f"Scores moyens - Vector: {avg_similarity:.3f}, BM25: {avg_bm25:.3f}, Combined: {avg_combined:.4f}"
            )
        else:
            logger.warning(f"⚠️ Hybrid search: 0 résultats pour query '{query}'")

        return formatted_results

    except Exception as e:
        logger.error(f"❌ Erreur hybrid search: {e}", exc_info=True)
        raise


async def smart_hybrid_search(
    query: str,
    query_embedding: List[float],
    k: int = 5,
    alpha: Optional[float] = None
) -> List[Dict]:
    """
    Recherche hybride intelligente qui gère automatiquement parent-child chunks.

    Utilise match_chunks_smart_hybrid() qui:
    - Détecte automatiquement si parent-child chunks existent
    - Si oui: cherche dans children, retourne parents
    - Si non: recherche hybride classique

    Args:
        query: Question utilisateur
        query_embedding: Embedding de la question
        k: Nombre de résultats
        alpha: Poids vector/keyword (None = adaptive)

    Returns:
        Résultats hybrid search avec meilleur contexte (parents si disponibles)
    """
    # Déterminer alpha
    if alpha is None:
        alpha = adaptive_alpha(query)

    alpha = max(0.0, min(1.0, alpha))
    processed_query = preprocess_query_for_tsquery(query)

    if not processed_query:
        processed_query = query.lower()

    logger.info(f"🧠 Smart hybrid search: query='{query}', alpha={alpha:.2f}")

    # Convertir embedding liste Python en chaîne PostgreSQL vector
    embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"

    try:
        async with database.db_pool.acquire() as conn:
            # Appeler directement la fonction sans SELECT (évite réordonnancement)
            results = await conn.fetch("""
                SELECT * FROM match_chunks_smart_hybrid($1::vector, $2, $3, $4)
            """,
            embedding_str,
            processed_query,
            k,
            alpha
            )

        # Formater identique à hybrid_search()
        formatted_results = []
        for row in results:
            formatted_results.append({
                "chunk_id": str(row["id"]),
                "content": row["content"],
                "scores": {
                    "vector_similarity": float(row["similarity"]),
                    "bm25_score": float(row["bm25_score"]),
                    "combined_score": float(row["combined_score"]),
                    "alpha_used": alpha
                },
                "metadata": row["metadata"] or {},
                "document_id": str(row["document_id"]),
                "chunk_index": row["chunk_index"],
                "adjacent": {
                    "prev_chunk_id": str(row["prev_chunk_id"]) if row["prev_chunk_id"] else None,
                    "next_chunk_id": str(row["next_chunk_id"]) if row["next_chunk_id"] else None,
                },
                "structure": {
                    "section_hierarchy": row["section_hierarchy"] or [],
                    "heading_context": row["heading_context"],
                    "document_position": float(row["document_position"]) if row["document_position"] else None,
                },
                "parent_child": {
                    "chunk_level": row["chunk_level"],
                    "parent_chunk_id": str(row["parent_chunk_id"]) if row["parent_chunk_id"] else None,
                }
            })

        logger.info(f"✅ Smart hybrid: {len(formatted_results)} résultats")
        return formatted_results

    except Exception as e:
        logger.error(f"❌ Erreur smart hybrid search: {e}", exc_info=True)
        raise
