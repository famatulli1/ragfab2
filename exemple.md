# Guide d'utilisation de RAGFab

## Introduction

RAGFab est un système RAG (Retrieval Augmented Generation) optimisé pour le français. Il utilise Chocolatine-2-14B comme modèle de langage et Multilingual-E5-Large pour les embeddings.

## Caractéristiques principales

### Performance française
- Modèle Chocolatine-2-14B classé Top 3 sur le benchmark French LLM
- Score de 9.08/10 sur MT-Bench-French
- Équivalent à GPT-4o-mini pour le français

### Architecture autonome
- Serveur d'embeddings local avec multilingual-e5-large
- Base de données PostgreSQL avec extension PGVector
- Aucune dépendance OpenAI

### Embeddings multilingues
- Dimension : 1024 (multilingual-e5-large)
- Support de 102 langues
- Optimisé pour le français et l'anglais

## Fonctionnalités

### Ingestion de documents
RAGFab supporte de nombreux formats :
- PDF, Word, PowerPoint
- Markdown, texte brut
- HTML et autres formats via Docling

### Recherche sémantique
La recherche utilise la similarité cosinus pour trouver les documents les plus pertinents. Les résultats incluent toujours les citations des sources.

### Agent conversationnel
L'agent maintient un historique de conversation et peut répondre à des questions complexes en combinant plusieurs sources d'information.

## Déploiement

### Local avec Docker
Utilisez `docker-compose up -d` pour démarrer tous les services localement.

### Production sur Coolify
Déployez facilement sur Coolify en utilisant le fichier docker-compose.coolify.yml.

## Support

Pour toute question, consultez la documentation complète dans le README.md ou ouvrez une issue sur GitHub.
