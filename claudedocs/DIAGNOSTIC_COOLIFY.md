# Diagnostic Recherche RAG sur Coolify

## Problème identifié
Les chunks existent en base de données mais ne sont pas trouvés lors d'une recherche simple : "comment désannuler un séjour annulé à tort"

## Option 1 : Vérifier les logs de l'API en temps réel

### Étape 1 : Connectez-vous à votre serveur Coolify
```bash
ssh votre-serveur-coolify
```

### Étape 2 : Visualisez les logs de l'API
```bash
# Remplacez <project-name> par le nom de votre projet Coolify
docker logs -f <project-name>-ragfab-api --tail 100

# Ou si le nom est différent :
docker ps | grep ragfab
# Puis utilisez le nom du container trouvé
```

### Étape 3 : Faites une recherche depuis l'interface
1. Ouvrez votre interface RAGFab dans le navigateur
2. Posez la question : "comment désannuler un séjour annulé à tort"
3. Observez les logs en temps réel

**Recherchez dans les logs :**
- `🔧 Query enrichie:` → Vérifier si la query est enrichie
- `📚 Sources récupérées` → Vérifier combien de sources sont trouvées
- `search_knowledge_base_tool` → Vérifier si le tool est appelé
- `Erreur` ou `ERROR` → Identifier les erreurs

---

## Option 2 : Test via SQL directement en base

### Étape 1 : Connectez-vous au container PostgreSQL
```bash
# Sur votre serveur Coolify
docker exec -it <project-name>-postgres psql -U raguser -d ragdb
```

### Étape 2 : Vérifiez l'état de la base
```sql
-- Nombre de documents
SELECT COUNT(*) FROM documents;

-- Nombre de chunks
SELECT COUNT(*) FROM chunks;

-- Lister les documents
SELECT id, title, source, created_at FROM documents ORDER BY created_at DESC LIMIT 5;

-- Vérifier la dimension des embeddings
SELECT array_length(embedding, 1) as dimension FROM chunks LIMIT 1;

-- Vérifier l'index vectoriel
SELECT indexname FROM pg_indexes WHERE tablename = 'chunks' AND indexdef LIKE '%embedding%';
```

### Étape 3 : Test de recherche vectorielle manuelle

**ATTENTION**: Cette étape nécessite de générer un embedding pour la query.

```sql
-- Pour tester avec un embedding factice (juste pour vérifier que la recherche fonctionne)
-- Récupérer un embedding existant pour test
SELECT embedding FROM chunks LIMIT 1;

-- Puis tester la recherche (remplacez <embedding> par un vrai vecteur)
SELECT
    c.content,
    d.title,
    (c.embedding <=> '<embedding>'::vector) as distance
FROM chunks c
JOIN documents d ON c.document_id = d.id
ORDER BY c.embedding <=> '<embedding>'::vector
LIMIT 5;
```

---

## Option 3 : Script de test Python dans le container

### Étape 1 : Créez le script de test sur le serveur

```bash
# Sur votre serveur Coolify, créez un fichier
cat > /tmp/test_search.py << 'EOF'
import asyncio
import httpx
import os

async def test_search():
    # URL de votre API (ajustez si nécessaire)
    api_url = os.getenv("API_URL", "http://localhost:8000")

    # Test 1: Vérifier l'API embeddings
    print("🔍 Test 1: Service d'embeddings...")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "http://embeddings:8001/embed",
                json={"texts": ["test"]}
            )
            print(f"✅ Embeddings API OK (status: {response.status_code})")
            result = response.json()
            print(f"   Dimension: {len(result['embeddings'][0])}")
    except Exception as e:
        print(f"❌ Erreur embeddings: {e}")

    # Test 2: Recherche via l'API RAG
    print("\n🔍 Test 2: Recherche RAG...")
    query = "comment désannuler un séjour annulé à tort"

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Vous devrez vous authentifier si nécessaire
            # headers = {"Authorization": "Bearer YOUR_TOKEN"}

            response = await client.post(
                f"{api_url}/api/conversations/test-conversation-id/messages",
                json={"content": query}
            )

            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Réponse reçue")
                print(f"   Nombre de sources: {len(result.get('sources', []))}")
                if result.get('sources'):
                    print("   Sources:")
                    for i, src in enumerate(result['sources'][:3], 1):
                        print(f"     {i}. {src.get('title', 'N/A')}")
            else:
                print(f"❌ Erreur: {response.text}")
    except Exception as e:
        print(f"❌ Erreur API: {e}")

asyncio.run(test_search())
EOF
```

### Étape 2 : Exécutez le script dans le container API
```bash
# Copiez le script dans le container
docker cp /tmp/test_search.py <project-name>-ragfab-api:/tmp/

# Exécutez-le
docker exec -it <project-name>-ragfab-api python /tmp/test_search.py
```

---

## Option 4 : Test via curl (le plus simple)

### Étape 1 : Récupérez un token d'authentification

```bash
# Remplacez par l'URL de votre instance Coolify
API_URL="https://votre-api.coolify.fr"

# Login pour obtenir un token
curl -X POST "$API_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin"}' \
  | jq -r '.access_token'

# Sauvegardez le token
TOKEN="<coller-le-token-ici>"
```

### Étape 2 : Créez une conversation de test

```bash
curl -X POST "$API_URL/api/conversations" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": "Test recherche"}' \
  | jq

# Récupérez l'ID de la conversation
CONV_ID="<id-de-la-conversation>"
```

### Étape 3 : Testez la recherche

```bash
curl -X POST "$API_URL/api/conversations/$CONV_ID/messages" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"content": "comment désannuler un séjour annulé à tort"}' \
  | jq

# Observez la réponse, particulièrement le champ "sources"
```

---

## Analyse des résultats

### Si aucune source n'est trouvée

**Causes possibles :**

1. **Problème d'embeddings**
   - Le service d'embeddings ne fonctionne pas
   - Les chunks n'ont pas d'embeddings générés
   - Solution : Vérifier `docker logs <project-name>-embeddings`

2. **LLM n'appelle pas le tool**
   - `LLM_USE_TOOLS=false` dans la config
   - Le LLM ne comprend pas qu'il doit utiliser le tool
   - Solution : Vérifier les variables d'environnement, forcer `LLM_USE_TOOLS=true`

3. **Problème de similarité vectorielle**
   - Les embeddings des chunks ne matchent pas avec la query
   - Score de similarité trop faible
   - Solution : Vérifier avec une query plus proche du contenu des chunks

### Si des sources sont trouvées mais ne semblent pas pertinentes

**Causes possibles :**

1. **Reranking désactivé**
   - `RERANKER_ENABLED=false`
   - Solution : Activer le reranking pour améliorer la précision

2. **Enrichissement de query défaillant**
   - La query n'est pas enrichie avec le contexte conversationnel
   - Solution : Vérifier les logs pour voir si `🔧 Query enrichie` apparaît

3. **Chunks mal découpés**
   - Les chunks sont trop grands ou trop petits
   - Solution : Réingérer les documents avec `CHUNK_SIZE` et `CHUNK_OVERLAP` ajustés

---

## Variables à vérifier dans Coolify

Dans l'interface Coolify, vérifiez ces variables d'environnement :

```bash
# LLM Configuration
LLM_USE_TOOLS=true  # DOIT être true pour function calling
LLM_API_URL=<url-de-votre-llm>
LLM_API_KEY=<clé-api>
LLM_MODEL_NAME=<nom-du-modèle>

# Embeddings
EMBEDDINGS_API_URL=http://ragfab-embeddings:8001  # Ou embeddings.internal
EMBEDDING_DIMENSION=1024

# Reranking (recommandé pour améliorer la précision)
RERANKER_ENABLED=false  # Essayez avec true si problème persiste
RERANKER_API_URL=http://ragfab-reranker:8002

# Adjacent chunks (contexte enrichi)
USE_ADJACENT_CHUNKS=true
```

---

## Solutions rapides selon le diagnostic

### Solution 1 : Forcer le tool calling
Si le LLM n'appelle pas le tool, modifiez dans Coolify :
```bash
LLM_USE_TOOLS=true
RAG_PROVIDER=mistral  # Ou autre provider supportant function calling
```

### Solution 2 : Activer le reranking
Si les résultats sont de mauvaise qualité :
```bash
RERANKER_ENABLED=true
```

### Solution 3 : Améliorer le chunking
Si les chunks sont mal découpés, réingérez avec :
```bash
CHUNK_SIZE=1000  # Réduire pour chunks plus petits et précis
CHUNK_OVERLAP=400  # Augmenter pour plus de contexte
```

### Solution 4 : Vérifier le service d'embeddings
```bash
# Test direct du service
docker exec -it <project-name>-embeddings curl http://localhost:8001/health

# Vérifier les logs
docker logs <project-name>-embeddings --tail 50
```

---

## Besoin d'aide ?

Si le problème persiste après ces tests, partagez :
1. Les logs de l'API lors d'une recherche
2. Les résultats des requêtes SQL (nombre de documents/chunks)
3. Les variables d'environnement LLM_* et EMBEDDINGS_*
4. La réponse du test curl

Je pourrai alors vous aider à identifier la cause exacte.
