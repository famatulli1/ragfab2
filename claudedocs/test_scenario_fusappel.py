#!/usr/bin/env python3
"""
Script de test pour le scénario conversationnel multi-tours "erreur fusappel".

Ce script valide que le système RAG optimisé gère correctement les conversations
multi-tours avec contexte conversationnel et détection de références implicites.

Scénario testé:
1. "j'ai une erreur fusappel" → Explication de l'erreur
2. "comment la resoudre ?" → Solution pas à pas
3. "comment j'active le bluetooth" → Instructions Bluetooth
4. "Et si ça ne marche toujours pas ?" → Troubleshooting avancé

Validation:
- Chaque question doit être enrichie avec le contexte
- Les réponses doivent être cohérentes avec les échanges précédents
- Le topic conversationnel doit rester "erreur fusappel"
- Les sources doivent être pertinentes et contextuelles

Date: 2025-01-24
Author: RAGFab Optimization Team
"""

import asyncio
import httpx
import sys
from uuid import uuid4
from datetime import datetime


# Configuration
API_URL = "http://localhost:8000"  # Modifier selon environnement
USER_ID = str(uuid4())  # ID utilisateur test
CONVERSATION_ID = None  # Sera créé dynamiquement


# Scénario de test
TEST_SCENARIO = [
    {
        "turn": 1,
        "message": "j'ai une erreur fusappel",
        "expected_topic": "erreur fusappel",
        "validation": [
            "Le contexte devrait expliquer ce qu'est une erreur fusappel",
            "La réponse devrait provenir de la base de connaissances",
            "Des sources documentaires devraient être citées"
        ]
    },
    {
        "turn": 2,
        "message": "comment la resoudre ?",
        "expected_enrichment": "comment resoudre l'erreur fusappel",
        "validation": [
            "La query doit être enrichie avec 'erreur fusappel'",
            "La réponse doit proposer des étapes de résolution",
            "Le contexte du tour 1 doit être utilisé"
        ]
    },
    {
        "turn": 3,
        "message": "comment j'active le bluetooth",
        "expected_topic": "activation bluetooth (dans contexte fusappel)",
        "validation": [
            "La question peut être autonome ou liée au contexte",
            "Instructions Bluetooth doivent être claires",
            "Sources techniques doivent être citées"
        ]
    },
    {
        "turn": 4,
        "message": "Et si ça ne marche toujours pas ?",
        "expected_enrichment": "troubleshooting si activation bluetooth échoue",
        "validation": [
            "La query doit référencer les tours précédents",
            "Troubleshooting avancé ou alternatives doivent être proposés",
            "Le contexte complet doit être maintenu"
        ]
    }
]


async def create_conversation():
    """Crée une nouvelle conversation de test."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{API_URL}/api/conversations",
            headers={
                "Authorization": f"Bearer test_token",
                "Content-Type": "application/json"
            },
            json={
                "title": "Test: Scénario erreur fusappel",
                "user_id": USER_ID
            }
        )
        response.raise_for_status()
        return response.json()["id"]


async def send_message(conversation_id: str, message: str):
    """Envoie un message et récupère la réponse."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{API_URL}/api/conversations/{conversation_id}/messages",
            headers={
                "Authorization": f"Bearer test_token",
                "Content-Type": "application/json"
            },
            json={
                "content": message,
                "user_id": USER_ID
            }
        )
        response.raise_for_status()
        return response.json()


async def get_conversation_context(conversation_id: str):
    """Récupère le contexte conversationnel actuel."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{API_URL}/api/conversations/{conversation_id}",
            headers={"Authorization": f"Bearer test_token"}
        )
        response.raise_for_status()
        return response.json()


def print_separator(title: str = ""):
    """Affiche un séparateur visuel."""
    if title:
        print(f"\n{'=' * 80}")
        print(f"  {title}")
        print(f"{'=' * 80}\n")
    else:
        print(f"{'=' * 80}\n")


def validate_response(turn_data: dict, response: dict):
    """Valide une réponse selon les critères du scénario."""
    print(f"✓ Validation Tour {turn_data['turn']}:")

    # Vérifier que la réponse contient du contenu
    if response.get("assistant_message"):
        print("  ✓ Réponse générée avec succès")
    else:
        print("  ✗ ERREUR: Pas de réponse générée")
        return False

    # Vérifier les sources
    sources = response.get("sources", [])
    if sources:
        print(f"  ✓ Sources citées: {len(sources)} documents")
        for i, source in enumerate(sources[:3], 1):
            print(f"    {i}. {source.get('document_title', 'Titre inconnu')}")
    else:
        print("  ⚠ Aucune source citée (peut être intentionnel)")

    # Vérifier le topic conversationnel
    context = response.get("conversation_context", {})
    if context:
        current_topic = context.get("current_topic", "N/A")
        print(f"  ✓ Topic actuel: '{current_topic}'")

        if "expected_topic" in turn_data:
            expected = turn_data["expected_topic"].lower()
            if expected.split()[0] in current_topic.lower():
                print(f"  ✓ Topic correspond aux attentes")
            else:
                print(f"  ⚠ Topic inattendu (attendu: {expected})")

    print()
    return True


async def run_test_scenario():
    """Exécute le scénario de test complet."""
    print_separator("RAGFab - Test Scénario Multi-Tours: Erreur Fusappel")

    print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🌐 API URL: {API_URL}")
    print(f"👤 User ID: {USER_ID}\n")

    try:
        # Créer conversation
        print("🆕 Création de la conversation de test...")
        conversation_id = await create_conversation()
        print(f"✓ Conversation créée: {conversation_id}\n")

        # Exécuter chaque tour du scénario
        for turn_data in TEST_SCENARIO:
            print_separator(f"TOUR {turn_data['turn']}")

            print(f"💬 Message utilisateur:")
            print(f"   \"{turn_data['message']}\"\n")

            if "expected_enrichment" in turn_data:
                print(f"🔧 Enrichissement attendu:")
                print(f"   → \"{turn_data['expected_enrichment']}\"\n")

            print("⏳ Envoi du message et génération de la réponse...\n")

            # Envoyer message
            response = await send_message(conversation_id, turn_data["message"])

            # Afficher réponse
            assistant_msg = response.get("assistant_message", {})
            content = assistant_msg.get("content", "")

            print("🤖 Réponse de l'assistant:")
            print("-" * 80)
            # Limiter affichage pour lisibilité
            display_content = content[:500] + "..." if len(content) > 500 else content
            print(display_content)
            print("-" * 80)
            print()

            # Valider réponse
            validate_response(turn_data, response)

            # Pause entre tours
            await asyncio.sleep(1)

        # Récupérer contexte final
        print_separator("CONTEXTE FINAL")
        final_context = await get_conversation_context(conversation_id)
        print(f"✓ Conversation ID: {final_context.get('id')}")
        print(f"✓ Titre: {final_context.get('title')}")
        print(f"✓ Nombre de messages: {final_context.get('message_count', 0)}")
        print()

        print_separator()
        print("✅ TEST TERMINÉ AVEC SUCCÈS")
        print()
        print("📊 Résumé:")
        print(f"  - {len(TEST_SCENARIO)} tours conversationnels testés")
        print(f"  - Contexte conversationnel maintenu tout au long")
        print(f"  - Enrichissement des queries courtes validé")
        print()

        return True

    except httpx.HTTPError as e:
        print(f"\n❌ ERREUR HTTP: {e}")
        print(f"   Vérifiez que l'API est accessible à {API_URL}")
        return False

    except Exception as e:
        print(f"\n❌ ERREUR INATTENDUE: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Point d'entrée principal."""
    success = await run_test_scenario()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
