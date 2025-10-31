#!/usr/bin/env python3
"""
Script de test pour Hybrid Search (BM25 + Vector)
Valide le fonctionnement avec des requêtes en français

Tests couverts:
1. Acronymes (devrait privilégier BM25 avec alpha=0.3)
2. Noms propres (devrait privilégier BM25 avec alpha=0.3)
3. Questions conceptuelles (devrait privilégier sémantique avec alpha=0.7)
4. Requêtes courtes (devrait avoir léger biais BM25 avec alpha=0.4)
5. Requêtes générales (équilibré avec alpha=0.5)
"""
import os
import sys
import asyncio
import asyncpg

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from web_api.app.hybrid_search import preprocess_query_for_tsquery, adaptive_alpha


# Tests de préprocessing
def test_preprocessing():
    print("\n" + "="*80)
    print("TEST 1: Préprocessing des requêtes")
    print("="*80)

    test_cases = [
        {
            "query": "Quelle est la politique de télétravail ?",
            "expected_keywords": ["politique", "télétravail"],
            "description": "Question avec stopwords"
        },
        {
            "query": "procédure RTT congés payés",
            "expected_keywords": ["procédure", "RTT", "congés", "payés"],
            "description": "Mots-clés avec acronyme"
        },
        {
            "query": "l'entreprise et les employés",
            "expected_keywords": ["entreprise", "employés"],
            "description": "Stopwords avec articles"
        },
        {
            "query": "Comment fonctionne PeopleDoc ?",
            "expected_keywords": ["fonctionne", "PeopleDoc"],
            "description": "Question avec nom propre"
        }
    ]

    for i, test in enumerate(test_cases, 1):
        query = test["query"]
        processed = preprocess_query_for_tsquery(query)

        print(f"\n{i}. {test['description']}")
        print(f"   Requête: \"{query}\"")
        print(f"   Traité: \"{processed}\"")
        print(f"   Attendu: {' & '.join(test['expected_keywords'])}")

        # Vérifier que tous les mots-clés attendus sont présents
        for keyword in test["expected_keywords"]:
            if keyword.lower() in processed.lower():
                print(f"   ✅ '{keyword}' présent")
            else:
                print(f"   ❌ '{keyword}' MANQUANT")


# Tests d'alpha adaptatif
def test_adaptive_alpha():
    print("\n" + "="*80)
    print("TEST 2: Alpha adaptatif")
    print("="*80)

    test_cases = [
        {
            "query": "procédure RTT",
            "expected_alpha": 0.3,
            "reason": "Acronyme RTT → biais keyword",
            "category": "Acronyme"
        },
        {
            "query": "logiciel PeopleDoc",
            "expected_alpha": 0.3,
            "reason": "Nom propre PeopleDoc → biais keyword",
            "category": "Nom propre"
        },
        {
            "query": "pourquoi favoriser le télétravail ?",
            "expected_alpha": 0.7,
            "reason": "Question conceptuelle 'pourquoi' → biais sémantique",
            "category": "Conceptuel"
        },
        {
            "query": "comment activer bluetooth",
            "expected_alpha": 0.7,
            "reason": "Question conceptuelle 'comment' → biais sémantique",
            "category": "Conceptuel"
        },
        {
            "query": "télétravail",
            "expected_alpha": 0.4,
            "reason": "Question courte (1 mot) → léger biais keyword",
            "category": "Court"
        },
        {
            "query": "politique de télétravail de l'entreprise",
            "expected_alpha": 0.5,
            "reason": "Question générale → équilibré",
            "category": "Général"
        }
    ]

    for i, test in enumerate(test_cases, 1):
        query = test["query"]
        calculated_alpha = adaptive_alpha(query)

        print(f"\n{i}. {test['category']}: \"{query}\"")
        print(f"   Alpha calculé: {calculated_alpha}")
        print(f"   Alpha attendu: {test['expected_alpha']}")
        print(f"   Raison: {test['reason']}")

        if calculated_alpha == test['expected_alpha']:
            print(f"   ✅ CORRECT")
        else:
            print(f"   ❌ ERREUR (écart: {abs(calculated_alpha - test['expected_alpha'])})")


# Test de connexion PostgreSQL
async def test_database_connection():
    print("\n" + "="*80)
    print("TEST 3: Connexion PostgreSQL et migration")
    print("="*80)

    try:
        # Récupérer DATABASE_URL depuis .env ou utiliser défaut
        database_url = os.getenv(
            "DATABASE_URL",
            "postgresql://raguser:ragpass@localhost:5432/ragdb"
        )

        conn = await asyncpg.connect(database_url)

        print(f"\n✅ Connexion PostgreSQL établie")

        # Vérifier que la colonne content_tsv existe
        column_check = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'chunks'
                AND column_name = 'content_tsv'
            );
        """)

        if column_check:
            print("✅ Colonne 'content_tsv' existe")
        else:
            print("❌ Colonne 'content_tsv' MANQUANTE")
            print("   → Appliquer migration: docker-compose exec postgres psql -U raguser -d ragdb -f /docker-entrypoint-initdb.d/10_hybrid_search.sql")
            await conn.close()
            return False

        # Vérifier que l'index GIN existe
        index_check = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE tablename = 'chunks'
                AND indexname = 'idx_chunks_content_tsv'
            );
        """)

        if index_check:
            print("✅ Index GIN 'idx_chunks_content_tsv' existe")
        else:
            print("❌ Index GIN MANQUANT")
            await conn.close()
            return False

        # Vérifier que la fonction match_chunks_hybrid existe
        function_check = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM pg_proc
                WHERE proname = 'match_chunks_hybrid'
            );
        """)

        if function_check:
            print("✅ Fonction 'match_chunks_hybrid' existe")
        else:
            print("❌ Fonction 'match_chunks_hybrid' MANQUANTE")
            await conn.close()
            return False

        # Vérifier combien de chunks ont du contenu tsvector
        tsvector_count = await conn.fetchval("""
            SELECT COUNT(*) FROM chunks WHERE content_tsv IS NOT NULL;
        """)

        total_count = await conn.fetchval("""
            SELECT COUNT(*) FROM chunks;
        """)

        print(f"\n📊 Statistiques:")
        print(f"   Total chunks: {total_count}")
        print(f"   Chunks avec tsvector: {tsvector_count}")

        if tsvector_count == 0 and total_count > 0:
            print(f"   ⚠️ Aucun chunk n'a de tsvector, exécuter:")
            print(f"      UPDATE chunks SET content_tsv = to_tsvector('french', content);")
        elif tsvector_count < total_count:
            print(f"   ⚠️ {total_count - tsvector_count} chunks sans tsvector")
        else:
            print(f"   ✅ Tous les chunks ont un tsvector")

        await conn.close()
        return True

    except Exception as e:
        print(f"\n❌ Erreur connexion: {e}")
        print(f"\nVérifier que PostgreSQL est accessible:")
        print(f"  docker-compose ps postgres")
        return False


# Test de recherche hybride sur données réelles
async def test_hybrid_search_query():
    print("\n" + "="*80)
    print("TEST 4: Recherche hybride sur données réelles")
    print("="*80)

    try:
        database_url = os.getenv(
            "DATABASE_URL",
            "postgresql://raguser:ragpass@localhost:5432/ragdb"
        )

        conn = await asyncpg.connect(database_url)

        # Vérifier qu'il y a des documents
        doc_count = await conn.fetchval("SELECT COUNT(*) FROM documents;")

        if doc_count == 0:
            print("\n⚠️ Aucun document dans la base")
            print("   Uploader des documents via /admin avant de tester la recherche")
            await conn.close()
            return

        print(f"\n📚 {doc_count} document(s) disponible(s)")

        # Exemple de requête test (nécessite un embedding, donc on teste juste la fonction SQL)
        test_query = "télétravail"
        processed_query = preprocess_query_for_tsquery(test_query)

        print(f"\n🔍 Test de la recherche keyword seule:")
        print(f"   Requête: \"{test_query}\"")
        print(f"   Traité: \"{processed_query}\"")

        # Recherche keyword uniquement
        keyword_results = await conn.fetch("""
            SELECT
                c.id,
                LEFT(c.content, 150) as preview,
                ts_rank_cd(c.content_tsv, to_tsquery('french', $1), 32) AS bm25_score
            FROM chunks c
            WHERE c.content_tsv @@ to_tsquery('french', $1)
            ORDER BY bm25_score DESC
            LIMIT 5;
        """, processed_query)

        if keyword_results:
            print(f"\n✅ Trouvé {len(keyword_results)} résultat(s) BM25:")
            for i, result in enumerate(keyword_results, 1):
                print(f"\n   {i}. Score BM25: {result['bm25_score']:.4f}")
                print(f"      Preview: {result['preview']}...")
        else:
            print(f"\n⚠️ Aucun résultat BM25 pour '{test_query}'")
            print(f"   Ceci est normal si le terme n'existe pas dans les documents")

        await conn.close()

    except Exception as e:
        print(f"\n❌ Erreur test recherche: {e}")


# Main
async def main():
    print("\n" + "="*80)
    print("VALIDATION HYBRID SEARCH - RAGFab")
    print("="*80)

    # Tests unitaires (pas de DB requise)
    test_preprocessing()
    test_adaptive_alpha()

    # Tests DB (requiert PostgreSQL)
    db_ok = await test_database_connection()

    if db_ok:
        await test_hybrid_search_query()

    print("\n" + "="*80)
    print("RÉSUMÉ DES TESTS")
    print("="*80)
    print("""
Si tous les tests sont verts ✅:
1. Activer hybrid search: HYBRID_SEARCH_ENABLED=true dans .env
2. Rebuild: docker-compose up -d --build ragfab-api
3. Tester dans l'interface avec des requêtes contenant:
   - Acronymes: "procédure RTT"
   - Noms propres: "logiciel PeopleDoc"
   - Questions: "pourquoi favoriser le télétravail"

Si des tests sont rouges ❌:
1. Appliquer migration SQL:
   docker-compose exec postgres psql -U raguser -d ragdb \\
     -f /docker-entrypoint-initdb.d/10_hybrid_search.sql

2. Vérifier tsvector:
   docker-compose exec postgres psql -U raguser -d ragdb \\
     -c "UPDATE chunks SET content_tsv = to_tsvector('french', content);"

3. Relancer ce script: python claudedocs/test_hybrid_search.py
""")


if __name__ == "__main__":
    asyncio.run(main())
