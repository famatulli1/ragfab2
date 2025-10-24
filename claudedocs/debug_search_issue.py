#!/usr/bin/env python3
"""
Script de diagnostic pour analyser pourquoi la recherche RAG ne trouve pas les chunks.
Test direct des embeddings et de la recherche vectorielle.
"""

import os
import sys
import asyncio
import httpx
from typing import List, Dict
import psycopg2
from psycopg2.extras import RealDictCursor

# Configuration
EMBEDDINGS_API_URL = os.getenv("EMBEDDINGS_API_URL", "http://localhost:8001")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://raguser:changeme_secure_password@localhost:5432/ragdb")

async def get_embedding(text: str) -> List[float]:
    """Récupère l'embedding d'un texte via l'API d'embeddings."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{EMBEDDINGS_API_URL}/embed",
            json={"texts": [text]}
        )
        response.raise_for_status()
        result = response.json()
        return result["embeddings"][0]

def vector_search_direct(query_embedding: List[float], top_k: int = 10, conn=None):
    """Effectue une recherche vectorielle directe en base de données."""
    close_conn = False
    if conn is None:
        conn = psycopg2.connect(DATABASE_URL)
        close_conn = True

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Requête de similarité vectorielle (cosine distance)
            query = """
                SELECT
                    c.id,
                    c.content,
                    c.metadata,
                    d.title,
                    d.source,
                    (c.embedding <=> %s::vector) as distance,
                    1 - (c.embedding <=> %s::vector) as similarity
                FROM chunks c
                JOIN documents d ON c.document_id = d.id
                ORDER BY c.embedding <=> %s::vector
                LIMIT %s;
            """

            # PostgreSQL nécessite le vecteur comme string
            embedding_str = f"[{','.join(map(str, query_embedding))}]"

            cur.execute(query, (embedding_str, embedding_str, embedding_str, top_k))
            results = cur.fetchall()

            return results
    finally:
        if close_conn:
            conn.close()

async def test_query(query: str):
    """Teste une requête complète avec affichage détaillé des résultats."""
    print(f"\n{'='*80}")
    print(f"🔍 TEST DE RECHERCHE")
    print(f"{'='*80}")
    print(f"Query: {query}")
    print(f"{'='*80}\n")

    # Étape 1: Générer l'embedding de la query
    print("📊 Étape 1: Génération de l'embedding...")
    try:
        query_embedding = await get_embedding(query)
        print(f"✅ Embedding généré (dimension: {len(query_embedding)})")
        print(f"   Premiers éléments: {query_embedding[:5]}")
    except Exception as e:
        print(f"❌ Erreur lors de la génération de l'embedding: {e}")
        return

    # Étape 2: Recherche vectorielle directe
    print("\n🔎 Étape 2: Recherche vectorielle en base de données...")
    try:
        results = vector_search_direct(query_embedding, top_k=10)
        print(f"✅ {len(results)} résultats trouvés\n")

        if not results:
            print("⚠️  AUCUN RÉSULTAT TROUVÉ")
            print("Causes possibles:")
            print("  1. Base de données vide (pas de chunks)")
            print("  2. Problème avec l'index vectoriel")
            print("  3. Dimension d'embedding incorrecte")
            return

        # Afficher les résultats avec détails
        for i, result in enumerate(results, 1):
            print(f"{'─'*80}")
            print(f"Résultat #{i}")
            print(f"{'─'*80}")
            print(f"🎯 Score de similarité: {result['similarity']:.4f} (distance: {result['distance']:.4f})")
            print(f"📄 Document: {result['title']}")
            print(f"📂 Source: {result['source']}")
            print(f"🆔 Chunk ID: {result['id']}")

            # Afficher le contenu (tronqué)
            content = result['content']
            if len(content) > 300:
                print(f"📝 Contenu (tronqué):\n{content[:300]}...")
            else:
                print(f"📝 Contenu:\n{content}")

            # Afficher les métadonnées si présentes
            if result.get('metadata'):
                print(f"🏷️  Métadonnées: {result['metadata']}")
            print()

        # Analyse des scores
        print(f"\n{'='*80}")
        print("📈 ANALYSE DES SCORES")
        print(f"{'='*80}")
        best_score = results[0]['similarity']
        worst_score = results[-1]['similarity']
        avg_score = sum(r['similarity'] for r in results) / len(results)

        print(f"✨ Meilleur score: {best_score:.4f}")
        print(f"📉 Score le plus bas: {worst_score:.4f}")
        print(f"📊 Score moyen: {avg_score:.4f}")

        if best_score < 0.5:
            print("\n⚠️  ALERTE: Tous les scores sont < 0.5")
            print("Cela suggère que la recherche vectorielle ne trouve pas de chunks pertinents.")
            print("Causes possibles:")
            print("  1. Le modèle d'embeddings ne fonctionne pas bien pour ce type de contenu")
            print("  2. Les chunks ne contiennent pas d'information pertinente pour la query")
            print("  3. La question est mal formulée ou trop vague")
        elif best_score > 0.7:
            print(f"\n✅ EXCELLENT: Le chunk le plus pertinent a un score > 0.7")
            print(f"   Le système devrait retourner ce chunk au LLM.")
        else:
            print(f"\n⚠️  MOYEN: Scores entre 0.5 et 0.7")
            print(f"   Les résultats sont moyennement pertinents.")

    except Exception as e:
        print(f"❌ Erreur lors de la recherche: {e}")
        import traceback
        traceback.print_exc()

async def check_database_status():
    """Vérifie l'état de la base de données."""
    print(f"\n{'='*80}")
    print("🗄️  VÉRIFICATION DE LA BASE DE DONNÉES")
    print(f"{'='*80}\n")

    try:
        conn = psycopg2.connect(DATABASE_URL)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Nombre total de documents
            cur.execute("SELECT COUNT(*) as count FROM documents;")
            doc_count = cur.fetchone()['count']
            print(f"📚 Documents: {doc_count}")

            # Nombre total de chunks
            cur.execute("SELECT COUNT(*) as count FROM chunks;")
            chunk_count = cur.fetchone()['count']
            print(f"📄 Chunks: {chunk_count}")

            # Vérifier les dimensions d'embeddings
            cur.execute("SELECT array_length(embedding, 1) as dim FROM chunks LIMIT 1;")
            result = cur.fetchone()
            if result:
                dim = result['dim']
                print(f"🔢 Dimension des embeddings: {dim}")
            else:
                print("⚠️  Aucun chunk avec embedding trouvé")

            # Lister les documents disponibles
            if doc_count > 0:
                print("\n📋 Documents disponibles:")
                cur.execute("SELECT id, title, source, created_at FROM documents ORDER BY created_at DESC LIMIT 10;")
                docs = cur.fetchall()
                for doc in docs:
                    print(f"  - {doc['title']} (source: {doc['source']}, créé: {doc['created_at']})")

            # Vérifier l'index vectoriel
            cur.execute("""
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE tablename = 'chunks' AND indexdef LIKE '%embedding%';
            """)
            indexes = cur.fetchall()
            if indexes:
                print(f"\n📇 Index vectoriel trouvé:")
                for idx in indexes:
                    print(f"  - {idx['indexname']}")
            else:
                print("\n⚠️  ATTENTION: Aucun index vectoriel trouvé sur 'embedding'")
                print("   Cela peut ralentir considérablement les recherches.")

        conn.close()
        print("\n✅ Base de données accessible et opérationnelle")
        return True

    except Exception as e:
        print(f"\n❌ Erreur de connexion à la base de données: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Point d'entrée principal."""
    print("""
    ╔═══════════════════════════════════════════════════════════════════════╗
    ║                   DIAGNOSTIC RECHERCHE RAG                            ║
    ║                                                                       ║
    ║  Ce script teste la recherche vectorielle et identifie les problèmes ║
    ╚═══════════════════════════════════════════════════════════════════════╝
    """)

    # Configuration
    print(f"🔧 Configuration:")
    print(f"  - Embeddings API: {EMBEDDINGS_API_URL}")
    print(f"  - Database: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'N/A'}")

    # Vérifier la base de données
    db_ok = await check_database_status()
    if not db_ok:
        print("\n❌ Impossible de continuer sans accès à la base de données.")
        return

    # Tests de recherche
    test_queries = [
        "comment désannuler un séjour annulé à tort",
        "désannulation séjour Sillage",
        "message A11 annulation",
        "réactiver un séjour annulé",
    ]

    print(f"\n{'='*80}")
    print(f"🧪 TESTS DE RECHERCHE")
    print(f"{'='*80}")
    print(f"Nombre de queries à tester: {len(test_queries)}\n")

    for query in test_queries:
        await test_query(query)
        await asyncio.sleep(0.5)  # Petite pause entre les tests

    print(f"\n{'='*80}")
    print("✅ DIAGNOSTIC TERMINÉ")
    print(f"{'='*80}\n")

    print("📝 RECOMMANDATIONS:")
    print("  1. Si aucun résultat: vérifier que les documents sont bien ingérés")
    print("  2. Si scores faibles (<0.5): considérer le reranking ou améliorer les chunks")
    print("  3. Si problème d'embeddings: vérifier que le service est accessible")
    print("  4. Si recherche lente: vérifier l'index vectoriel (HNSW)")

if __name__ == "__main__":
    asyncio.run(main())
