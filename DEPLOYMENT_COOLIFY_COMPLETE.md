# Guide Complet de Déploiement RAGFab sur Coolify

## 📋 Table des Matières

1. [Vue d'Ensemble](#vue-densemble)
2. [Prérequis](#prérequis)
3. [Préparation](#préparation)
4. [Configuration Coolify](#configuration-coolify)
5. [Déploiement](#déploiement)
6. [Vérification](#vérification)
7. [Troubleshooting](#troubleshooting)
8. [Maintenance](#maintenance)

---

## Vue d'Ensemble

### Architecture Complète

```
┌─────────────────────────────────────────────────────────────────┐
│                    SERVEUR COOLIFY                              │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐   │
│  │ PostgreSQL   │  │ Embeddings   │  │ Reranker (opt.)    │   │
│  │ + PGVector   │  │ E5-Large     │  │ BGE-M3             │   │
│  │ Port: 5432   │  │ Port: 8001   │  │ Port: 8002         │   │
│  └──────┬───────┘  └──────┬───────┘  └────────┬───────────┘   │
│         │                 │                    │               │
│         └─────────────────┼────────────────────┤               │
│                           │                    │               │
│              ┌────────────▼──────┐  ┌──────────▼────────────┐ │
│              │ Web API (FastAPI) │  │ Ingestion Worker     │ │
│              │ Port: 8000        │◄─┤ - Docling parsing    │ │
│              │ Public: HTTPS     │  │ - Chunk + embed      │ │
│              └──────────┬────────┘  │ - VLM analysis (opt.)│ │
│                         │           └──────────────────────┘ │
│              ┌──────────▼────────┐      Shared Volume:       │
│              │ Frontend (React)  │      /app/uploads         │
│              │ Port: 5173        │                           │
│              │ Public: HTTPS     │                           │
│              └───────────────────┘                           │
└─────────────────────────────────────────────────────────────────┘
```

### Services Déployés

| Service | Rôle | Port | Exposition |
|---------|------|------|------------|
| **ragfab-postgres** | Base de données + PGVector | 5432 | Interne |
| **ragfab-embeddings** | Génération d'embeddings | 8001 | Interne |
| **ragfab-reranker** | Reranking des résultats | 8002 | Interne (optionnel) |
| **ragfab-api** | API REST FastAPI | 8000 | Public (HTTPS) |
| **ingestion-worker** | Worker d'ingestion async | - | Interne |
| **ragfab-frontend** | Interface React | 5173 | Public (HTTPS) |

---

## Prérequis

### 1. Infrastructure

✅ **Serveur Coolify**
- Coolify v4+ installé et fonctionnel
- Traefik configuré avec Let's Encrypt
- Accès SSH au serveur

✅ **Ressources Minimales**
- **CPU** : 8 cores (16 cores recommandé)
- **RAM** : 16 GB minimum (32 GB recommandé)
- **Disque** : 100 GB minimum (SSD recommandé)
- **GPU** : Optionnel (améliore les performances embeddings)

✅ **Réseau**
- IP publique fixe
- Ports 80/443 ouverts (gérés par Traefik)
- Accès DNS pour configurer les domaines

### 2. Comptes et Clés API

✅ **Mistral API**
- Compte sur [console.mistral.ai](https://console.mistral.ai)
- Clé API générée
- Budget configuré (recommandé : au moins 10€/mois)

✅ **VLM API** (optionnel)
- Service VLM compatible OpenAI (vLLM, Ollama, ou cloud)
- URL d'endpoint et clé API si nécessaire

✅ **DNS**
- Accès au registrar de domaine
- Capacité à créer des enregistrements A/CNAME

### 3. Repository Git

✅ **Code Source**
- Repository Git accessible (GitHub/GitLab/Gitea)
- Branche `main` ou `master` prête pour production
- `.env.example` à jour avec toutes les variables

---

## Préparation

### Étape 1 : Vérifier le Code Local

```bash
# Aller dans le répertoire du projet
cd /Users/famatulli/Documents/rag/ragfab

# Vérifier l'état Git
git status

# S'assurer que tout est commité
git add .
git commit -m "Prepare for Coolify deployment"
```

### Étape 2 : Vérifier docker-compose.yml

**Important** : Les noms de conteneurs doivent être uniques avec le préfixe `ragfab-` :

```bash
# Vérifier les noms de conteneurs
grep "container_name:" docker-compose.yml
```

**Attendu** :
```yaml
container_name: ragfab-postgres
container_name: ragfab-embeddings
container_name: ragfab-reranker
container_name: ragfab-api
container_name: ingestion-worker
container_name: ragfab-frontend
```

### Étape 3 : Créer docker-compose.coolify.yml

Coolify nécessite quelques ajustements. Créer un fichier spécifique :

```bash
# Copier le docker-compose.yml
cp docker-compose.yml docker-compose.coolify.yml
```

**Modifications dans docker-compose.coolify.yml** :

```yaml
# 1. Utiliser .internal pour les connexions inter-services
environment:
  POSTGRES_HOST: ragfab-postgres.internal  # Au lieu de ragfab-postgres
  EMBEDDINGS_API_URL: http://ragfab-embeddings.internal:8001
  RERANKER_API_URL: http://ragfab-reranker.internal:8002

# 2. Ajouter les labels Traefik pour l'API
ragfab-api:
  labels:
    - "traefik.enable=true"
    - "traefik.http.routers.ragfab-api.rule=Host(`${API_DOMAIN}`)"
    - "traefik.http.routers.ragfab-api.entrypoints=websecure"
    - "traefik.http.routers.ragfab-api.tls.certresolver=letsencrypt"
    - "traefik.http.services.ragfab-api.loadbalancer.server.port=8000"

# 3. Ajouter les labels Traefik pour le Frontend
ragfab-frontend:
  labels:
    - "traefik.enable=true"
    - "traefik.http.routers.ragfab-frontend.rule=Host(`${FRONTEND_DOMAIN}`)"
    - "traefik.http.routers.ragfab-frontend.entrypoints=websecure"
    - "traefik.http.routers.ragfab-frontend.tls.certresolver=letsencrypt"
    - "traefik.http.services.ragfab-frontend.loadbalancer.server.port=5173"
```

### Étape 4 : Pousser sur Git

```bash
# Ajouter le fichier Coolify
git add docker-compose.coolify.yml

# Commit
git commit -m "Add Coolify-specific docker-compose configuration

- Use .internal suffix for inter-service communication
- Add Traefik labels for public services
- Configure SSL/HTTPS with Let's Encrypt

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"

# Pousser
git push origin main
```

### Étape 5 : Préparer les Variables d'Environnement

Créer un fichier local `.env.coolify` pour référence :

```bash
# Copier l'exemple
cp .env.example .env.coolify

# Éditer avec vos vraies valeurs
nano .env.coolify
```

**Contenu minimal de .env.coolify** :

```bash
# ==========================================
# DOMAINES (À REMPLACER)
# ==========================================
FRONTEND_DOMAIN=ragfab.votre-domaine.com
API_DOMAIN=api.ragfab.votre-domaine.com

# ==========================================
# BASE DE DONNÉES
# ==========================================
POSTGRES_USER=raguser
POSTGRES_PASSWORD=GENERER_MOT_DE_PASSE_FORT_ICI
POSTGRES_DB=ragdb
POSTGRES_HOST=ragfab-postgres.internal
POSTGRES_PORT=5432
DATABASE_URL=postgresql://raguser:VOTRE_MOT_DE_PASSE@ragfab-postgres.internal:5432/ragdb

# ==========================================
# SERVICES INTERNES
# ==========================================
EMBEDDINGS_API_URL=http://ragfab-embeddings.internal:8001
EMBEDDING_DIMENSION=1024

RERANKER_ENABLED=true
RERANKER_API_URL=http://ragfab-reranker.internal:8002
RERANKER_MODEL=BAAI/bge-reranker-v2-m3
RERANKER_TOP_K=20
RERANKER_RETURN_K=5

# ==========================================
# SÉCURITÉ (GÉNÉRER DES VALEURS FORTES)
# ==========================================
SECRET_KEY=GENERER_CLE_SECRETE_64_CHARS_ICI
ADMIN_USERNAME=admin
ADMIN_PASSWORD=GENERER_MOT_DE_PASSE_ADMIN_ICI

# ==========================================
# MISTRAL API
# ==========================================
MISTRAL_API_KEY=votre_cle_mistral_ici
MISTRAL_MODEL_NAME=mistral-small-latest
MISTRAL_TIMEOUT=120.0

# ==========================================
# CHOCOLATINE (OPTIONNEL)
# ==========================================
CHOCOLATINE_API_URL=https://apigpt.mynumih.fr
CHOCOLATINE_API_KEY=
CHOCOLATINE_MODEL_NAME=jpacifico/Chocolatine-14B-Instruct

# ==========================================
# PROVIDER PAR DÉFAUT
# ==========================================
RAG_PROVIDER=mistral

# ==========================================
# CORS (AJUSTER SELON VOS DOMAINES)
# ==========================================
ALLOWED_ORIGINS=https://ragfab.votre-domaine.com,https://www.ragfab.votre-domaine.com

# ==========================================
# VLM (OPTIONNEL - EXTRACTION D'IMAGES)
# ==========================================
VLM_ENABLED=false
VLM_API_URL=
VLM_API_KEY=
VLM_MODEL_NAME=ibm-granite/SmolDocling-256M-Instruct
VLM_TIMEOUT=120.0

# ==========================================
# STOCKAGE
# ==========================================
UPLOAD_DIR=/app/uploads
IMAGE_STORAGE_PATH=/app/uploads/images
```

**Ne pas commiter ce fichier !** Ajouter au `.gitignore` :

```bash
echo ".env.coolify" >> .gitignore
git add .gitignore
git commit -m "Add .env.coolify to gitignore"
git push
```

---

## Configuration Coolify

### Étape 1 : Créer le Projet

1. **Ouvrir Coolify** : Aller sur votre instance Coolify (ex: `https://coolify.votre-serveur.com`)
2. **Se connecter** avec vos identifiants admin
3. **Nouveau Projet** :
   - Cliquer sur **"+ New"** → **"Project"**
   - **Name** : `ragfab`
   - **Description** : "RAG System with Dual LLM Providers"
   - **Cliquer sur "Create"**

### Étape 2 : Ajouter la Resource Docker Compose

1. **Dans le projet** `ragfab`, cliquer sur **"+ Add New Resource"**
2. **Choisir** : **"Docker Compose"**
3. **Configuration** :
   - **Name** : `ragfab-stack`
   - **Description** : "Complete RAGFab stack with 6 services"

### Étape 3 : Connecter le Repository Git

1. **Git Source** :
   - **Repository URL** : `https://github.com/votre-user/ragfab.git` (ou votre URL Git)
   - **Branch** : `main`
   - **Docker Compose File** : `docker-compose.coolify.yml`

2. **Si repository privé** :
   - Coolify va générer une **Deploy Key**
   - Copier la clé publique affichée
   - Aller dans les **Settings** de votre repository Git
   - Ajouter la clé dans **Deploy Keys** avec accès en lecture seule

3. **Tester la connexion** :
   - Cliquer sur **"Test Connection"**
   - Attendu : ✅ Success

### Étape 4 : Configurer les Variables d'Environnement

**Important** : Coolify permet de définir les variables au niveau du projet OU du service. Pour RAGFab, on va utiliser **les deux niveaux**.

#### 4.1 Variables Globales (Niveau Projet)

Dans **Project Settings** → **Environment Variables** :

```bash
# Domaines
FRONTEND_DOMAIN=ragfab.votre-domaine.com
API_DOMAIN=api.ragfab.votre-domaine.com

# Secrets (marquer comme "Secret" dans Coolify)
SECRET_KEY=votre_cle_secrete_generee
POSTGRES_PASSWORD=votre_mot_de_passe_postgres
ADMIN_PASSWORD=votre_mot_de_passe_admin
MISTRAL_API_KEY=votre_cle_mistral

# Database globale
POSTGRES_USER=raguser
POSTGRES_DB=ragdb
```

#### 4.2 Générer les Secrets

**Sur votre machine locale** :

```bash
# SECRET_KEY (64 caractères)
python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(64))"

# POSTGRES_PASSWORD (32 caractères)
python3 -c "import secrets; print('POSTGRES_PASSWORD=' + secrets.token_urlsafe(32))"

# ADMIN_PASSWORD (24 caractères)
python3 -c "import secrets; print('ADMIN_PASSWORD=' + secrets.token_urlsafe(24))"
```

**Copier les valeurs** générées et les coller dans Coolify.

#### 4.3 Variables Spécifiques par Service

**Pour chaque service**, aller dans **Service Settings** → **Environment Variables** :

**ragfab-postgres** :
```bash
POSTGRES_USER=${POSTGRES_USER}  # Référence variable globale
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
POSTGRES_DB=${POSTGRES_DB}
```

**ragfab-embeddings** :
```bash
MODEL_NAME=intfloat/multilingual-e5-large
MAX_BATCH_SIZE=32
PORT=8001
```

**ragfab-reranker** (si activé) :
```bash
MODEL_NAME=BAAI/bge-reranker-v2-m3
MAX_BATCH_SIZE=16
PORT=8002
```

**ragfab-api** :
```bash
# Database
DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@ragfab-postgres.internal:5432/${POSTGRES_DB}
POSTGRES_HOST=ragfab-postgres.internal
POSTGRES_PORT=5432
POSTGRES_USER=${POSTGRES_USER}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
POSTGRES_DB=${POSTGRES_DB}

# Services
EMBEDDINGS_API_URL=http://ragfab-embeddings.internal:8001
EMBEDDING_DIMENSION=1024

RERANKER_ENABLED=true
RERANKER_API_URL=http://ragfab-reranker.internal:8002
RERANKER_MODEL=BAAI/bge-reranker-v2-m3
RERANKER_TOP_K=20
RERANKER_RETURN_K=5

# Security
SECRET_KEY=${SECRET_KEY}
ADMIN_USERNAME=admin
ADMIN_PASSWORD=${ADMIN_PASSWORD}

# LLM
MISTRAL_API_KEY=${MISTRAL_API_KEY}
MISTRAL_MODEL_NAME=mistral-small-latest
MISTRAL_TIMEOUT=120.0

CHOCOLATINE_API_URL=https://apigpt.mynumih.fr
CHOCOLATINE_API_KEY=
RAG_PROVIDER=mistral

# CORS
ALLOWED_ORIGINS=https://${FRONTEND_DOMAIN},https://www.${FRONTEND_DOMAIN}

# Storage
UPLOAD_DIR=/app/uploads
IMAGE_STORAGE_PATH=/app/uploads/images

# VLM (optionnel)
VLM_ENABLED=false
```

**ingestion-worker** :
```bash
# TOUTES les mêmes variables que ragfab-api
# (copier-coller de ragfab-api)
```

**ragfab-frontend** :
```bash
VITE_API_URL=https://${API_DOMAIN}
NODE_ENV=production
```

### Étape 5 : Configurer les Volumes

Coolify gère automatiquement les volumes, mais vérifier :

1. **ragfab-postgres** :
   - Volume : `postgres_data` → `/var/lib/postgresql/data`
   - Volume : `./database` → `/docker-entrypoint-initdb.d` (read-only)

2. **ragfab-api** :
   - Volume : `uploads_data` → `/app/uploads`

3. **ingestion-worker** :
   - Volume : `uploads_data` → `/app/uploads` (MÊME volume que l'API !)

**Important** : Le volume `uploads_data` **doit être partagé** entre `ragfab-api` et `ingestion-worker`.

### Étape 6 : Configurer les Domaines et SSL

Pour **ragfab-api** :
1. Aller dans **Service Settings** → **Domains**
2. **Add Domain** : `api.ragfab.votre-domaine.com`
3. **SSL** : Laisser Coolify gérer automatiquement avec Let's Encrypt
4. **Port** : `8000`

Pour **ragfab-frontend** :
1. Aller dans **Service Settings** → **Domains**
2. **Add Domain** : `ragfab.votre-domaine.com`
3. **SSL** : Laisser Coolify gérer automatiquement
4. **Port** : `5173`

### Étape 7 : Configurer le DNS

**Avant de déployer**, configurer le DNS chez votre registrar :

```
# Enregistrements A
ragfab.votre-domaine.com     A     IP_PUBLIQUE_SERVEUR_COOLIFY
api.ragfab.votre-domaine.com A     IP_PUBLIQUE_SERVEUR_COOLIFY

# Optionnel : www
www.ragfab.votre-domaine.com CNAME ragfab.votre-domaine.com
```

**Vérifier la propagation DNS** :

```bash
# Sur votre machine locale
dig ragfab.votre-domaine.com
dig api.ragfab.votre-domaine.com

# Attendu : IP publique du serveur Coolify
```

---

## Déploiement

### Étape 1 : Lancer le Déploiement

1. **Dans Coolify**, aller sur votre resource `ragfab-stack`
2. **Cliquer sur le bouton bleu "Deploy"** en haut à droite
3. **Surveiller les logs** en temps réel

### Étape 2 : Ordre de Démarrage

Coolify va démarrer les services dans cet ordre (grâce aux `depends_on`) :

```
1. ragfab-postgres      ⏱️  ~30 secondes
2. ragfab-embeddings    ⏱️  ~2-3 minutes (télécharge le modèle)
3. ragfab-reranker      ⏱️  ~1-2 minutes (télécharge le modèle)
4. ragfab-api           ⏱️  ~5-10 minutes (installe docling la première fois)
5. ingestion-worker     ⏱️  ~1-2 minutes
6. ragfab-frontend      ⏱️  ~30 secondes
```

**Temps total estimé** : 10-20 minutes pour le premier déploiement.

### Étape 3 : Surveiller les Logs

**Pour chaque service**, cliquer sur le nom dans Coolify pour voir les logs :

**ragfab-postgres** - Attendu :
```
PostgreSQL Database directory appears to contain a database; Skipping initialization
database system is ready to accept connections
```

**ragfab-embeddings** - Attendu :
```
Downloading model intfloat/multilingual-e5-large...
Model loaded successfully
Application startup complete
Uvicorn running on http://0.0.0.0:8001
```

**ragfab-reranker** - Attendu :
```
Loading model BAAI/bge-reranker-v2-m3...
Model ready
Application startup complete
```

**ragfab-api** - Attendu :
```
✅ Connexion à la base de données établie
🔄 Initialisation de la base de données...
✅ Toutes les tables existent
👤 Utilisateur admin créé avec succès
Application startup complete
```

**ingestion-worker** - Attendu :
```
🔄 Worker d'ingestion démarré
📊 Polling ingestion jobs every 3s...
```

**ragfab-frontend** - Attendu :
```
> ragfab-frontend@0.1.0 preview
VITE v5.0.0 ready in 500 ms
```

---

## Vérification

### Étape 1 : Vérifier les Services

**Via SSH sur le serveur Coolify** :

```bash
# SSH
ssh user@votre-serveur-coolify

# Vérifier que tous les conteneurs sont UP
docker ps | grep ragfab

# Attendu : 6 conteneurs avec status "Up"
# ragfab-postgres      Up 5 minutes
# ragfab-embeddings    Up 4 minutes
# ragfab-reranker      Up 3 minutes
# ragfab-api           Up 2 minutes
# ingestion-worker     Up 2 minutes
# ragfab-frontend      Up 1 minute
```

### Étape 2 : Tester les Endpoints Internes

**Depuis un conteneur (ex: ragfab-api)** :

```bash
# PostgreSQL
docker exec ragfab-api psql postgresql://raguser:password@ragfab-postgres.internal:5432/ragdb -c "SELECT version();"

# Embeddings
docker exec ragfab-api curl -f http://ragfab-embeddings.internal:8001/health

# Reranker
docker exec ragfab-api curl -f http://ragfab-reranker.internal:8002/health
```

### Étape 3 : Tester les Endpoints Publics

**Depuis votre machine locale** :

```bash
# API Health
curl https://api.ragfab.votre-domaine.com/health
# Attendu: {"status":"ok"}

# Frontend
curl https://ragfab.votre-domaine.com
# Attendu: HTML de la page React
```

### Étape 4 : Vérifier la Base de Données

```bash
# SSH dans le serveur
ssh user@votre-serveur-coolify

# Lister les tables
docker exec ragfab-postgres psql -U raguser -d ragdb -c "\dt"

# Attendu:
#  public | chunks               | table
#  public | conversations        | table
#  public | document_images      | table
#  public | documents            | table
#  public | ingestion_jobs       | table
#  public | messages             | table
#  public | users                | table
```

### Étape 5 : Tester l'Interface Web

1. **Ouvrir le navigateur** : `https://ragfab.votre-domaine.com`
2. **Se connecter** : `admin` / votre mot de passe admin
3. **Vérifier** :
   - ✅ Page de chat s'affiche
   - ✅ Sélecteur de provider (Mistral/Chocolatine)
   - ✅ Menu latéral avec conversations

### Étape 6 : Tester une Conversation

1. **Créer une nouvelle conversation**
2. **Poser une question** : "Bonjour, peux-tu m'expliquer comment tu fonctionnes ?"
3. **Vérifier** :
   - ✅ Réponse générée (Mistral API)
   - ✅ Pas de sources (pas de documents encore)
   - ✅ Message sauvegardé dans l'historique

### Étape 7 : Tester l'Upload de Document

1. **Aller dans Admin** : `https://ragfab.votre-domaine.com/admin`
2. **Se connecter** avec `admin` / mot de passe
3. **Upload un PDF** : Glisser-déposer un document de test
4. **Surveiller les logs** :
   ```bash
   docker logs -f ingestion-worker
   ```
5. **Vérifier la progression** : Barre de progression 0% → 100%
6. **Vérifier dans la BD** :
   ```bash
   docker exec ragfab-postgres psql -U raguser -d ragdb -c "SELECT title, COUNT(c.id) as chunks FROM documents d LEFT JOIN chunks c ON d.id = c.document_id GROUP BY d.id, title;"
   ```

### Étape 8 : Tester le RAG

1. **Retourner au chat**
2. **Poser une question** sur le document uploadé
3. **Vérifier** :
   - ✅ Réponse pertinente
   - ✅ Sources affichées
   - ✅ Chunks pertinents listés
   - ✅ Score de similarité affiché

---

## Troubleshooting

### Problème 1 : Service ne démarre pas

**Symptômes** :
- Conteneur en status "Restarting" ou "Exited"
- Logs montrent des erreurs répétées

**Solution** :

```bash
# 1. Vérifier les logs du service
docker logs ragfab-api --tail 100

# 2. Chercher les erreurs
docker logs ragfab-api 2>&1 | grep -i error

# 3. Vérifier les variables d'environnement
docker exec ragfab-api env | grep DATABASE_URL

# 4. Tester la connectivité inter-services
docker exec ragfab-api ping ragfab-postgres.internal
```

**Causes fréquentes** :
- ❌ Variable d'environnement manquante
- ❌ Mauvais mot de passe PostgreSQL
- ❌ Service dépendant pas encore démarré
- ❌ Réseau Docker mal configuré

### Problème 2 : Erreur de connexion PostgreSQL

**Symptômes** :
- `connection refused` ou `password authentication failed`
- API ne démarre pas

**Solution** :

```bash
# 1. Vérifier que PostgreSQL est UP
docker ps | grep postgres

# 2. Tester la connexion manuellement
docker exec ragfab-api psql postgresql://raguser:VOTRE_PASSWORD@ragfab-postgres.internal:5432/ragdb -c "SELECT 1;"

# 3. Vérifier les logs PostgreSQL
docker logs ragfab-postgres | grep -i error

# 4. Vérifier que le réseau interne est créé
docker network inspect ragfab_default
```

**Causes fréquentes** :
- ❌ `POSTGRES_PASSWORD` différent entre `.env` et PostgreSQL
- ❌ Utilisation de `ragfab-postgres` au lieu de `ragfab-postgres.internal`
- ❌ PostgreSQL pas complètement démarré (attendre 30-60s)

### Problème 3 : Embeddings timeout

**Symptômes** :
- Upload de document échoue
- Erreur `connection timeout` ou `504 Gateway Timeout`

**Solution** :

```bash
# 1. Vérifier que le service est UP
docker exec ragfab-embeddings curl localhost:8001/health

# 2. Tester l'embedding d'un texte
docker exec ragfab-api curl -X POST http://ragfab-embeddings.internal:8001/embed \
  -H "Content-Type: application/json" \
  -d '{"text": "test"}' \
  --max-time 60

# 3. Vérifier les ressources
docker stats ragfab-embeddings --no-stream

# 4. Si le service est lent, augmenter les ressources dans Coolify
```

**Causes fréquentes** :
- ❌ Modèle pas encore téléchargé (première requête peut prendre 2-3 minutes)
- ❌ RAM insuffisante (minimum 4 GB recommandé)
- ❌ CPU surchargé

### Problème 4 : Frontend ne charge pas

**Symptômes** :
- Page blanche
- Erreur CORS dans la console
- 502 Bad Gateway

**Solution** :

```bash
# 1. Vérifier que le frontend est UP
docker ps | grep frontend

# 2. Vérifier les logs
docker logs ragfab-frontend

# 3. Tester l'accès direct au conteneur
docker exec ragfab-frontend curl localhost:5173

# 4. Vérifier VITE_API_URL
docker exec ragfab-frontend env | grep VITE_API_URL

# 5. Vérifier CORS dans l'API
docker exec ragfab-api env | grep ALLOWED_ORIGINS
```

**Causes fréquentes** :
- ❌ `VITE_API_URL` pointe vers la mauvaise URL
- ❌ Domaine frontend pas dans `ALLOWED_ORIGINS`
- ❌ Certificat SSL pas encore généré (attendre 1-2 minutes)

### Problème 5 : SSL/HTTPS ne fonctionne pas

**Symptômes** :
- `NET::ERR_CERT_AUTHORITY_INVALID`
- `This site can't provide a secure connection`

**Solution** :

```bash
# 1. Vérifier la configuration DNS
dig ragfab.votre-domaine.com
# Doit pointer vers l'IP du serveur Coolify

# 2. Vérifier les logs Traefik dans Coolify
# Aller dans Coolify → Settings → Logs → Traefik

# 3. Vérifier les certificats
docker exec coolify-proxy ls -la /letsencrypt/

# 4. Forcer la régénération du certificat
# Dans Coolify : Service Settings → Domains → Regenerate Certificate
```

**Causes fréquentes** :
- ❌ DNS pas encore propagé (attendre 5-60 minutes)
- ❌ Port 80/443 pas ouvert dans le firewall
- ❌ Let's Encrypt rate limit atteint (5 certificats par domaine par semaine)

### Problème 6 : Ingestion worker ne traite pas les jobs

**Symptômes** :
- Jobs restent en "pending"
- Barre de progression à 0%
- Worker ne log rien

**Solution** :

```bash
# 1. Vérifier que le worker est UP
docker ps | grep ingestion-worker

# 2. Vérifier les logs
docker logs ingestion-worker -f

# 3. Vérifier les jobs en attente
docker exec ragfab-postgres psql -U raguser -d ragdb -c "SELECT id, filename, status, progress, error_message FROM ingestion_jobs ORDER BY created_at DESC LIMIT 5;"

# 4. Vérifier que le volume est partagé
docker exec ragfab-api ls -la /app/uploads
docker exec ingestion-worker ls -la /app/uploads
# Les deux doivent montrer les mêmes fichiers
```

**Causes fréquentes** :
- ❌ Volume `uploads_data` pas partagé entre API et worker
- ❌ Worker ne peut pas se connecter à PostgreSQL
- ❌ Worker ne peut pas se connecter au service embeddings

### Problème 7 : Reranker ne fonctionne pas

**Symptômes** :
- Recherche RAG fonctionne mais sans amélioration
- Logs montrent "Reranker fallback"

**Solution** :

```bash
# 1. Vérifier que le service est UP
docker ps | grep reranker

# 2. Tester le service
docker exec ragfab-api curl http://ragfab-reranker.internal:8002/health

# 3. Si vous ne voulez pas utiliser le reranker
# Dans Coolify, mettre RERANKER_ENABLED=false dans ragfab-api

# 4. Vérifier les ressources
docker stats ragfab-reranker --no-stream
```

---

## Maintenance

### Mise à Jour du Code

**Workflow** :

```bash
# 1. Sur votre machine locale
git pull origin main
# Faire vos modifications...
git add .
git commit -m "Update feature X"
git push origin main

# 2. Dans Coolify
# Aller sur votre resource ragfab-stack
# Cliquer sur "Redeploy"
# Coolify va automatiquement :
# - Pull la nouvelle version du code
# - Rebuild les images modifiées
# - Redémarrer les services avec rolling update (zéro downtime)
```

### Backup de la Base de Données

**Manuel** :

```bash
# Backup complet
docker exec ragfab-postgres pg_dump -U raguser ragdb > backup_$(date +%Y%m%d_%H%M%S).sql

# Backup gzippé
docker exec ragfab-postgres pg_dump -U raguser ragdb | gzip > backup_$(date +%Y%m%d_%H%M%S).sql.gz

# Restore
gunzip -c backup_20250108_143000.sql.gz | docker exec -i ragfab-postgres psql -U raguser -d ragdb
```

**Automatique dans Coolify** :

1. **Aller dans** : Project Settings → Backups
2. **New Backup** :
   - **Source** : Volume `postgres_data`
   - **Destination** : S3/Backblaze/Local
   - **Schedule** : `0 2 * * *` (tous les jours à 2h du matin)
   - **Retention** : 7 jours
3. **Save**

### Monitoring des Ressources

```bash
# Utilisation CPU/RAM/Disque en temps réel
docker stats

# Espace disque
df -h

# Logs de tous les services
docker-compose logs -f

# Logs d'un service spécifique
docker logs ragfab-api -f --tail 100
```

### Nettoyage Périodique

```bash
# Nettoyer les images Docker inutilisées
docker image prune -a

# Nettoyer les conteneurs arrêtés
docker container prune

# Nettoyer les volumes orphelins (ATTENTION: Peut supprimer des données!)
docker volume prune  # À FAIRE AVEC PRÉCAUTION

# Archiver les vieilles conversations (>90 jours)
docker exec ragfab-postgres psql -U raguser -d ragdb -c "UPDATE conversations SET is_archived = true WHERE updated_at < NOW() - INTERVAL '90 days';"
```

### Optimisation des Performances

**Si les embeddings sont lents** :

```bash
# Dans Coolify, augmenter les ressources de ragfab-embeddings
Memory: 8-12 GB
CPU: 4 cores
```

**Si la base de données est lente** :

```bash
# Analyser les requêtes lentes
docker exec ragfab-postgres psql -U raguser -d ragdb -c "SELECT query, mean_exec_time FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;"

# Réindexer si nécessaire
docker exec ragfab-postgres psql -U raguser -d ragdb -c "REINDEX DATABASE ragdb;"
```

### Surveillance des Logs

**Erreurs critiques** :

```bash
# Chercher les erreurs dans tous les services
for service in ragfab-postgres ragfab-embeddings ragfab-reranker ragfab-api ingestion-worker ragfab-frontend; do
  echo "=== $service ==="
  docker logs $service 2>&1 | grep -i error | tail -5
done
```

**Performance** :

```bash
# Requêtes lentes
docker logs ragfab-api | grep -i "slow\|timeout"

# Utilisation mémoire
docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}"
```

---

## Checklist Finale

### Avant le Déploiement

- [ ] Code poussé sur Git (branche `main`)
- [ ] `docker-compose.coolify.yml` créé avec labels Traefik
- [ ] `.env.coolify` préparé avec toutes les variables
- [ ] Secrets générés (SECRET_KEY, POSTGRES_PASSWORD, ADMIN_PASSWORD)
- [ ] Clé API Mistral obtenue
- [ ] DNS configuré (enregistrements A pour `ragfab.votre-domaine.com` et `api.ragfab.votre-domaine.com`)

### Pendant le Déploiement

- [ ] Projet créé dans Coolify
- [ ] Repository Git connecté
- [ ] Variables d'environnement configurées (globales + par service)
- [ ] Domaines configurés avec SSL automatique
- [ ] Volume `uploads_data` partagé entre API et worker
- [ ] Déploiement lancé avec succès

### Après le Déploiement

- [ ] Tous les conteneurs en status "Up" (6 services)
- [ ] Endpoints internes fonctionnels (postgres, embeddings, reranker)
- [ ] Endpoints publics fonctionnels (HTTPS sur API et frontend)
- [ ] SSL/HTTPS actif sur les deux domaines (certificats Let's Encrypt)
- [ ] Tables de base de données créées automatiquement
- [ ] Utilisateur admin créé (`admin` / mot de passe configuré)
- [ ] Interface web accessible et fonctionnelle
- [ ] Conversation de test réussie (Mistral API)
- [ ] Upload de document de test réussi
- [ ] Ingestion worker traite les jobs correctement
- [ ] RAG fonctionnel (question → sources → réponse pertinente)
- [ ] Backup automatique configuré
- [ ] Monitoring activé dans Coolify

**Statut** : ✅ Production Ready si tous les items sont cochés

---

## Support et Documentation

### Documentation Projet

- **CLAUDE.md** : Architecture complète et détails techniques
- **VLM_TESTING_GUIDE.md** : Guide pour activer l'extraction d'images avec VLM
- **README.md** : Vue d'ensemble du projet

### Ressources Externes

- **Coolify** : [docs.coolify.io](https://docs.coolify.io)
- **Docker** : [docs.docker.com](https://docs.docker.com)
- **Traefik** : [doc.traefik.io](https://doc.traefik.io)
- **Mistral API** : [docs.mistral.ai](https://docs.mistral.ai)

### Commandes de Diagnostic

```bash
# État complet du système
docker ps -a
docker volume ls
docker network ls
docker stats --no-stream

# Logs de tous les services
docker-compose logs --tail 50

# Santé de la base de données
docker exec ragfab-postgres pg_isready -U raguser

# Test de connectivité
docker exec ragfab-api ping ragfab-postgres.internal
docker exec ragfab-api curl http://ragfab-embeddings.internal:8001/health
```

---

**Version** : RAGFab avec VLM Image Extraction
**Date** : 2025-01-08
**Auteur** : Guide de déploiement Coolify complet
**Prêt pour Production** : ✅ Oui (suivre la checklist)
