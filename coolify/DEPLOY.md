# 🚀 Déploiement RAGFab sur Coolify - Procédure Automatisée

## 📋 Prérequis

- Serveur Coolify configuré
- Domaine : `ragbot.lab-numihfrance.fr`
- Clé API Mistral

---

## ⚡ Déploiement Rapide (15 minutes)

### 1. PostgreSQL

**Dans Coolify :**
1. Créer une nouvelle application → Docker Compose
2. Path: `coolify/4-postgres/docker-compose.yml`
3. Variables d'environnement :
   ```bash
   POSTGRES_USER=raguser
   POSTGRES_PASSWORD=VotreMotDePasseSecure123!
   POSTGRES_DB=ragdb
   ```
4. **IMPORTANT:** Section "Storages" → **Supprimer tous les anciens montages** s'il y en a
5. Déployer

**Vérifier les logs :** Tu dois voir `✅ Base de données RAGFab initialisée avec succès !`

---

### 2. Embeddings

**Dans Coolify :**
1. Créer une nouvelle application → Docker Compose
2. Path: `coolify/3-embeddings/docker-compose.yml`
3. Variables d'environnement :
   ```bash
   MODEL_NAME=intfloat/multilingual-e5-large
   LOG_LEVEL=INFO
   ```
4. Ressources : 4-8 GB RAM minimum
5. Déployer

**Attendre :** Premier démarrage = 2-5 minutes (téléchargement du modèle 1.5 GB)

---

### 3. Backend API

**Dans Coolify :**
1. Créer une nouvelle application → Docker Compose
2. Path: `coolify/2-backend/docker-compose.yml`
3. Variables d'environnement :
   ```bash
   # Database
   DATABASE_URL=postgresql://raguser:VotreMotDePasseSecure123!@ragfab-postgres:5432/ragdb
   POSTGRES_HOST=ragfab-postgres
   POSTGRES_PORT=5432
   POSTGRES_USER=raguser
   POSTGRES_PASSWORD=VotreMotDePasseSecure123!
   POSTGRES_DB=ragdb

   # Embeddings
   EMBEDDINGS_API_URL=http://ragfab-embeddings:8001
   EMBEDDING_DIMENSION=1024

   # Security
   JWT_SECRET=GenerezUnSecretAvecOpenSSL
   ADMIN_USERNAME=admin
   ADMIN_PASSWORD=VotreMotDePasseAdmin!

   # Mistral API
   MISTRAL_API_KEY=VotreCléAPIMistral
   MISTRAL_API_URL=https://api.mistral.ai
   MISTRAL_MODEL_NAME=mistral-small-latest

   # CORS
   CORS_ORIGINS=https://ragbot.lab-numihfrance.fr
   ```
4. **PAS de domaine public** (backend privé)
5. Déployer

---

### 4. Frontend

**Dans Coolify :**
1. Créer une nouvelle application → Docker Compose
2. Path: `coolify/1-frontend/docker-compose.yml`
3. Variables d'environnement :
   ```bash
   BACKEND_API_URL=https://ragbot.lab-numihfrance.fr
   ```
4. **Domaine :** `ragbot.lab-numihfrance.fr`
5. **Enable HTTPS :** ✅ Activé
6. Déployer

---

## ✅ Vérification

### Test 1 : Frontend accessible
```bash
curl https://ragbot.lab-numihfrance.fr/health
# Attendu: "healthy"
```

### Test 2 : Backend (via proxy)
```bash
curl https://ragbot.lab-numihfrance.fr/api/health
# Attendu: {"status":"healthy"}
```

### Test 3 : Login admin
```bash
curl -X POST https://ragbot.lab-numihfrance.fr/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}'
# Attendu: {"access_token":"..."}
```

### Test 4 : Interface web
Ouvrir : `https://ragbot.lab-numihfrance.fr`

---

## 🔧 Dépannage

### Problème : PostgreSQL ne s'initialise pas

**Si le script init-db.sql ne s'exécute pas :**

1. Sur le serveur, exécute :
   ```bash
   cd /tmp
   git clone https://github.com/famatulli1/ragfab2.git
   bash ragfab2/coolify/init-postgres.sh
   ```

2. Dans Coolify :
   - Section "Storages" → Supprimer tous les montages
   - Redéployer PostgreSQL

3. Vérifier les logs : `✅ Base de données RAGFab initialisée avec succès !`

### Problème : Backend 500 erreurs

**Vérifie les logs :**
```bash
docker logs <backend-container-id> --tail 50
```

**Solutions courantes :**
- Erreur `relation "conversation_stats" does not exist` → Réinitialiser PostgreSQL
- Erreur `column "use_tools" does not exist` → Réinitialiser PostgreSQL
- Erreur `password authentication failed` → Vérifier les credentials

### Problème : Frontend 404

**Vérifications :**
1. Domaine configuré dans Coolify UI (section "Domains")
2. "Enable HTTPS" activé
3. Labels Traefik présents : `docker inspect <frontend-id> | grep traefik`

---

## 🎯 Architecture Finale

```
Internet (HTTPS)
    ↓
Traefik (Coolify)
    ↓
Frontend (Nginx) [PUBLIC] → ragbot.lab-numihfrance.fr
    ↓ /api/* → ragfab-backend:8000
Backend (FastAPI) [PRIVÉ]
    ↓
    ├─→ ragfab-postgres:5432 [PRIVÉ]
    └─→ ragfab-embeddings:8001 [PRIVÉ]
```

**Sécurité :**
- ✅ Seul le frontend est public
- ✅ Backend, PostgreSQL et Embeddings sont privés
- ✅ Toutes les communications internes via réseau Docker `coolify`

---

## 📝 Credentials par défaut

**Admin Web UI :**
- Username: `admin`
- Password: `admin`

⚠️ **CHANGEZ CES CREDENTIALS EN PRODUCTION !**

---

## 🔄 Redéploiement

Pour redéployer après des changements de code :

1. Push les changements sur GitHub
2. Dans Coolify, cliquer sur "Redeploy" pour chaque service
3. L'ordre n'est pas important (sauf PostgreSQL qui doit être démarré en premier)

**PostgreSQL :** Le script init-db.sql ne s'exécute que si le volume est vide. Pour réinitialiser, supprimer le volume d'abord.

---

**Tout fonctionne ? Parfait ! 🎉**

Des questions ? Consultez `COOLIFY_TROUBLESHOOTING.md`
