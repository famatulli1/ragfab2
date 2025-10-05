# Session Claude Code - RAGFab avec Mistral Function Calling

**Date:** 5 octobre 2025
**Objectif:** Implémenter le function calling avec l'API Mistral pour le système RAG

---

## 🎯 Résultat Final

✅ **Système RAG complet avec function calling opérationnel**
- Provider Mistral avec tool calling automatique
- Ingestion PDF avec Docling HybridChunker
- Recherche vectorielle intelligente
- Réponses structurées avec citations des sources

---

## 📋 Travaux Réalisés

### 1. **Création du Provider Mistral** (`utils/mistral_provider.py`)

**Fonctionnalités implémentées :**
- `MistralModel` : Provider de base compatible PydanticAI
- `MistralAgentModel` : Provider avec support des tools
- Conversion automatique des tools PydanticAI → format Mistral API
- Gestion complète du workflow de function calling

**Corrections techniques :**
- Import `ArgsDict` depuis `pydantic_ai.messages` (pas depuis `models`)
- Sérialisation des arguments : `part.args.args_dict` au lieu de `part.args`
- Traitement des `ToolReturnPart` dans `ModelRequest` (pas dans `ModelResponse`)
- Messages formatés correctement pour l'ordre attendu par Mistral API

**Fichier créé :** [utils/mistral_provider.py](rag-app/utils/mistral_provider.py)

---

### 2. **Mise à Jour de l'Agent RAG** (`rag_agent.py`)

**Dual-provider system :**
```python
# Sélection automatique du provider via variable d'environnement
RAG_PROVIDER = "mistral"  # ou "chocolatine"
```

**Modes disponibles :**
- **Mistral** : Function calling automatique avec `search_knowledge_base` tool
- **Chocolatine** : Injection manuelle du contexte (pour vLLM local)

**Modifications :**
- Factory function `get_rag_provider()` pour basculer entre providers
- Mode non-streaming pour Mistral (`run()` au lieu de `run_stream()`)
- Nettoyage UTF-8 des chunks pour éviter les erreurs d'encodage

**Fichier modifié :** [rag_agent.py](rag-app/rag_agent.py:116-213)

---

### 3. **Configuration Environment** (`.env`)

**Nouvelles variables ajoutées :**
```bash
# Provider RAG
RAG_PROVIDER=mistral

# API Mistral
MISTRAL_API_KEY=0SINPnbC1ebzLbEzxrRmUaPBkVo9Fhvf
MISTRAL_API_URL=https://api.mistral.ai
MISTRAL_MODEL_NAME=mistral-small-latest
MISTRAL_TIMEOUT=120.0

# Logs
LOG_LEVEL=INFO
```

**Fichier modifié :** [.env](\.env:40-71)

---

### 4. **Docker Compose** (`docker-compose.yml`)

**Variables d'environnement rag-app :**
```yaml
environment:
  RAG_PROVIDER: ${RAG_PROVIDER:-chocolatine}
  MISTRAL_API_KEY: ${MISTRAL_API_KEY:-}
  MISTRAL_API_URL: ${MISTRAL_API_URL:-https://api.mistral.ai}
  MISTRAL_MODEL_NAME: ${MISTRAL_MODEL_NAME:-mistral-small-latest}
  MISTRAL_TIMEOUT: ${MISTRAL_TIMEOUT:-120.0}
```

**Fichier modifié :** [docker-compose.yml](docker-compose.yml:64-71)

---

### 5. **Optimisations Ingestion**

#### **A. Fix détection fichiers PDF** (`ingestion/ingest.py`)

**Problème :** Le glob pattern `**/*.pdf` ne trouvait pas les PDFs à la racine du dossier `documents/`

**Solution :**
```python
for pattern in patterns:
    # Chercher à la racine du dossier
    files.extend(glob.glob(os.path.join(self.documents_folder, pattern)))
    # Chercher dans les sous-dossiers
    files.extend(glob.glob(os.path.join(self.documents_folder, "**", pattern), recursive=True))
```

**Fichier modifié :** [ingestion/ingest.py](rag-app/ingestion/ingest.py:251-258)

#### **B. Optimisation batch embeddings** (`ingestion/embedder.py`)

**Problème :** Timeouts lors du traitement de 51 chunks en un seul batch

**Solution :**
- `batch_size: 100 → 20` chunks par batch
- `timeout: 60s → 90s` par requête
- Le système génère maintenant 3 batches au lieu d'un seul

**Résultat :** Moins de timeouts, fallback individuel uniquement en cas d'erreur réelle

**Fichier modifié :** [ingestion/embedder.py](rag-app/ingestion/embedder.py:32-35)

#### **C. Nettoyage caractères UTF-8** (`rag_agent.py`)

**Problème :** Caractères surrogates UTF-8 invalides dans les chunks PDF causaient des erreurs

**Solution :**
```python
# Nettoyer le contenu des caractères mal encodés
clean_content = content.encode('utf-8', errors='replace').decode('utf-8')
clean_title = doc_title.encode('utf-8', errors='replace').decode('utf-8')
```

**Fichier modifié :** [rag_agent.py](rag-app/rag_agent.py:98-108)

---

### 6. **Logs Debug Désactivés** (`utils/mistral_provider.py`)

Pour une sortie console plus propre, les logs debug ont été commentés :
- `logger.debug(f"Mistral API payload: ...")` → commenté
- `logger.debug(f"Formatting {len(messages)} messages:")` → commenté

**Fichier modifié :** [utils/mistral_provider.py](rag-app/utils/mistral_provider.py:188-297)

---

## 🔧 Problèmes Résolus

### Erreur 1: `ImportError: cannot import name 'ModelResponsePart'`
**Cause :** Mauvais module d'import
**Solution :** Importer depuis `pydantic_ai.messages` au lieu de `pydantic_ai.models`

### Erreur 2: `'dict' object has no attribute 'args_dict'`
**Cause :** Tentative d'accès à `.args_dict` sur un dict brut
**Solution :** Créer `ArgsDict(args_dict=args_data)` au lieu de passer le dict directement

### Erreur 3: `Object of type ArgsDict is not JSON serializable`
**Cause :** Sérialisation directe de l'objet `ArgsDict`
**Solution :** Extraire le dict avec `part.args.args_dict` avant `json.dumps()`

### Erreur 4: `Expected last role User or Tool but got assistant`
**Cause :** `ToolReturnPart` traité dans `ModelResponse` au lieu de `ModelRequest`
**Solution :** Déplacer le traitement dans la section `ModelRequest`

### Erreur 5: Timeout batch embeddings
**Cause :** 51 chunks trop lourd pour un seul batch de 60s
**Solution :** Réduire `batch_size` à 20 et augmenter `timeout` à 90s

### Erreur 6: `'utf-8' codec can't encode character '\udcc3'`
**Cause :** Caractères surrogates UTF-8 invalides dans le PDF
**Solution :** Nettoyage avec `encode('utf-8', errors='replace')`

### Erreur 7: PDFs non détectés lors de l'ingestion
**Cause :** Pattern glob `**/*.pdf` ne trouve pas les fichiers à la racine
**Solution :** Ajouter un glob pour la racine + un pour les sous-dossiers

---

## 📊 Test du Système

### Document ingéré
- **Fichier :** `mes_manuel_utilisateur_medimail_webmail_v1.5.pdf` (1.1 MB)
- **Chunks créés :** 51 chunks avec HybridChunker
- **Temps de conversion Docling :** ~135 secondes
- **Qualité :** Chunks cohérents et bien structurés

### Exemples de questions testées

**Q1:** "Qu'est-ce que RAGFab ?"
✅ Réponse structurée complète avec architecture, fonctionnalités, déploiement

**Q2:** "Comment accéder à Medimail ?"
✅ Réponse avec 3 méthodes d'accès + durée de conservation

**Q3:** "Quels sont les dossiers par défaut dans Medimail ?"
✅ Liste exacte des 4 dossiers + info sur sous-dossiers

### Workflow observé
```
Question utilisateur
    ↓
Mistral API (tool_choice: auto)
    ↓
Tool call détecté: search_knowledge_base(query="...", limit=5)
    ↓
Embeddings de la query (multilingual-e5-large)
    ↓
Recherche vectorielle PostgreSQL (similarité cosinus)
    ↓
Top 5 chunks retournés
    ↓
Tool results envoyés à Mistral
    ↓
Réponse finale structurée avec citations
```

---

## 🚀 Commandes Utiles

### Démarrer les services
```bash
cd c:\Users\famat\Documents\rag-cole\ragfab
docker-compose up -d postgres embeddings
```

### Lancer l'agent RAG (mode interactif)
```bash
docker-compose --profile app run --rm rag-app
```

### Ingérer un document PDF
```bash
# Placer le PDF dans rag-app/documents/
docker-compose --profile app run --rm rag-app python -m ingestion.ingest
```

### Vérifier les documents ingérés
```bash
docker-compose exec postgres psql -U raguser -d ragdb -c "SELECT title, COUNT(c.id) as chunks FROM documents d LEFT JOIN chunks c ON d.id = c.document_id GROUP BY d.id, title;"
```

### Voir le contenu des chunks
```bash
docker-compose exec postgres psql -U raguser -d ragdb -c "SELECT LEFT(content, 200) FROM chunks ORDER BY chunk_index LIMIT 5;"
```

### Rebuild après modifications
```bash
docker-compose build rag-app
```

---

## 📁 Fichiers Modifiés/Créés

| Fichier | Type | Description |
|---------|------|-------------|
| `rag-app/utils/mistral_provider.py` | **CRÉÉ** | Provider Mistral avec function calling |
| `rag-app/rag_agent.py` | Modifié | Dual-provider + nettoyage UTF-8 |
| `rag-app/ingestion/ingest.py` | Modifié | Fix détection PDFs racine |
| `rag-app/ingestion/embedder.py` | Modifié | Optimisation batch size |
| `.env` | Modifié | Variables Mistral ajoutées |
| `docker-compose.yml` | Modifié | Env vars Mistral pour rag-app |

---

## 🎓 Concepts Clés Utilisés

### PydanticAI Framework
- `Agent` : Agent conversationnel avec tools
- `Model` / `AgentModel` : Providers pour différents LLMs
- `ToolDefinition` : Définition des tools disponibles
- `ModelRequest` / `ModelResponse` : Format des messages
- `ArgsDict` : Wrapper pour arguments de tool calls

### Mistral API
- Format OpenAI-compatible
- `tools` : Liste des fonctions disponibles
- `tool_choice: "auto"` : LLM décide quand appeler les tools
- `tool_calls` : Appels de fonctions dans la réponse
- Messages role `"tool"` : Résultats des tools

### Docling
- **HybridChunker** : Chunking intelligent respectant la structure du document
- **DocumentConverter** : Conversion PDF → Markdown
- **DoclingDocument** : Représentation interne du document avec structure préservée

### Embeddings
- **Modèle :** multilingual-e5-large (1024 dimensions)
- **Serveur :** FastAPI autonome sur port 8001
- **Batch processing :** 20 chunks par batch pour éviter timeouts

---

## 🔄 Workflow Function Calling

### Étape 1: Requête initiale
```json
{
  "model": "mistral-small-latest",
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "Qu'est-ce que RAGFab ?"}
  ],
  "tools": [{
    "type": "function",
    "function": {
      "name": "search_knowledge_base",
      "parameters": {...}
    }
  }],
  "tool_choice": "auto"
}
```

### Étape 2: Réponse Mistral avec tool call
```json
{
  "role": "assistant",
  "tool_calls": [{
    "id": "call_xyz",
    "function": {
      "name": "search_knowledge_base",
      "arguments": "{\"query\": \"RAGFab\", \"limit\": 5}"
    }
  }]
}
```

### Étape 3: Exécution du tool par PydanticAI
```python
# PydanticAI exécute automatiquement search_knowledge_base
results = await search_knowledge_base(ctx, query="RAGFab", limit=5)
```

### Étape 4: Envoi des résultats à Mistral
```json
{
  "messages": [
    {...système...},
    {...user...},
    {...assistant avec tool_calls...},
    {
      "role": "tool",
      "tool_call_id": "call_xyz",
      "content": "Trouvé 2 résultats pertinents:\n[Source: Guide]..."
    }
  ]
}
```

### Étape 5: Réponse finale de Mistral
```json
{
  "role": "assistant",
  "content": "RAGFab est un système RAG optimisé pour le français..."
}
```

---

## 💡 Leçons Apprises

1. **PydanticAI streaming ne supporte pas bien les tools** → Utiliser `run()` au lieu de `run_stream()`

2. **ArgsDict n'est pas un dict** → Toujours extraire avec `.args_dict` avant sérialisation JSON

3. **L'ordre des messages Mistral est strict** → Tool results doivent être dans des messages séparés avec role "tool"

4. **Les caractères UTF-8 invalides sont fréquents dans les PDFs** → Toujours nettoyer avec `errors='replace'`

5. **Glob patterns `**/*` ne trouvent pas les fichiers à la racine** → Ajouter un pattern pour la racine explicitement

6. **Les batches d'embeddings trop gros timeout** → Batch size de 20 est un bon compromis

7. **Docling HybridChunker est excellent** → Chunks beaucoup plus cohérents que le découpage caractère simple

---

## 🎯 Prochaines Étapes Possibles

- [ ] Ajouter support pour plus de modèles Mistral (large, codestral)
- [ ] Implémenter le streaming avec tools (complexe avec PydanticAI)
- [ ] Ajouter d'autres tools (résumé de document, extraction d'entités)
- [ ] Monitoring des coûts API Mistral (tokens utilisés)
- [ ] Cache des embeddings pour éviter regeneration
- [ ] Interface web Streamlit/Gradio pour démo
- [ ] Multi-turn conversation avec contexte enrichi
- [ ] Support de plusieurs langues simultanément

---

## 📝 Notes Techniques

### Pourquoi Mistral Small Latest ?
- `open-mistral-7b` inventait des réponses au lieu d'appeler les tools
- `mistral-small-latest` a un meilleur support du function calling
- Bon compromis coût/performance pour le français

### Pourquoi non-streaming ?
- `run_stream()` de PydanticAI détecte les tool calls mais ne les exécute pas automatiquement
- Il faudrait gérer manuellement l'exécution des tools et le renvoi des résultats
- `run()` gère tout le workflow automatiquement

### Structure des ArgsDict
```python
# Création
args = ArgsDict(args_dict={"query": "test", "limit": 5})

# Accès
args.args_dict  # → {"query": "test", "limit": 5}

# Sérialisation JSON
json.dumps(args.args_dict)  # ✅ OK
json.dumps(args)            # ❌ TypeError
```

---

**Fin de session - Système RAGFab opérationnel avec Mistral function calling ! 🎉**
