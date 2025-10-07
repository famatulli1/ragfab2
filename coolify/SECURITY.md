# 🔐 Guide de Sécurité - Déploiement RAGFab

Ce document détaille les bonnes pratiques de sécurité pour déployer RAGFab en production sur Coolify.

---

## 🎯 Principes de Sécurité

### 1. **Isolation des Services**

✅ **Ce qui est bien avec cette architecture:**

```
Frontend (HTTPS public)
    ↓
Backend (HTTPS public OU HTTP privé)
    ↓
Embeddings (HTTP privé seulement)
    ↓
PostgreSQL (privé, jamais exposé publiquement)
```

**Règles:**
- ❌ **JAMAIS** exposer PostgreSQL sur Internet
- ❌ **JAMAIS** exposer Embeddings sur Internet (sauf si authentification)
- ✅ **TOUJOURS** utiliser HTTPS pour le frontend
- ✅ **TOUJOURS** utiliser HTTPS pour le backend si exposé publiquement
- ✅ **PRÉFÉRER** HTTP sur réseau privé pour les communications internes

---

### 2. **Gestion des Secrets**

#### Variables sensibles

**❌ À NE JAMAIS COMMITER dans Git:**
```bash
JWT_SECRET=...
POSTGRES_PASSWORD=...
ADMIN_PASSWORD=...
MISTRAL_API_KEY=...
```

**✅ Stocker dans Coolify:**
1. Aller dans les paramètres du service
2. Ajouter les variables d'environnement
3. Activer "Encrypt" pour les secrets

#### Génération de secrets forts

```bash
# JWT Secret (32+ caractères hexadécimaux)
openssl rand -hex 32

# Mot de passe PostgreSQL (20 caractères alphanumériques + symboles)
openssl rand -base64 20

# Mot de passe admin (20 caractères)
openssl rand -base64 20
```

**Format recommandé:**
```bash
JWT_SECRET=a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6
POSTGRES_PASSWORD=X9#mK2@pL5!qR8&nT4
ADMIN_PASSWORD=V7$jF3%hB9^sD2*gA6
```

---

### 3. **Configuration PostgreSQL**

#### A. Ne JAMAIS exposer publiquement

**❌ Mauvaise configuration:**
```yaml
ports:
  - "5432:5432"  # Accessible depuis Internet
```

**✅ Bonne configuration (réseau privé Coolify):**
```yaml
# Pas de section ports!
# Accessible uniquement via ragfab-backend sur le réseau Docker
```

**✅ Alternative (si exposition nécessaire):**
```yaml
ports:
  - "127.0.0.1:5432:5432"  # Seulement localhost
```

#### B. Utiliser SSL pour les connexions

```bash
# Dans DATABASE_URL, ajouter sslmode=require
DATABASE_URL=postgresql://user:pass@host:5432/db?sslmode=require
```

#### C. Limiter les connexions

```sql
-- Créer un rôle avec permissions limitées
CREATE ROLE ragfab_app WITH LOGIN PASSWORD 'secure_password';
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO ragfab_app;
GRANT USAGE ON SCHEMA public TO ragfab_app;

-- Révoquer les permissions superuser
REVOKE ALL ON DATABASE ragdb FROM PUBLIC;
```

---

### 4. **Configuration Backend API**

#### A. CORS strict

**❌ À ÉVITER (trop permissif):**
```bash
CORS_ORIGINS=*
```

**✅ Bonne configuration:**
```bash
CORS_ORIGINS=https://ragfab.yourdomain.com,https://www.ragfab.yourdomain.com
```

**✅ En développement local:**
```bash
CORS_ORIGINS=https://ragfab.yourdomain.com,http://localhost:3000
```

#### B. Rate Limiting

Ajouter dans le backend FastAPI (fichier `web-api/app/main.py`):

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Limiter les requêtes à 100 par minute par IP
@app.post("/api/chat")
@limiter.limit("100/minute")
async def chat_endpoint(request: Request):
    ...
```

**Installation:**
```bash
pip install slowapi
```

#### C. Limiter la taille des uploads

Dans `web-api/app/main.py`:

```python
from fastapi import File, UploadFile

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

@app.post("/api/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    # Vérifier la taille
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large")
    ...
```

---

### 5. **Configuration Frontend**

#### A. Headers de sécurité Nginx

Vérifier dans `nginx.coolify.conf`:

```nginx
# Security headers
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';" always;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
```

#### B. Cacher les informations serveur

```nginx
# Masquer la version Nginx
server_tokens off;
```

#### C. Limiter les requêtes

```nginx
# Limiter le taux de requêtes par IP
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;

location /api/ {
    limit_req zone=api_limit burst=20 nodelay;
    proxy_pass ${BACKEND_API_URL};
    ...
}
```

---

### 6. **Configuration Embeddings**

#### A. Authentification par token

Ajouter dans `embeddings-server/app.py`:

```python
from fastapi import Header, HTTPException

EMBEDDINGS_API_TOKEN = os.getenv("EMBEDDINGS_API_TOKEN", "")

async def verify_token(authorization: str = Header(None)):
    if not EMBEDDINGS_API_TOKEN:
        return  # Pas d'authentification si pas de token configuré

    if authorization != f"Bearer {EMBEDDINGS_API_TOKEN}":
        raise HTTPException(status_code=401, detail="Invalid token")

@app.post("/embed", dependencies=[Depends(verify_token)])
async def embed_endpoint(request: EmbedRequest):
    ...
```

**Configuration:**
```bash
# Embeddings service
EMBEDDINGS_API_TOKEN=votre_token_secret_genere

# Backend service
EMBEDDINGS_API_URL=https://embeddings.yourdomain.com
EMBEDDINGS_API_TOKEN=votre_token_secret_genere
```

#### B. Limiter les requêtes

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/embed")
@limiter.limit("60/minute")  # 60 requêtes par minute max
async def embed_endpoint(request: Request):
    ...
```

---

### 7. **Backup et Récupération**

#### A. Backup PostgreSQL automatique

**Script de backup (à exécuter via cron):**

```bash
#!/bin/bash
# backup-postgres.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups/postgres"
CONTAINER_NAME="ragfab-postgres"

mkdir -p $BACKUP_DIR

# Dump de la base de données
docker exec $CONTAINER_NAME pg_dump -U raguser ragdb | gzip > "$BACKUP_DIR/ragdb_$DATE.sql.gz"

# Garder seulement les 7 derniers jours
find $BACKUP_DIR -name "ragdb_*.sql.gz" -mtime +7 -delete

echo "Backup créé: ragdb_$DATE.sql.gz"
```

**Crontab (backup quotidien à 2h du matin):**
```bash
0 2 * * * /path/to/backup-postgres.sh >> /var/log/postgres-backup.log 2>&1
```

#### B. Restauration

```bash
# Décompresser le backup
gunzip ragdb_20250107_020000.sql.gz

# Restaurer
docker exec -i ragfab-postgres psql -U raguser ragdb < ragdb_20250107_020000.sql
```

---

### 8. **Monitoring et Alertes**

#### A. Logs centralisés

**Envoyer les logs vers un service externe (ex: Loki, Elasticsearch):**

```yaml
# docker-compose.yml
services:
  ragfab-backend:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
        labels: "service=ragfab-backend"
```

#### B. Alertes de sécurité

**Surveiller:**
- Tentatives de login échouées (bruteforce)
- Requêtes avec erreurs 401/403
- Utilisation CPU/RAM anormale
- Connexions PostgreSQL multiples depuis une même IP

**Script de monitoring basique:**

```bash
#!/bin/bash
# security-monitor.sh

# Compter les erreurs 401 dans les logs backend
FAILED_LOGINS=$(docker logs ragfab-backend --since 1h | grep "401" | wc -l)

if [ $FAILED_LOGINS -gt 50 ]; then
    echo "ALERTE: $FAILED_LOGINS tentatives de login échouées dans la dernière heure"
    # Envoyer un email ou notification
fi
```

---

### 9. **Firewall et Réseau**

#### A. Firewall serveur (UFW)

```bash
# Installer UFW
sudo apt install ufw

# Autoriser SSH
sudo ufw allow 22/tcp

# Autoriser HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Bloquer tout le reste par défaut
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Activer le firewall
sudo ufw enable
```

#### B. Whitelisting d'IPs

Si vous voulez autoriser uniquement certaines IPs à accéder au backend:

```nginx
# Dans nginx.coolify.conf
location /api/ {
    # Autoriser seulement ces IPs
    allow 203.0.113.0/24;  # Votre réseau
    allow 198.51.100.50;   # IP spécifique
    deny all;

    proxy_pass ${BACKEND_API_URL};
    ...
}
```

---

### 10. **Checklist de Sécurité Finale**

#### Infrastructure
- [ ] PostgreSQL non exposé publiquement (réseau privé uniquement)
- [ ] Embeddings non exposé publiquement (ou avec authentification)
- [ ] HTTPS activé sur frontend et backend (Let's Encrypt)
- [ ] Firewall UFW configuré (ports 80, 443, 22 seulement)

#### Secrets
- [ ] JWT_SECRET généré aléatoirement (32+ caractères)
- [ ] POSTGRES_PASSWORD fort (16+ caractères, symboles)
- [ ] ADMIN_PASSWORD fort (16+ caractères, symboles)
- [ ] MISTRAL_API_KEY stockée dans Coolify (encrypted)
- [ ] Aucun secret dans le code Git

#### Backend
- [ ] CORS strict (pas de `*`)
- [ ] Rate limiting activé (100 req/min)
- [ ] Taille max upload limitée (50MB)
- [ ] SSL/TLS pour connexion PostgreSQL
- [ ] Logs d'accès activés

#### Frontend
- [ ] Headers de sécurité Nginx configurés
- [ ] Content Security Policy (CSP) configurée
- [ ] Server tokens cachés
- [ ] Rate limiting Nginx activé

#### Base de données
- [ ] Rôle PostgreSQL avec permissions minimales
- [ ] Backup automatique quotidien
- [ ] Rotation des backups (7 jours)
- [ ] Test de restauration effectué

#### Monitoring
- [ ] Health checks configurés sur tous les services
- [ ] Logs centralisés ou archivés
- [ ] Alertes pour échecs de login
- [ ] Monitoring CPU/RAM/Disk

---

## 🚨 Que Faire en Cas d'Incident

### 1. Fuite de credentials

```bash
# 1. Changer immédiatement les mots de passe
# PostgreSQL
docker exec -it ragfab-postgres psql -U raguser -d ragdb -c "ALTER USER raguser WITH PASSWORD 'nouveau_mdp';"

# 2. Régénérer le JWT_SECRET
openssl rand -hex 32

# 3. Mettre à jour les variables Coolify

# 4. Redéployer les services
```

### 2. Tentative d'intrusion détectée

```bash
# 1. Vérifier les logs
docker logs ragfab-backend | grep "401\|403"

# 2. Identifier l'IP attaquante
docker logs ragfab-backend | grep "IP_SUSPECTE"

# 3. Bloquer l'IP dans le firewall
sudo ufw deny from IP_SUSPECTE

# 4. Vérifier les accès récents à la base
docker exec ragfab-postgres psql -U raguser -d ragdb -c "SELECT * FROM pg_stat_activity;"
```

### 3. Base de données compromise

```bash
# 1. Couper l'accès immédiatement
docker stop ragfab-postgres

# 2. Restaurer depuis le dernier backup sain
gunzip /backups/postgres/ragdb_20250106_020000.sql.gz
docker start ragfab-postgres
docker exec -i ragfab-postgres psql -U raguser ragdb < ragdb_20250106_020000.sql

# 3. Changer tous les credentials
# 4. Investiguer les logs pour comprendre le vecteur d'attaque
```

---

## 📚 Ressources Supplémentaires

- **OWASP Top 10:** https://owasp.org/www-project-top-ten/
- **PostgreSQL Security:** https://www.postgresql.org/docs/current/security.html
- **FastAPI Security:** https://fastapi.tiangolo.com/tutorial/security/
- **Nginx Security:** https://docs.nginx.com/nginx/admin-guide/security-controls/

---

**🔒 La sécurité est un processus continu, pas une destination !**
