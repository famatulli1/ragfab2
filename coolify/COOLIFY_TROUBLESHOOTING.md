# Guide de Dépannage Coolify - RAGFab

## 🔧 Problèmes Courants et Solutions

### 1. Frontend accessible mais retourne 404

**Symptômes:**
- `https://ragbot.lab-numihfrance.fr` retourne 404
- `curl http://localhost` depuis le container fonctionne
- Les fichiers existent dans `/usr/share/nginx/html`

**Causes possibles:**

#### A. Domaine mal configuré dans Coolify
**Solution:**
1. Allez dans l'interface web de Coolify
2. Ouvrez l'application "1-frontend"
3. Section "Domains" → Vérifiez que `ragbot.lab-numihfrance.fr` est bien configuré
4. Vérifiez que "Enable HTTPS" est activé
5. Redéployez l'application

#### B. Caddy n'a pas encore généré le certificat SSL
**Solution:**
1. Vérifiez les logs Caddy: `docker logs coolify-proxy`
2. Cherchez les erreurs de génération de certificat Let's Encrypt
3. Vérifiez que le DNS pointe bien vers votre serveur: `dig ragbot.lab-numihfrance.fr`
4. Le port 443 doit être ouvert sur votre firewall

#### C. Configuration Nginx incorrecte
**Solution:**
1. Connectez-vous au container frontend:
   ```bash
   docker exec -it <frontend-container-id> sh
   ```
2. Testez Nginx:
   ```bash
   nginx -t
   ```
3. Si erreur, vérifiez `/etc/nginx/conf.d/default.conf`

### 2. Frontend 502 Bad Gateway lors de l'appel API

**Symptômes:**
- Appels à `https://ragbot.lab-numihfrance.fr/api/...` retournent 502
- Frontend charge correctement

**Causes possibles:**

#### A. Backend pas déployé ou crashé
**Solution:**
1. Vérifiez que le backend est déployé dans Coolify
2. Vérifiez les logs du backend:
   ```bash
   docker logs <backend-container-id>
   ```
3. Vérifiez que le healthcheck passe:
   ```bash
   docker exec <backend-container-id> curl -f http://localhost:8000/health
   ```

#### B. Container name incorrect
**Solution:**
1. Listez les containers sur le réseau coolify:
   ```bash
   docker network inspect coolify
   ```
2. Trouvez le nom réel du container backend
3. Si différent de `ragfab-backend`, mettez à jour `nginx.coolify.conf`:
   ```nginx
   proxy_pass http://<nom-réel-backend>:8000;
   ```
4. Redéployez le frontend

#### C. Backend et frontend pas sur le même réseau
**Solution:**
1. Vérifiez que les deux sont sur le réseau `coolify`:
   ```bash
   docker inspect <container-id> | grep -A 10 "Networks"
   ```
2. Si manquant, vérifiez que `networks: - coolify` est dans les docker-compose.yml

### 3. Backend ne peut pas se connecter à PostgreSQL

**Symptômes:**
- Backend logs montrent `password authentication failed` ou `could not translate host name`
- Healthcheck backend échoue

**Solutions:**

#### A. Container names PostgreSQL
**Solution:**
1. Trouvez le nom réel du container PostgreSQL:
   ```bash
   docker ps | grep postgres
   ```
2. Mettez à jour les variables d'environnement backend dans Coolify:
   ```bash
   DATABASE_URL=postgresql://raguser:ragpass123@<nom-container-postgres>:5432/ragdb
   ```

#### B. Schéma de base de données non initialisé
**Solution:**
1. Connectez-vous au container PostgreSQL:
   ```bash
   docker exec -it <postgres-container-id> psql -U raguser -d ragdb
   ```
2. Vérifiez que les tables existent:
   ```sql
   \dt
   ```
3. Si vide, exécutez les scripts SQL de `rag-app/init-db/`:
   ```bash
   docker exec -i <postgres-container-id> psql -U raguser -d ragdb < rag-app/init-db/01-schema.sql
   ```

#### C. Extension pgvector manquante
**Solution:**
1. Connectez-vous à PostgreSQL:
   ```bash
   docker exec -it <postgres-container-id> psql -U raguser -d ragdb
   ```
2. Créez l'extension:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

### 4. Embeddings service timeout

**Symptômes:**
- Backend logs: `Connection timeout to embeddings service`
- Embeddings healthcheck échoue

**Solutions:**

#### A. Service pas encore prêt (premier démarrage)
**Solution:**
- Le premier démarrage peut prendre 2-5 minutes pour télécharger le modèle (1.5 GB)
- Vérifiez les logs:
  ```bash
  docker logs <embeddings-container-id>
  ```
- Attendez de voir: `Uvicorn running on http://0.0.0.0:8001`

#### B. Mémoire insuffisante
**Solution:**
- Le service requiert minimum 4 GB de RAM
- Vérifiez l'utilisation mémoire:
  ```bash
  docker stats <embeddings-container-id>
  ```
- Si limite atteinte, augmentez dans docker-compose.yml:
  ```yaml
  deploy:
    resources:
      limits:
        memory: 8G
  ```

### 5. CORS errors dans le navigateur

**Symptômes:**
- Console navigateur: `CORS policy: No 'Access-Control-Allow-Origin' header`
- Requêtes API bloquées

**Solution:**
1. Mettez à jour la variable `CORS_ORIGINS` du backend:
   ```bash
   CORS_ORIGINS=https://ragbot.lab-numihfrance.fr,http://localhost:3000
   ```
2. Redéployez le backend

### 6. Certificat SSL non généré

**Symptômes:**
- Navigateur affiche "Certificat invalide" ou "Connexion non sécurisée"
- `https://` ne fonctionne pas

**Solutions:**

#### A. DNS pas encore propagé
**Solution:**
1. Vérifiez la résolution DNS:
   ```bash
   dig ragbot.lab-numihfrance.fr
   ```
2. Doit pointer vers l'IP de votre serveur Coolify
3. Attendez la propagation DNS (jusqu'à 24h)

#### B. Port 443 fermé
**Solution:**
1. Vérifiez le firewall:
   ```bash
   sudo ufw status
   ```
2. Ouvrez le port 443:
   ```bash
   sudo ufw allow 443/tcp
   ```

#### C. Let's Encrypt rate limit atteint
**Solution:**
- Let's Encrypt limite à 5 certificats par semaine par domaine
- Vérifiez les logs Caddy: `docker logs coolify-proxy`
- Attendez ou utilisez un sous-domaine différent

## 🔍 Commandes de Diagnostic

### Vérifier l'état global
```bash
# Tous les containers RAGFab
docker ps -a | grep ragfab

# Santé des services
docker ps --filter "name=ragfab" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Réseau Coolify
docker network inspect coolify | jq '.[] | .Containers'
```

### Tester la connectivité inter-services
```bash
# Depuis le frontend vers le backend
docker exec <frontend-container-id> wget -qO- http://ragfab-backend:8000/health

# Depuis le backend vers PostgreSQL
docker exec <backend-container-id> curl -v telnet://ragfab-postgres:5432

# Depuis le backend vers embeddings
docker exec <backend-container-id> curl -f http://ragfab-embeddings:8001/health
```

### Logs en temps réel
```bash
# Frontend
docker logs -f <frontend-container-id>

# Backend
docker logs -f <backend-container-id>

# PostgreSQL
docker logs -f <postgres-container-id>

# Embeddings
docker logs -f <embeddings-container-id>

# Caddy (proxy Coolify)
docker logs -f coolify-proxy
```

### Vérifier les variables d'environnement
```bash
# Voir toutes les variables d'un container
docker exec <container-id> env | sort
```

### Tester les healthchecks manuellement
```bash
# Frontend
docker exec <frontend-container-id> curl -f http://localhost/health

# Backend
docker exec <backend-container-id> curl -f http://localhost:8000/health

# PostgreSQL
docker exec <postgres-container-id> pg_isready -U raguser -d ragdb

# Embeddings
docker exec <embeddings-container-id> curl -f http://localhost:8001/health
```

## 📋 Checklist de Déploiement

Avant de signaler un bug, vérifiez:

- [ ] Les 4 services sont déployés dans Coolify (postgres, embeddings, backend, frontend)
- [ ] Tous les containers sont "healthy" (`docker ps`)
- [ ] Tous les services sont sur le réseau `coolify` (`docker network inspect coolify`)
- [ ] Le domaine est configuré dans l'interface Coolify
- [ ] Le DNS pointe vers l'IP du serveur (`dig <domain>`)
- [ ] Les ports 80 et 443 sont ouverts (`sudo ufw status`)
- [ ] Les variables d'environnement sont correctes dans Coolify
- [ ] La base de données est initialisée (tables + pgvector)
- [ ] Les logs ne montrent pas d'erreurs critiques

## 🆘 Support

Si le problème persiste:
1. Collectez les logs de tous les services
2. Vérifiez la configuration DNS et firewall
3. Créez une issue GitHub avec:
   - Description du problème
   - Logs des containers concernés
   - Sortie de `docker ps` et `docker network inspect coolify`
   - Variables d'environnement (masquez les secrets!)
