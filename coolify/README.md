# 🚀 Guide de Déploiement RAGFab sur Coolify

Ce guide explique comment déployer RAGFab en 4 services séparés sur Coolify pour une architecture distribuée et sécurisée.

---

## 📋 Architecture

```
┌─────────────────────────────────────────────────────────┐
│                                                         │
│  1. ragfab-frontend (Nginx + React)                    │
│     https://ragfab.yourdomain.com                       │
│     Port: 80                                            │
│                                                         │
└────────────────┬────────────────────────────────────────┘
                 │ HTTPS
                 ▼
┌─────────────────────────────────────────────────────────┐
│                                                         │
│  2. ragfab-backend (FastAPI)                           │
│     https://api-ragfab.yourdomain.com                   │
│     Port: 8000                                          │
│                                                         │
└─────┬───────────────────────┬─────────────────────────┘
      │ HTTPS                 │ PostgreSQL
      ▼                       ▼
┌─────────────────┐   ┌─────────────────────────────────┐
│                 │   │                                 │
│  3. Embeddings  │   │  4. PostgreSQL + pgvector       │
│  (FastAPI)      │   │     postgres-ragfab             │
│  Port: 8001     │   │     Port: 5432 (privé)          │
│                 │   │                                 │
└─────────────────┘   └─────────────────────────────────┘
```

---

## 🔐 Prérequis

- Serveur Coolify fonctionnel
- 4 domaines ou sous-domaines configurés (ou utiliser le réseau privé Coolify)
- Clé API Mistral (https://console.mistral.ai/)

### Domaines recommandés

```
ragfab.yourdomain.com          → Frontend
api-ragfab.yourdomain.com      → Backend
embeddings-ragfab.yourdomain.com → Embeddings
postgres-ragfab.yourdomain.com → PostgreSQL (optionnel, préférer réseau privé)
```

---

## 📦 Ordre de Déploiement

**Important:** Déployer dans l'ordre suivant pour gérer les dépendances.

### 1️⃣ Déployer PostgreSQL

**Emplacement:** `coolify/4-postgres/`

1. **Créer un nouveau service dans Coolify**
   - Type: Docker Compose
   - Repository: Votre repo Git
   - Branch: main
   - Docker Compose Path: `coolify/4-postgres/docker-compose.yml`

2. **Configurer les variables d'environnement**
   ```bash
   POSTGRES_USER=raguser
   POSTGRES_PASSWORD=VotreMotDePasseSecurise123!
   POSTGRES_DB=ragdb
   POSTGRES_PORT=5432
   ```

3. **⚠️ Sécurité:**
   - **NE PAS EXPOSER** le port 5432 publiquement
   - Utiliser le **réseau privé Coolify** ou un VPN
   - Si exposition nécessaire, whitelister les IPs du backend uniquement

4. **Déployer et vérifier**
   ```bash
   # Vérifier les logs
   docker logs ragfab-postgres

   # Tester la connexion (depuis le serveur)
   docker exec ragfab-postgres psql -U raguser -d ragdb -c "SELECT version();"
   ```

---

### 2️⃣ Déployer le Service Embeddings

**Emplacement:** `coolify/3-embeddings/`

1. **Créer un nouveau service dans Coolify**
   - Type: Docker Compose
   - Docker Compose Path: `coolify/3-embeddings/docker-compose.yml`

2. **Configurer les variables d'environnement**
   ```bash
   MODEL_NAME=intfloat/multilingual-e5-large
   LOG_LEVEL=INFO
   ```

3. **Configuration réseau**
   - Domaine: `embeddings-ragfab.yourdomain.com` (ou réseau privé)
   - Port: 8001
   - SSL: Activé (Let's Encrypt)

4. **Ressources recommandées**
   - CPU: 2-4 cores
   - RAM: 4-8 GB (le modèle pèse ~2GB)
   - Disk: 5GB minimum

5. **Déployer et vérifier**
   ```bash
   # Test de santé
   curl https://embeddings-ragfab.yourdomain.com/health

   # Test d'embedding
   curl -X POST https://embeddings-ragfab.yourdomain.com/embed \
     -H "Content-Type: application/json" \
     -d '{"texts": ["Bonjour le monde"]}'
   ```

---

### 3️⃣ Déployer le Backend API

**Emplacement:** `coolify/2-backend/`

1. **Créer un nouveau service dans Coolify**
   - Type: Docker Compose
   - Docker Compose Path: `coolify/2-backend/docker-compose.yml`

2. **Configurer les variables d'environnement**

   **Base de données:**
   ```bash
   # Option 1: Réseau privé Coolify (recommandé)
   DATABASE_URL=postgresql://raguser:VotreMotDePasse@ragfab-postgres:5432/ragdb

   # Option 2: Domaine public (si PostgreSQL exposé)
   DATABASE_URL=postgresql://raguser:VotreMotDePasse@postgres-ragfab.yourdomain.com:5432/ragdb
   ```

   **Embeddings:**
   ```bash
   EMBEDDINGS_API_URL=https://embeddings-ragfab.yourdomain.com
   EMBEDDING_DIMENSION=1024
   ```

   **Authentification:**
   ```bash
   # Générer avec: openssl rand -hex 32
   JWT_SECRET=votre_secret_jwt_genere_avec_openssl
   ADMIN_USERNAME=admin
   ADMIN_PASSWORD=VotreMotDePasseAdmin123!
   ```

   **Mistral API:**
   ```bash
   MISTRAL_API_KEY=votre_cle_api_mistral
   MISTRAL_API_URL=https://api.mistral.ai
   MISTRAL_MODEL_NAME=mistral-small-latest
   ```

   **CORS (important!):**
   ```bash
   CORS_ORIGINS=https://ragfab.yourdomain.com,https://www.ragfab.yourdomain.com
   ```

3. **Configuration réseau**
   - Domaine: `api-ragfab.yourdomain.com`
   - Port: 8000
   - SSL: Activé (Let's Encrypt)

4. **Déployer et vérifier**
   ```bash
   # Test de santé
   curl https://api-ragfab.yourdomain.com/health

   # Test d'authentification
   curl -X POST https://api-ragfab.yourdomain.com/api/auth/login \
     -H "Content-Type: application/json" \
     -d '{"username": "admin", "password": "VotreMotDePasseAdmin123!"}'
   ```

---

### 4️⃣ Déployer le Frontend

**Emplacement:** `coolify/1-frontend/`

1. **Créer un nouveau service dans Coolify**
   - Type: Docker Compose
   - Docker Compose Path: `coolify/1-frontend/docker-compose.yml`

2. **Configurer les variables d'environnement**
   ```bash
   BACKEND_API_URL=https://api-ragfab.yourdomain.com
   ```

3. **Configuration réseau**
   - Domaine: `ragfab.yourdomain.com`
   - Port: 80
   - SSL: Activé (Let's Encrypt)

4. **⚠️ Important: Configuration Nginx**

   Le frontend utilise Nginx pour proxifier les requêtes `/api/` vers le backend.
   Vérifiez que `nginx.coolify.conf` pointe vers la bonne URL backend.

5. **Déployer et vérifier**
   ```bash
   # Test de santé
   curl https://ragfab.yourdomain.com/health

   # Accéder à l'interface web
   open https://ragfab.yourdomain.com
   ```

---

## 🔧 Configuration Post-Déploiement

### 1. Initialiser la base de données

Si les schémas SQL ne se sont pas exécutés automatiquement:

```bash
# Se connecter au conteneur PostgreSQL
docker exec -it ragfab-postgres psql -U raguser -d ragdb

# Vérifier que les tables existent
\dt

# Si besoin, exécuter manuellement les schémas
\i /docker-entrypoint-initdb.d/01_schema.sql
\i /docker-entrypoint-initdb.d/02_web_schema.sql
```

### 2. Créer le premier utilisateur admin

```bash
# Via l'API backend
curl -X POST https://api-ragfab.yourdomain.com/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "email": "admin@yourdomain.com",
    "password": "VotreMotDePasseAdmin123!"
  }'
```

### 3. Ingérer des documents

Via l'interface web:
1. Connectez-vous sur `https://ragfab.yourdomain.com`
2. Allez dans "Documents"
3. Uploadez vos PDFs

Ou via l'API:
```bash
curl -X POST https://api-ragfab.yourdomain.com/api/documents/upload \
  -H "Authorization: Bearer VOTRE_JWT_TOKEN" \
  -F "file=@votre_document.pdf"
```

---

## 🔐 Sécurité - Checklist

- [ ] **PostgreSQL** : Port 5432 NON exposé publiquement (réseau privé uniquement)
- [ ] **JWT_SECRET** : Généré avec `openssl rand -hex 32` (32+ caractères)
- [ ] **POSTGRES_PASSWORD** : Mot de passe fort (16+ caractères, chiffres, symboles)
- [ ] **ADMIN_PASSWORD** : Mot de passe fort (16+ caractères)
- [ ] **CORS_ORIGINS** : Seulement les domaines autorisés (pas de `*`)
- [ ] **HTTPS** : Activé sur tous les services publics (Let's Encrypt)
- [ ] **Firewall** : Whitelister les IPs si nécessaire
- [ ] **Secrets** : Utiliser les variables d'environnement Coolify (pas de .env dans le repo)
- [ ] **Backup** : Planifier des backups PostgreSQL réguliers

---

## 📊 Monitoring et Logs

### Vérifier les logs

```bash
# Frontend
docker logs -f ragfab-frontend

# Backend
docker logs -f ragfab-backend

# Embeddings
docker logs -f ragfab-embeddings

# PostgreSQL
docker logs -f ragfab-postgres
```

### Health checks

```bash
# Script de monitoring
#!/bin/bash
echo "Frontend: $(curl -s https://ragfab.yourdomain.com/health)"
echo "Backend: $(curl -s https://api-ragfab.yourdomain.com/health)"
echo "Embeddings: $(curl -s https://embeddings-ragfab.yourdomain.com/health)"
```

---

## 🛠️ Troubleshooting

### Problème: Le frontend ne peut pas joindre le backend

**Solution:**
1. Vérifier que `BACKEND_API_URL` est correct dans les variables d'environnement du frontend
2. Vérifier les CORS dans le backend (`CORS_ORIGINS`)
3. Tester manuellement:
   ```bash
   curl -I https://api-ragfab.yourdomain.com/health
   ```

### Problème: Le backend ne peut pas joindre PostgreSQL

**Solution:**
1. Vérifier que `DATABASE_URL` est correct
2. Si réseau privé Coolify, vérifier que les services sont dans le même réseau
3. Tester la connexion:
   ```bash
   docker exec ragfab-backend curl -v telnet://ragfab-postgres:5432
   ```

### Problème: Les embeddings sont lents

**Solution:**
1. Augmenter les ressources CPU/RAM dans Coolify (4 cores / 8GB recommandé)
2. Vérifier que le modèle est bien mis en cache (volume `model_cache`)
3. Considérer l'utilisation d'un GPU si disponible

### Problème: Erreur 502 Bad Gateway

**Causes possibles:**
- Service non démarré (vérifier `docker ps`)
- Health check échoué (vérifier les logs)
- Timeout (augmenter les timeouts Nginx)

**Solution:**
```bash
# Redémarrer le service concerné
docker restart ragfab-frontend
docker restart ragfab-backend
```

---

## 📈 Optimisations de Performance

### PostgreSQL

Ajuster selon vos ressources serveur:

```sql
-- Se connecter à PostgreSQL
ALTER SYSTEM SET shared_buffers = '512MB';
ALTER SYSTEM SET effective_cache_size = '2GB';
ALTER SYSTEM SET maintenance_work_mem = '128MB';

-- Redémarrer PostgreSQL
docker restart ragfab-postgres
```

### Backend API

Augmenter le nombre de workers Uvicorn (dans le Dockerfile):

```bash
CMD ["uvicorn", "web-api.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### Embeddings

Pour GPU (modifier le Dockerfile):

```dockerfile
# Remplacer la ligne torch CPU par:
RUN pip install --no-cache-dir torch==2.5.1 --index-url https://download.pytorch.org/whl/cu121
```

---

## 🔄 Mise à Jour

Pour mettre à jour un service:

1. **Commiter les changements** dans votre repo Git
2. **Dans Coolify**, aller sur le service
3. Cliquer sur **"Redeploy"**
4. Coolify va rebuild l'image et redémarrer le service

**Important:**
- Les volumes persistent (PostgreSQL data, model cache, uploads)
- Les variables d'environnement sont conservées
- Zero-downtime si vous configurez plusieurs replicas

---

## 📝 Variables d'Environnement - Résumé

### Frontend
```bash
BACKEND_API_URL=https://api-ragfab.yourdomain.com
```

### Backend
```bash
DATABASE_URL=postgresql://raguser:password@ragfab-postgres:5432/ragdb
EMBEDDINGS_API_URL=https://embeddings-ragfab.yourdomain.com
EMBEDDING_DIMENSION=1024
JWT_SECRET=votre_secret_jwt_32_chars_min
ADMIN_USERNAME=admin
ADMIN_PASSWORD=password
MISTRAL_API_KEY=votre_cle_mistral
MISTRAL_MODEL_NAME=mistral-small-latest
CORS_ORIGINS=https://ragfab.yourdomain.com
LOG_LEVEL=INFO
```

### Embeddings
```bash
MODEL_NAME=intfloat/multilingual-e5-large
LOG_LEVEL=INFO
```

### PostgreSQL
```bash
POSTGRES_USER=raguser
POSTGRES_PASSWORD=password
POSTGRES_DB=ragdb
```

---

## 🎯 Architecture Alternative - Réseau Privé Coolify

Si Coolify supporte les réseaux privés, vous pouvez:

1. **Exposer uniquement le frontend** en HTTPS public
2. **Tous les autres services** en HTTP privé (pas de domaine)

**Avantages:**
- Plus sécurisé (backend/embeddings/postgres non accessibles depuis Internet)
- Pas besoin de certificats SSL pour les services internes
- Moins de latence (HTTP au lieu de HTTPS)

**Configuration:**
```bash
# Frontend (public)
BACKEND_API_URL=http://ragfab-backend:8000

# Backend (privé)
EMBEDDINGS_API_URL=http://ragfab-embeddings:8001
DATABASE_URL=postgresql://raguser:password@ragfab-postgres:5432/ragdb

# Embeddings (privé)
# Aucune variable externe nécessaire

# PostgreSQL (privé)
# Aucune variable externe nécessaire
```

---

## 📞 Support

- **Documentation Coolify:** https://coolify.io/docs
- **Issues RAGFab:** Créer une issue dans votre repo
- **Logs:** Toujours vérifier les logs Docker en premier

---

## ✅ Checklist de Déploiement Final

- [ ] PostgreSQL déployé et accessible depuis le backend
- [ ] Embeddings déployé et répond aux health checks
- [ ] Backend déployé et peut se connecter à PostgreSQL + Embeddings
- [ ] Frontend déployé et peut communiquer avec le backend
- [ ] Tous les services ont un health check vert
- [ ] HTTPS activé sur tous les services publics
- [ ] Variables d'environnement sensibles configurées (JWT, passwords, API keys)
- [ ] CORS configuré correctement
- [ ] Premier utilisateur admin créé
- [ ] Test d'upload de document réussi
- [ ] Test de recherche RAG réussi

---

**🎉 Félicitations ! Votre système RAGFab est déployé sur Coolify !**
