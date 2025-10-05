"""
RAG CLI Agent avec PostgreSQL/PGVector et Chocolatine-2-14B
============================================================
Agent CLI basé sur texte qui effectue des recherches dans la base de connaissances
en utilisant la similarité sémantique avec Chocolatine-2-14B
"""

import asyncio
import asyncpg
import json
import logging
import os
import sys
from typing import Any

from dotenv import load_dotenv
from pydantic_ai import Agent, RunContext

# Charger les variables d'environnement
load_dotenv(".env")

logger = logging.getLogger(__name__)

# Pool de connexion à la base de données
db_pool = None


async def initialize_db():
    """Initialise le pool de connexions à la base de données."""
    global db_pool
    if not db_pool:
        db_pool = await asyncpg.create_pool(
            os.getenv("DATABASE_URL"),
            min_size=2,
            max_size=10,
            command_timeout=60,
        )
        logger.info("Pool de connexions BD initialisé")


async def close_db():
    """Ferme le pool de connexions à la base de données."""
    global db_pool
    if db_pool:
        await db_pool.close()
        logger.info("Pool de connexions BD fermé")


async def search_knowledge_base(
    ctx: RunContext[None], query: str, limit: int = 5
) -> str:
    """
    Recherche dans la base de connaissances par similarité sémantique.

    Args:
        query: Requête de recherche pour trouver des informations pertinentes
        limit: Nombre maximum de résultats à retourner (défaut: 5)

    Returns:
        Résultats de recherche formatés avec citations des sources
    """
    try:
        # S'assurer que la base de données est initialisée
        if not db_pool:
            await initialize_db()

        # Générer l'embedding pour la requête
        from ingestion.embedder import create_embedder

        embedder = create_embedder()
        query_embedding = await embedder.embed_query(query)

        # Convertir au format vecteur PostgreSQL
        embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"

        # Rechercher avec la fonction match_chunks
        async with db_pool.acquire() as conn:
            results = await conn.fetch(
                """
                SELECT * FROM match_chunks($1::vector, $2)
                """,
                embedding_str,
                limit,
            )

        # Formater les résultats pour la réponse
        if not results:
            return "Aucune information pertinente trouvée dans la base de connaissances pour votre requête."

        # Construire la réponse avec les sources
        response_parts = []
        for i, row in enumerate(results, 1):
            similarity = row["similarity"]
            content = row["content"]
            doc_title = row["document_title"]
            doc_source = row["document_source"]

            response_parts.append(f"[Source: {doc_title}]\n{content}\n")

        if not response_parts:
            return "Des résultats ont été trouvés mais ils ne sont peut-être pas directement pertinents pour votre requête. Veuillez reformuler votre question."

        return (
            f"Trouvé {len(response_parts)} résultats pertinents:\n\n"
            + "\n---\n".join(response_parts)
        )

    except Exception as e:
        logger.error(f"Échec de la recherche dans la base de connaissances: {e}", exc_info=True)
        return f"J'ai rencontré une erreur lors de la recherche dans la base de connaissances: {str(e)}"


# Importer le provider Chocolatine
from utils.chocolatine_provider import get_chocolatine_model

# Créer l'agent PydanticAI avec le modèle Chocolatine et l'outil RAG
chocolatine_model = get_chocolatine_model()

agent = Agent(
    chocolatine_model,
    system_prompt="""Tu es un assistant intelligent de connaissances avec accès à la documentation et aux informations d'une organisation.
Ton rôle est d'aider les utilisateurs à trouver des informations précises dans la base de connaissances.
Tu as un comportement professionnel mais amical.

IMPORTANT: On te fournira des extraits de la base de connaissances en contexte pour répondre aux questions.
Utilise UNIQUEMENT les informations fournies dans le contexte pour répondre.
Si l'information n'est pas dans le contexte fourni, indique-le clairement.
Sois concis mais complet dans tes réponses.
Cite toujours les sources des documents utilisés dans ta réponse.

Réponds toujours en français, car c'est la langue principale de l'utilisateur.""",
)


async def run_cli():
    """Exécute l'agent dans une CLI interactive avec streaming."""

    # Initialiser la base de données
    await initialize_db()

    print("=" * 60)
    print("🤖 Assistant RAG de Connaissances (Chocolatine-2-14B)")
    print("=" * 60)
    print("Posez-moi des questions sur la base de connaissances!")
    print("Tapez 'quit', 'exit', ou Ctrl+C pour quitter.")
    print("=" * 60)
    print()

    message_history = []

    try:
        while True:
            # Obtenir l'entrée utilisateur
            try:
                user_input = input("Vous: ").strip()
            except EOFError:
                break

            if not user_input:
                continue

            # Vérifier les commandes de sortie
            if user_input.lower() in ["quit", "exit", "bye", "au revoir"]:
                print("\nAssistant: Merci d'avoir utilisé l'assistant de connaissances. Au revoir!")
                break

            print("Assistant: ", end="", flush=True)

            try:
                # Rechercher dans la base de connaissances AVANT d'appeler l'agent
                context = await search_knowledge_base(None, user_input, limit=3)

                # Construire le prompt avec le contexte
                prompt_with_context = f"""Contexte de la base de connaissances:
{context}

---

Question de l'utilisateur: {user_input}

Réponds à la question en utilisant UNIQUEMENT les informations du contexte ci-dessus."""

                # Streamer la réponse avec run_stream
                async with agent.run_stream(
                    prompt_with_context, message_history=message_history
                ) as result:
                    # Streamer le texte au fur et à mesure (delta=True pour uniquement les nouveaux tokens)
                    async for text in result.stream_text(delta=True):
                        # Afficher uniquement le nouveau token
                        print(text, end="", flush=True)

                    print()  # Nouvelle ligne après la fin du streaming

                    # Mettre à jour l'historique des messages pour le contexte
                    message_history = result.all_messages()

            except KeyboardInterrupt:
                print("\n\n[Interrompu]")
                break
            except Exception as e:
                print(f"\n\nErreur: {e}")
                logger.error(f"Erreur de l'agent: {e}", exc_info=True)

            print()  # Ligne supplémentaire pour la lisibilité

    except KeyboardInterrupt:
        print("\n\nAu revoir!")
    finally:
        await close_db()


async def main():
    """Point d'entrée principal."""
    # Configurer le logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Vérifier les variables d'environnement requises
    if not os.getenv("DATABASE_URL"):
        logger.error("La variable d'environnement DATABASE_URL est requise")
        sys.exit(1)

    if not os.getenv("CHOCOLATINE_API_URL"):
        logger.error("La variable d'environnement CHOCOLATINE_API_URL est requise")
        sys.exit(1)

    if not os.getenv("EMBEDDINGS_API_URL"):
        logger.error("La variable d'environnement EMBEDDINGS_API_URL est requise")
        sys.exit(1)

    # Exécuter la CLI
    await run_cli()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nArrêt en cours...")
