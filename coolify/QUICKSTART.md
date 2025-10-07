# ⚡ Guide de Démarrage Rapide - RAGFab sur Coolify

Guide condensé pour déployer RAGFab en 15 minutes.

---

## 📋 Avant de Commencer

**Ce dont vous avez besoin:**

1. Un serveur Coolify fonctionnel avec Caddy comme reverse proxy
2. 1 domaine configuré pour le frontend:
   - `ragbot.lab-numihfrance.fr` (frontend - seul service public)
   - Backend, Embeddings et PostgreSQL restent privés sur réseau Docker

3. Une clé API Mistral: https://console.mistral.ai/

**Architecture:**
- Frontend (Nginx) → Exposé publiquement via Caddy avec HTTPS
- Backend (FastAPI) → Privé, accessible uniquement via frontend Nginx
- Embeddings → Privé, accessible uniquement via backend
- PostgreSQL → Privé, accessible uniquement via backend

---

## 🚀 Déploiement en 4 Étapes

### Étape 1: PostgreSQL (Base de données)

**1.1 - Créer le service dans Coolify**
- Type: Docker Compose
- Path: `coolify/4-postgres/docker-compose.yml`

**1.2 - Variables d'environnement**
```bash
POSTGRES_USER=raguser
POSTGRES_PASSWORD=ChangeMe123!  # ⚠️ Utilisez un mot de passe fort!
POSTGRES_DB=ragdb
```

**1.3 - Réseau**
- ⚠️ **IMPORTANT:** NE PAS exposer le port 5432 publiquement
- Utiliser le réseau privé Coolify uniquement

**1.4 - Déployer**

---

### Étape 2: Embeddings (Service d'embeddings)

**2.1 - Créer le service dans Coolify**
- Type: Docker Compose
- Path: `coolify/3-embeddings/docker-compose.yml`

**2.2 - Variables d'environnement**
```bash
MODEL_NAME=intfloat/multilingual-e5-large
LOG_LEVEL=INFO
```

**2.3 - Réseau**
- **Option A (recommandé):** Réseau privé (pas de domaine public)
- **Option B:** Domaine: `embeddings-ragfab.yourdomain.com` + SSL

**2.4 - Ressources**
- RAM: 4-8 GB
- CPU: 2-4 cores

**2.5 - Déployer**

---

### Étape 3: Backend API

**3.1 - Créer le service dans Coolify**
- Type: Docker Compose
- Path: `coolify/2-backend/docker-compose.yml`

**3.2 - Variables d'environnement**

**Connexions:**
```bash
# Base de données (réseau privé Coolify)
DATABASE_URL=postgresql://raguser:ChangeMe123!@ragfab-postgres:5432/ragdb

# Embeddings (réseau privé)
EMBEDDINGS_API_URL=http://ragfab-embeddings:8001
EMBEDDING_DIMENSION=1024
```

**Sécurité:**
```bash
# Générer avec: openssl rand -hex 32
JWT_SECRET=a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6

# Admin credentials
ADMIN_USERNAME=admin
ADMIN_PASSWORD=VotreMotDePasseAdmin123!
```

**Mistral API:**
```bash
MISTRAL_API_KEY=votre_cle_api_mistral_ici
MISTRAL_API_URL=https://api.mistral.ai
MISTRAL_MODEL_NAME=mistral-small-latest
```

**CORS:**
```bash
CORS_ORIGINS=https://ragbot.lab-numihfrance.fr
```

**3.3 - Configuration Coolify**
- ⚠️ **PAS de domaine public** (backend privé pour sécurité)
- Réseau: `coolify` (réseau Docker partagé)
- Le container DOIT avoir le nom: `ragfab-backend` (pour que Nginx le trouve)

**3.4 - Déployer**

---

### Étape 4: Frontend

**4.1 - Créer le service dans Coolify**
- Type: Docker Compose
- Path: `coolify/1-frontend/docker-compose.yml`

**4.2 - Variables d'environnement**
```bash
# Note: Cette variable n'est plus utilisée, le frontend appelle /api/ en relatif
# Nginx fait le proxy vers ragfab-backend:8000 automatiquement
BACKEND_API_URL=https://ragbot.lab-numihfrance.fr
```

**4.3 - Configuration Coolify**
- Domaine: `ragbot.lab-numihfrance.fr`
- Port interne: 80 (Nginx)
- SSL: Géré automatiquement par Caddy
- Réseau: `coolify` (réseau Docker partagé)

**4.4 - Déployer**

**IMPORTANT:** Après déploiement, vérifiez dans l'interface Coolify:
- Section "Domains" → Le domaine `ragbot.lab-numihfrance.fr` doit être configuré
- "Enable HTTPS" doit être activé
- Caddy génère automatiquement le certificat Let's Encrypt

---

## ✅ Vérification

### 1. Health Checks

```bash
# Frontend (public)
curl https://ragbot.lab-numihfrance.fr/health
# Attendu: "healthy"

# Backend (via frontend proxy)
curl https://ragbot.lab-numihfrance.fr/api/health
# Attendu: {"status":"healthy"}

# Backend (direct depuis le serveur, pas accessible depuis Internet)
docker exec <backend-container-id> curl http://localhost:8000/health

# Embeddings (privé, depuis le serveur uniquement)
docker exec <embeddings-container-id> curl http://localhost:8001/health

# PostgreSQL (privé)
docker exec <postgres-container-id> pg_isready -U raguser -d ragdb
```

### 2. Test d'authentification

```bash
curl -X POST https://ragbot.lab-numihfrance.fr/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "VotreMotDePasseAdmin123!"
  }'

# Attendu: {"access_token":"...", "token_type":"bearer"}
```

### 3. Interface Web

Ouvrir dans un navigateur: `https://ragbot.lab-numihfrance.fr`

Vous devriez voir l'interface RAGFab avec certificat SSL valide.

---

## 📤 Premier Upload de Document

### Via l'interface web

1. Se connecter sur `https://ragfab.yourdomain.com`
2. Login: `admin` / votre mot de passe admin
3. Aller dans "Documents"
4. Cliquer sur "Upload"
5. Sélectionner un PDF
6. Attendre la fin de l'ingestion (~2-3 minutes pour un PDF de 1MB)

### Via l'API

```bash
# 1. Se connecter et récupérer le token
TOKEN=$(curl -s -X POST https://api-ragfab.yourdomain.com/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"VotreMotDePasseAdmin123!"}' \
  | jq -r '.access_token')

# 2. Uploader un document
curl -X POST https://api-ragfab.yourdomain.com/api/documents/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@votre_document.pdf"
```

---

## 💬 Première Conversation

### Via l'interface web

1. Aller dans "Chat"
2. Poser une question: "Qu'est-ce que ce document explique ?"
3. Le système va:
   - Chercher dans la base vectorielle
   - Trouver les passages pertinents
   - Générer une réponse avec citations

### Via l'API

```bash
curl -X POST https://api-ragfab.yourdomain.com/api/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Qu'est-ce que ce document explique ?",
    "conversation_id": null
  }'
```

---

## 🔧 Configuration Réseau Privé (Recommandé)

Si Coolify supporte les réseaux privés Docker, utilisez cette configuration plus sécurisée:

### Frontend
```bash
# Communique avec le backend via HTTP privé
BACKEND_API_URL=http://ragfab-backend:8000
```

### Backend
```bash
# Communique avec embeddings et postgres via HTTP privé
EMBEDDINGS_API_URL=http://ragfab-embeddings:8001
DATABASE_URL=postgresql://raguser:password@ragfab-postgres:5432/ragdb
```

**Avantages:**
- Plus sécurisé (services internes non accessibles depuis Internet)
- Pas de certificats SSL à gérer pour les services internes
- Moins de latence

**Exposition publique:**
- ✅ Frontend: `https://ragfab.yourdomain.com` (HTTPS)
- ❌ Backend: Privé (HTTP interne)
- ❌ Embeddings: Privé (HTTP interne)
- ❌ PostgreSQL: Privé (TCP interne)

---

## 🐛 Dépannage Rapide

### Erreur: "Cannot connect to database"

**Solution:**
```bash
# Vérifier que PostgreSQL est démarré
docker ps | grep ragfab-postgres

# Vérifier les logs
docker logs ragfab-postgres

# Tester la connexion depuis le backend
docker exec ragfab-backend nc -zv ragfab-postgres 5432
```

### Erreur: "CORS error" dans le navigateur

**Solution:**
```bash
# Vérifier que CORS_ORIGINS contient votre domaine frontend
# Dans les variables d'environnement du backend:
CORS_ORIGINS=https://ragfab.yourdomain.com
```

### Erreur: "502 Bad Gateway"

**Solution:**
```bash
# Vérifier que le service concerné est démarré
docker ps

# Vérifier les health checks
docker inspect ragfab-backend | grep Health

# Redémarrer le service
docker restart ragfab-backend
```

### Erreur: Embeddings très lents

**Solution:**
```bash
# Augmenter la RAM allouée dans Coolify (8GB recommandé)
# Vérifier l'utilisation mémoire
docker stats ragfab-embeddings
```

---

## 📊 Monitoring Basique

### Script de monitoring

Créer un fichier `monitor.sh`:

```bash
#!/bin/bash

echo "=== RAGFab Status ==="
echo ""

# Frontend
echo -n "Frontend: "
curl -s https://ragfab.yourdomain.com/health && echo "✅ OK" || echo "❌ ERROR"

# Backend
echo -n "Backend: "
curl -s https://api-ragfab.yourdomain.com/health && echo "✅ OK" || echo "❌ ERROR"

# PostgreSQL (depuis le serveur)
echo -n "PostgreSQL: "
docker exec ragfab-postgres pg_isready -U raguser && echo "✅ OK" || echo "❌ ERROR"

# Embeddings (depuis le serveur)
echo -n "Embeddings: "
docker exec ragfab-embeddings curl -sf http://localhost:8001/health && echo "✅ OK" || echo "❌ ERROR"

echo ""
echo "=== Docker Stats ==="
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}" \
  ragfab-frontend ragfab-backend ragfab-embeddings ragfab-postgres
```

**Exécuter:**
```bash
chmod +x monitor.sh
./monitor.sh
```

---

## 📚 Prochaines Étapes

1. **Sécurité:** Lire [SECURITY.md](./SECURITY.md)
2. **Configuration avancée:** Lire [README.md](./README.md)
3. **Backup:** Mettre en place les backups PostgreSQL automatiques
4. **Monitoring:** Configurer des alertes (Uptime Kuma, etc.)

---

## 🎉 C'est Tout !

Votre système RAGFab est maintenant opérationnel sur Coolify.

**URLs utiles:**
- Interface web: `https://ragfab.yourdomain.com`
- API docs: `https://api-ragfab.yourdomain.com/docs`
- Health checks: `/health` sur chaque service

**Support:**
- Documentation complète: [README.md](./README.md)
- Sécurité: [SECURITY.md](./SECURITY.md)
