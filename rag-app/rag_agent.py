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

            # Nettoyer le contenu des caractères mal encodés (surrogates)
            try:
                # Encoder en UTF-8 avec remplacement des surrogates, puis décoder
                clean_content = content.encode('utf-8', errors='replace').decode('utf-8')
                clean_title = doc_title.encode('utf-8', errors='replace').decode('utf-8')
            except (UnicodeEncodeError, UnicodeDecodeError):
                # En cas d'erreur, utiliser ascii avec ignore
                clean_content = content.encode('ascii', errors='ignore').decode('ascii')
                clean_title = doc_title.encode('ascii', errors='ignore').decode('ascii')

            response_parts.append(f"[Source: {clean_title}]\n{clean_content}\n")

        if not response_parts:
            return "Des résultats ont été trouvés mais ils ne sont peut-être pas directement pertinents pour votre requête. Veuillez reformuler votre question."

        return (
            f"Trouvé {len(response_parts)} résultats pertinents:\n\n"
            + "\n---\n".join(response_parts)
        )

    except Exception as e:
        logger.error(f"Échec de la recherche dans la base de connaissances: {e}", exc_info=True)
        return f"J'ai rencontré une erreur lors de la recherche dans la base de connaissances: {str(e)}"


# Importer les providers
from utils.chocolatine_provider import get_chocolatine_model
from utils.mistral_provider import get_mistral_model


def get_rag_provider():
    """Factory function pour obtenir le provider RAG configuré."""
    provider_name = os.getenv("RAG_PROVIDER", "chocolatine").lower()

    if provider_name == "mistral":
        logger.info("Utilisation du provider Mistral avec support des tools")
        return "mistral", get_mistral_model()
    else:
        logger.info("Utilisation du provider Chocolatine avec injection manuelle de contexte")
        return "chocolatine", get_chocolatine_model()


# Obtenir le provider configuré
provider_type, model = get_rag_provider()

# System prompt de base
BASE_SYSTEM_PROMPT = """Tu es un assistant intelligent de connaissances avec accès à la documentation et aux informations d'une organisation.
Ton rôle est d'aider les utilisateurs à trouver des informations précises dans la base de connaissances.
Tu as un comportement professionnel mais amical.

Réponds toujours en français, car c'est la langue principale de l'utilisateur."""

# Créer l'agent selon le provider
if provider_type == "mistral":
    # Mistral avec tools
    agent = Agent(
        model,
        system_prompt=BASE_SYSTEM_PROMPT + """

Tu as accès à un outil 'search_knowledge_base' qui te permet de rechercher dans la base de connaissances.
Utilise cet outil dès que l'utilisateur pose une question nécessitant des informations de la base de connaissances.

IMPORTANT: Utilise UNIQUEMENT les informations retournées par l'outil search_knowledge_base pour répondre.
Si l'outil ne trouve pas d'informations pertinentes, indique-le clairement à l'utilisateur.
Sois concis mais complet dans tes réponses.
Cite toujours les sources des documents utilisés dans ta réponse.""",
        tools=[search_knowledge_base],
    )
else:
    # Chocolatine avec injection manuelle
    agent = Agent(
        model,
        system_prompt=BASE_SYSTEM_PROMPT + """

IMPORTANT: On te fournira des extraits pertinents de la base de connaissances en contexte pour répondre aux questions.
Utilise UNIQUEMENT les informations fournies dans le contexte pour répondre.
Si l'information n'est pas dans le contexte fourni, indique-le clairement.
Sois concis mais complet dans tes réponses.
Cite toujours les sources des documents utilisés dans ta réponse.""",
    )


async def run_cli():
    """Exécute l'agent dans une CLI interactive avec streaming."""

    # Initialiser la base de données
    await initialize_db()

    provider_display = "Mistral 7B avec tools" if provider_type == "mistral" else "Chocolatine-2-14B manuel"

    print("=" * 60)
    print(f"🤖 Assistant RAG de Connaissances ({provider_display})")
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
                if provider_type == "mistral":
                    # Mode Mistral: utiliser run() au lieu de run_stream() pour supporter les tools
                    # Le streaming avec tools est complexe dans PydanticAI
                    result = await agent.run(user_input, message_history=message_history)
                    print(result.data)
                    print()
                    message_history = result.all_messages()

                else:
                    # Mode Chocolatine: injection manuelle du contexte
                    context = await search_knowledge_base(None, user_input, limit=3)

                    prompt_with_context = f"""Contexte de la base de connaissances:
{context}

---

Question de l'utilisateur: {user_input}

Réponds à la question en utilisant UNIQUEMENT les informations du contexte ci-dessus."""

                    async with agent.run_stream(
                        prompt_with_context, message_history=message_history
                    ) as result:
                        async for text in result.stream_text(delta=True):
                            print(text, end="", flush=True)

                        print()
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
    log_level = logging.DEBUG if provider_type == "mistral" else logging.INFO
    logging.basicConfig(
        level=log_level,
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
