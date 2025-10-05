# RAGFab Web Interface - Guide de Démarrage Rapide

## 🚀 Démarrage Rapide

### 1. Arrêter les conteneurs existants

```bash
cd c:\Users\famat\Documents\rag-cole\ragfab
docker-compose down
```

### 2. Supprimer le volume PostgreSQL (pour appliquer le nouveau schéma)

```bash
docker volume rm ragfab_postgres_data
```

### 3. Démarrer tous les services web

```bash
docker-compose up -d
```

Cela démarrera :
- ✅ PostgreSQL (avec schéma web)
- ✅ Serveur d'embeddings
- ✅ API Backend (FastAPI sur port 8000)
- ✅ Frontend React (sur port 3000)

### 4. Vérifier que tout fonctionne

```bash
# Vérifier les logs
docker-compose logs -f ragfab-api
docker-compose logs -f ragfab-frontend

# Vérifier que les services sont actifs
docker-compose ps
```

### 5. Accéder à l'interface web

#### Chat Public
**URL :** http://localhost:3000

- Créer une nouvelle conversation
- Choisir le provider (Mistral / Chocolatine)
- Chatter avec l'assistant RAG

#### Administration
**URL :** http://localhost:3000/admin

**Credentials par défaut :**
- Username: `admin`
- Password: `admin`

⚠️ **CHANGEZ CES CREDENTIALS EN PRODUCTION !**

Fonctionnalités admin :
- Upload de documents (PDF, DOCX, MD, TXT)
- Visualisation des chunks
- Suppression de documents
- Suivi de progression des uploads

---

## 🔧 Configuration

### Variables d'environnement importantes

Fichier `.env` :

```bash
# Ports
API_PORT=8000
FRONTEND_PORT=3000

# JWT & Auth
JWT_SECRET=your-secret-key-change-in-production-please
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin

# Mistral API
MISTRAL_API_KEY=0SINPnbC1ebzLbEzxrRmUaPBkVo9Fhvf
MISTRAL_MODEL_NAME=mistral-small-latest

# Chocolatine API
CHOCOLATINE_API_URL=https://apigpt.mynumih.fr
CHOCOLATINE_MODEL_NAME=jpacifico/Chocolatine-2-14B-Instruct-v2.0.3
```

---

## 📊 Architecture

```
┌─────────────────┐
│  Frontend React │  (port 3000)
│   (Nginx)       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  API FastAPI    │  (port 8000)
│  (Backend)      │
└────────┬────────┘
         │
    ┌────┴────┬──────────────┐
    ▼         ▼              ▼
┌────────┐ ┌──────────┐ ┌─────────┐
│Postgres│ │Embeddings│ │rag-app  │
│PGVector│ │  Server  │ │(modules)│
└────────┘ └──────────┘ └─────────┘
```

---

## 🧪 Test Complet

### 1. Tester l'API directement

```bash
# Health check
curl http://localhost:8000/health

# Docs API interactives
open http://localhost:8000/docs
```

### 2. Tester l'upload d'un document

1. Aller sur http://localhost:3000/admin
2. Se connecter avec admin/admin
3. Glisser-déposer un fichier PDF
4. Observer la progression
5. Voir les chunks créés

### 3. Tester le chat

1. Aller sur http://localhost:3000
2. Créer une nouvelle conversation
3. Choisir le provider (Mistral recommandé)
4. Poser une question sur le document uploadé
5. Observer :
   - Indicateur "typing..."
   - Réponse avec sources
   - Boutons copier, régénérer, rating

---

## 🐛 Troubleshooting

### Frontend ne démarre pas

```bash
# Vérifier les logs
docker-compose logs ragfab-frontend

# Rebuild si nécessaire
docker-compose build ragfab-frontend
docker-compose up -d ragfab-frontend
```

### API ne répond pas

```bash
# Vérifier les logs
docker-compose logs ragfab-api

# Vérifier que PostgreSQL est prêt
docker-compose logs postgres | grep "ready to accept"

# Rebuild si nécessaire
docker-compose build ragfab-api
docker-compose up -d ragfab-api
```

### Erreur 401 Unauthorized

Le token JWT a expiré. Reconnectez-vous dans l'admin.

### Upload échoue

Vérifiez que le fichier fait moins de 100 MB et est dans un format supporté (PDF, DOCX, MD, TXT).

---

## 📝 Prochaines Étapes

### Features déjà implémentées ✅

- ✅ Chat avec historique de conversations
- ✅ Choix du provider (Mistral/Chocolatine)
- ✅ Activation/désactivation des tools
- ✅ Upload de documents avec progression
- ✅ Visualisation des chunks
- ✅ Export des conversations en Markdown
- ✅ Notation des réponses (thumbs up/down)
- ✅ Régénération de réponses
- ✅ Copie de messages
- ✅ Mode sombre/clair
- ✅ Sources cliquables

### Features à ajouter (optionnel)

- [ ] Export PDF des conversations
- [ ] Recherche dans les conversations
- [ ] Filtres avancés pour les documents
- [ ] Analytics admin (stats d'utilisation)
- [ ] Multi-utilisateurs avec comptes séparés
- [ ] Partage de conversations

---

## 🔒 Sécurité

### Pour la production

1. **Changez les credentials admin** dans `.env`
2. **Générez un JWT_SECRET fort** :
   ```bash
   openssl rand -hex 32
   ```
3. **Utilisez HTTPS** (configurez un reverse proxy)
4. **Limitez l'accès à l'admin** par IP si possible
5. **Activez les rate limits** sur l'API

---

## 📚 Documentation API

Une fois l'API lancée, accédez à :

- **Swagger UI :** http://localhost:8000/docs
- **ReDoc :** http://localhost:8000/redoc

Vous y trouverez toutes les routes disponibles avec leurs paramètres.

---

## ✅ Checklist de Démarrage

- [ ] PostgreSQL démarre et applique les schémas
- [ ] Serveur d'embeddings répond au health check
- [ ] API FastAPI démarre sur port 8000
- [ ] Frontend React build et démarre sur port 3000
- [ ] Login admin fonctionne
- [ ] Upload d'un document fonctionne
- [ ] Création d'une conversation fonctionne
- [ ] Envoi d'un message et réponse RAG fonctionne

**Si tous les éléments sont cochés, votre installation est complète ! 🎉**

---

## 📞 Support

En cas de problème :
1. Vérifiez les logs : `docker-compose logs <service>`
2. Vérifiez que tous les services sont "healthy" : `docker-compose ps`
3. Consultez les issues GitHub si le projet est partagé

Bonne utilisation de RAGFab ! 🚀
