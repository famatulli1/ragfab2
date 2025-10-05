# 🎉 Interface Web RAGFab - Prête à Tester !

## ✅ Services Démarrés

Tous les services sont maintenant actifs :

```bash
✅ PostgreSQL      - Port 5432 (avec schéma web complet)
✅ Embeddings      - Port 8001
✅ API Backend     - Port 8000
✅ Frontend React  - Port 3001
```

## 🌐 Accès à l'Interface

### Chat Public
**URL :** http://localhost:3001

**Fonctionnalités disponibles :**
- ✅ Création de nouvelles conversations
- ✅ Sélection du provider (Mistral / Chocolatine)
- ✅ Activation/désactivation des tools
- ✅ Chat avec indicateur "typing..."
- ✅ Affichage des sources
- ✅ Boutons copier, régénérer, rating
- ✅ Export conversation en Markdown
- ✅ Mode sombre/clair

### Interface Admin
**URL :** http://localhost:3001/admin

**Credentials par défaut :**
- Username: `admin`
- Password: `admin`

⚠️ **IMPORTANT : Changez ces credentials en production !**

**Fonctionnalités disponibles :**
- ✅ Authentification JWT
- ✅ Upload de documents (drag & drop)
- ✅ Barre de progression des uploads
- ✅ Liste des documents
- ✅ Visualisation des chunks
- ✅ Suppression de documents

## 📊 Base de Données

Le schéma web a été appliqué avec succès :

**Tables créées :**
- `users` - Authentification admin
- `conversations` - Historique chat
- `messages` - Messages individuels
- `message_ratings` - Notations thumbs up/down
- `ingestion_jobs` - Suivi des uploads

**Vues créées :**
- `conversation_stats` - Statistiques par conversation
- `document_stats` - Statistiques par document

## 🧪 Tests à Effectuer

### Test 1 : Accès Frontend
```bash
# Ouvrir dans le navigateur
http://localhost:3001
```
✅ **Résultat attendu :** Page de chat s'affiche

### Test 2 : Login Admin
1. Aller sur http://localhost:3001/admin
2. Username: `admin`, Password: `admin`
3. Cliquer "Se connecter"

✅ **Résultat attendu :** Redirection vers la page admin

### Test 3 : Upload Document (Simulé)
1. Dans l'admin, glisser-déposer un fichier PDF
2. Observer la barre de progression

⚠️ **Note :** L'ingestion est actuellement simulée. Le système crée un job mais ne traite pas réellement le document.

### Test 4 : Créer Conversation
1. Sur la page chat, cliquer "Nouvelle conversation"
2. ✅ **Résultat attendu :** Conversation créée dans la sidebar

### Test 5 : Envoyer Message (Simulé)
1. Taper un message : "Bonjour, comment ça va ?"
2. Appuyer sur Entrée

⚠️ **Note :** La réponse est actuellement simulée car le vrai RAG agent n'est pas encore intégré.

✅ **Résultat attendu :** Réponse simulée s'affiche

## 🔧 Commandes Utiles

### Voir les logs
```bash
# Logs API
docker-compose logs -f ragfab-api

# Logs Frontend
docker-compose logs -f ragfab-frontend

# Logs PostgreSQL
docker-compose logs -f postgres
```

### Arrêter les services
```bash
docker-compose down
```

### Redémarrer un service
```bash
# Redémarrer l'API
docker-compose restart ragfab-api

# Redémarrer le frontend
docker-compose restart ragfab-frontend
```

### Accéder à la base de données
```bash
docker exec -it ragfab-postgres psql -U raguser -d ragdb

# Dans psql :
\dt                          # Lister les tables
SELECT * FROM users;         # Voir les utilisateurs
SELECT * FROM conversations; # Voir les conversations
\q                           # Quitter
```

## 📝 Documentation API

Une fois l'API lancée, accédez à :

- **Swagger UI :** http://localhost:8000/docs
- **ReDoc :** http://localhost:8000/redoc

Toutes les routes sont documentées avec leurs paramètres.

## ⚠️ Limitations Actuelles

### Backend (À intégrer)

1. **Ingestion simulée** : La fonction `process_ingestion()` dans `web-api/app/main.py` est simulée.
   - Elle crée un job d'ingestion mais ne traite pas réellement le document
   - **À faire :** Connecter au vrai système d'ingestion de `rag-app`

2. **RAG Agent simulé** : La fonction `execute_rag_agent()` retourne une réponse simulée.
   - Elle ne fait pas appel au vrai agent RAG
   - **À faire :** Intégrer avec `rag_agent.py`

3. **Export PDF non implémenté** : Seul l'export Markdown fonctionne.

### Frontend

4. **Pas de streaming** : Les réponses arrivent d'un coup (pas mot par mot comme ChatGPT).
   - C'est un choix technique pour simplifier avec les tools
   - Peut être amélioré plus tard si nécessaire

## 🚀 Prochaines Étapes

### Étape 1 : Tester l'infrastructure (MAINTENANT)

Testez l'interface pour vérifier que :
- ✅ Le frontend se charge correctement
- ✅ Le login admin fonctionne
- ✅ Les conversations peuvent être créées
- ✅ Les messages peuvent être envoyés (avec réponse simulée)
- ✅ Le mode sombre/clair fonctionne
- ✅ L'export fonctionne

### Étape 2 : Intégrer le RAG Agent réel

Modifier `web-api/app/main.py`, fonction `execute_rag_agent()` :

```python
async def execute_rag_agent(message, history, provider, use_tools):
    # Import du vrai rag_agent
    import sys
    sys.path.append('/rag-app')
    from rag_agent import get_rag_provider, Agent, search_knowledge_base

    provider_type, model = get_rag_provider(provider)

    if use_tools:
        agent = Agent(model, tools=[search_knowledge_base])
    else:
        agent = Agent(model)

    # Convertir l'historique au format attendu
    message_history = []
    for msg in history:
        message_history.append({
            "role": msg["role"],
            "content": msg["content"]
        })

    result = await agent.run(message, message_history=message_history)

    # Extraire les sources
    sources = []
    if hasattr(result, 'tool_calls'):
        for call in result.tool_calls:
            if call.function.name == 'search_knowledge_base':
                # Extraire les chunks retournés
                sources.extend(extract_sources_from_result(call))

    return {
        "content": result.data,
        "sources": sources,
        "model_name": provider,
        "token_usage": result.usage if hasattr(result, 'usage') else None
    }
```

### Étape 3 : Intégrer l'ingestion réelle

Modifier `web-api/app/main.py`, fonction `process_ingestion()` :

```python
async def process_ingestion(job_id, file_path, filename):
    import sys
    sys.path.append('/rag-app')
    from ingestion.ingest import DocumentIngestionPipeline
    from utils.models import IngestionConfig

    try:
        # Créer la configuration
        config = IngestionConfig(
            database_url=settings.DATABASE_URL,
            embeddings_api_url=settings.EMBEDDINGS_API_URL,
            chunk_size=1000,
            chunk_overlap=200
        )

        # Créer le pipeline
        pipeline = DocumentIngestionPipeline(config)

        # Ingérer le document
        result = await pipeline.ingest_document(file_path)

        # Mettre à jour le job
        async with db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE ingestion_jobs
                SET status = 'completed',
                    document_id = $1,
                    chunks_created = $2,
                    completed_at = CURRENT_TIMESTAMP
                WHERE id = $3
            """, result.document_id, result.chunks_created, job_id)

    except Exception as e:
        # Marquer le job comme échoué
        async with db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE ingestion_jobs
                SET status = 'failed',
                    error_message = $1,
                    completed_at = CURRENT_TIMESTAMP
                WHERE id = $2
            """, str(e), job_id)
```

### Étape 4 : Tests End-to-End

1. Uploader un vrai document PDF
2. Attendre la fin de l'ingestion
3. Créer une conversation
4. Poser une question sur le document
5. Vérifier que le RAG retourne les bonnes informations avec sources

## 🎯 Checklist de Fonctionnalité

### Infrastructure ✅
- [x] PostgreSQL avec schéma web
- [x] API Backend FastAPI
- [x] Frontend React build et déployé
- [x] Services Docker actifs

### Frontend ✅
- [x] Page de chat accessible
- [x] Page admin accessible
- [x] Authentification JWT
- [x] Interface responsive
- [x] Mode sombre/clair
- [x] Toutes les routes React fonctionnelles

### Backend (Partiellement) ⚠️
- [x] Routes API toutes créées
- [x] Validation Pydantic
- [x] Authentification JWT
- [ ] **Intégration RAG agent** (simulé)
- [ ] **Intégration ingestion** (simulé)
- [ ] Export PDF

## 📞 Support

En cas de problème :

1. Vérifiez que tous les services sont actifs :
   ```bash
   docker-compose ps
   ```

2. Consultez les logs :
   ```bash
   docker-compose logs <service>
   ```

3. Redémarrez les services si nécessaire :
   ```bash
   docker-compose restart <service>
   ```

---

**L'interface web est prête à être testée !** 🎉

Une fois les tests de l'infrastructure validés, nous pourrons intégrer le vrai RAG agent et le système d'ingestion.
