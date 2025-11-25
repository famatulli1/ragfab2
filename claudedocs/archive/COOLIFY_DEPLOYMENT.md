# Guide de Déploiement sur Coolify

Ce guide explique comment déployer RAGFab sur Coolify avec le service de reranking.

## Prérequis

- Un serveur Coolify configuré
- Accès à l'interface Coolify
- Les variables d'environnement nécessaires (clés API, etc.)

## Architecture de Déploiement

RAGFab sur Coolify utilise les services suivants :

```
┌─────────────────────────────────────────────────────────┐
│                    COOLIFY STACK                        │
│                                                         │
│  ┌──────────────────┐      ┌──────────────────┐       │
│  │ ragfab-postgres  │◄────►│ ragfab-embeddings│       │
│  │ Port: 5432       │      │ Port: 8001       │       │
│  └────────┬─────────┘      └────────┬─────────┘       │
│           │                         │                  │
│           │         ┌───────────────┤                  │
│           │         │               │                  │
│  ┌────────▼─────────▼┐      ┌──────▼──────────┐       │
│  │ ragfab-reranker  │      │ ragfab-api      │       │
│  │ Port: 8002       │◄─────│ Port: 8000      │       │
│  └──────────────────┘      └────────┬─────────┘       │
│                                     │                  │
│                            ┌────────▼─────────┐       │
│                            │ ragfab-frontend  │       │
│                            │ Port: 3000       │       │
│                            └──────────────────┘       │
└─────────────────────────────────────────────────────────┘
```

## Étape 1 : Préparation du Projet

### 1.1 Cloner le Dépôt

```bash
git clone <votre-repo-ragfab>
cd ragfab
```

### 1.2 Vérifier les Fichiers de Configuration

Assurez-vous que les fichiers suivants sont présents :

- `docker-compose.yml`
- `database/schema.sql`
- `database/02_web_schema.sql`
- `database/03_reranking_migration.sql` (nouveau)
- `reranker-server/` (nouveau dossier complet)

## Étape 2 : Configuration Coolify

### 2.1 Créer un Nouveau Projet

1. Connectez-vous à Coolify
2. Créez un nouveau projet : "RAGFab"
3. Sélectionnez "Docker Compose" comme type de déploiement

### 2.2 Configuration du Réseau Interne

⚠️ **Important** : Coolify utilise des suffixes `.internal` pour la communication inter-services.

Dans Coolify, les services communiquent via :
- `ragfab-postgres.internal:5432`
- `ragfab-embeddings.internal:8001`
- `ragfab-reranker.internal:8002`

### 2.3 Variables d'Environnement

Configurez les variables d'environnement suivantes dans l'interface Coolify :

#### Variables Communes

```bash
# Database
POSTGRES_USER=raguser
POSTGRES_PASSWORD=<mot-de-passe-securise>
POSTGRES_DB=ragdb
POSTGRES_HOST=ragfab-postgres.internal
POSTGRES_PORT=5432
DATABASE_URL=postgresql://raguser:<password>@ragfab-postgres.internal:5432/ragdb

# JWT & Authentication
JWT_SECRET=<secret-key-securise>
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<admin-password-securise>

# Embeddings Service
EMBEDDINGS_API_URL=http://ragfab-embeddings.internal:8001
EMBEDDING_DIMENSION=1024
EMBEDDING_MODEL=intfloat/multilingual-e5-large

# Reranking Service (NOUVEAU)
RERANKER_ENABLED=false  # Activer globalement ou laisser par conversation
RERANKER_API_URL=http://ragfab-reranker.internal:8002
RERANKER_MODEL=BAAI/bge-reranker-v2-m3
RERANKER_TOP_K=20
RERANKER_RETURN_K=5

# LLM Providers
MISTRAL_API_KEY=<votre-cle-mistral>
MISTRAL_MODEL_NAME=mistral-small-latest
MISTRAL_TIMEOUT=120.0

CHOCOLATINE_API_URL=https://apigpt.mynumih.fr
CHOCOLATINE_MODEL_NAME=jpacifico/Chocolatine-2-14B-Instruct-v2.0.3
CHOCOLATINE_API_KEY=  # Optionnel

# CORS (pour le frontend)
CORS_ORIGINS=https://votre-domaine.com
```

#### Variables Spécifiques au Frontend

```bash
VITE_API_URL=/api  # ou l'URL complète de votre API
```

## Étape 3 : Configuration des Services

### 3.1 Préfixe des Noms de Conteneurs

⚠️ **Critique** : Tous les conteneurs doivent avoir un préfixe unique (`ragfab-`) pour éviter les conflits sur Coolify.

Dans `docker-compose.yml`, vérifiez que tous les services ont :

```yaml
services:
  postgres:
    container_name: ragfab-postgres
    # ...

  embeddings:
    container_name: ragfab-embeddings
    # ...

  reranker:
    container_name: ragfab-reranker
    # ...

  ragfab-api:
    container_name: ragfab-api
    # ...

  ragfab-frontend:
    container_name: ragfab-frontend
    # ...
```

### 3.2 Résolution DNS Interne

Dans les variables d'environnement qui référencent d'autres services, utilisez `.internal` :

```yaml
environment:
  DATABASE_URL: postgresql://raguser:pass@ragfab-postgres.internal:5432/ragdb
  EMBEDDINGS_API_URL: http://ragfab-embeddings.internal:8001
  RERANKER_API_URL: http://ragfab-reranker.internal:8002
```

## Étape 4 : Ressources Serveur

### 4.1 Ressources Recommandées

| Service | CPU | RAM | Disque | Priorité |
|---------|-----|-----|--------|----------|
| postgres | 1 core | 2GB | 10GB | Haute |
| embeddings | 2-4 cores | 4-8GB | 5GB | Haute |
| reranker | 1-2 cores | 2-4GB | 3GB | Moyenne |
| ragfab-api | 1-2 cores | 2GB | 1GB | Haute |
| ragfab-frontend | 0.5 core | 512MB | 500MB | Moyenne |

**Total recommandé** : 8 cores, 16GB RAM, 20GB disque

### 4.2 Ressources Minimales

| Service | CPU | RAM | Notes |
|---------|-----|-----|-------|
| postgres | 0.5 core | 1GB | Risque de lenteur |
| embeddings | 2 cores | 4GB | Minimum absolu |
| reranker | 1 core | 2GB | Minimum absolu |
| ragfab-api | 1 core | 1GB | Peut suffire |
| ragfab-frontend | 0.5 core | 256MB | Statique |

**Total minimal** : 5 cores, 8.5GB RAM

⚠️ **Important** :
- Les services d'embeddings et de reranking nécessitent de la RAM pour charger les modèles
- Avec moins de 8GB RAM total, le reranking peut être lent ou échouer

## Étape 5 : Déploiement

### 5.1 Déploiement Initial

1. Dans Coolify, importez votre `docker-compose.yml`
2. Configurez les variables d'environnement (voir Étape 2.3)
3. Lancez le déploiement

```bash
# Coolify exécutera automatiquement :
docker-compose up -d
```

### 5.2 Vérification du Déploiement

Vérifiez que tous les services démarrent correctement :

```bash
docker ps | grep ragfab
```

Vous devriez voir :
- `ragfab-postgres`
- `ragfab-embeddings`
- `ragfab-reranker`
- `ragfab-api`
- `ragfab-frontend`

### 5.3 Healthchecks

Coolify surveille automatiquement les healthchecks définis dans `docker-compose.yml` :

- **PostgreSQL** : `pg_isready -U raguser -d ragdb`
- **Embeddings** : `curl -f http://localhost:8001/health`
- **Reranker** : `curl -f http://localhost:8002/health`

## Étape 6 : Migration de la Base de Données

### 6.1 Appliquer la Migration Reranking

Si vous déployez sur une base existante, vous devez appliquer la migration :

```bash
docker exec -i ragfab-postgres psql -U raguser -d ragdb < database/03_reranking_migration.sql
```

### 6.2 Vérifier la Migration

```bash
docker exec ragfab-postgres psql -U raguser -d ragdb -c "\d conversations"
```

Vous devriez voir la colonne `reranking_enabled BOOLEAN`.

## Étape 7 : Configuration du Proxy (Traefik/Nginx)

Coolify utilise généralement Traefik pour le routage. Assurez-vous que :

### 7.1 Labels Traefik

Dans `docker-compose.yml`, ajoutez si nécessaire :

```yaml
ragfab-frontend:
  labels:
    - "traefik.enable=true"
    - "traefik.http.routers.ragfab-frontend.rule=Host(`votre-domaine.com`)"
    - "traefik.http.routers.ragfab-frontend.entrypoints=websecure"
    - "traefik.http.routers.ragfab-frontend.tls.certresolver=letsencrypt"
    - "traefik.http.services.ragfab-frontend.loadbalancer.server.port=3000"

ragfab-api:
  labels:
    - "traefik.enable=true"
    - "traefik.http.routers.ragfab-api.rule=Host(`api.votre-domaine.com`)"
    - "traefik.http.routers.ragfab-api.entrypoints=websecure"
    - "traefik.http.routers.ragfab-api.tls.certresolver=letsencrypt"
    - "traefik.http.services.ragfab-api.loadbalancer.server.port=8000"
```

### 7.2 CORS

Configurez `CORS_ORIGINS` pour autoriser votre domaine frontend :

```bash
CORS_ORIGINS=https://votre-domaine.com,https://www.votre-domaine.com
```

## Étape 8 : Tests Post-Déploiement

### 8.1 Test des Services

```bash
# Test PostgreSQL
docker exec ragfab-postgres pg_isready -U raguser

# Test Embeddings
curl http://localhost:8001/health

# Test Reranker
curl http://localhost:8002/health

# Test API
curl http://localhost:8000/health
```

### 8.2 Test du Toggle Reranking

1. Accédez au frontend : `https://votre-domaine.com`
2. Créez une nouvelle conversation
3. Cliquez sur le bouton "Reranking" dans l'en-tête
4. Vérifiez les 3 états :
   - 🟢 **Vert** : Reranking activé
   - 🔴 **Rouge** : Reranking désactivé
   - ⚪ **Gris** : Utilise la variable d'environnement globale

### 8.3 Test de Performance

Testez une requête avec et sans reranking :

```bash
# Sans reranking (toggle rouge ou env RERANKER_ENABLED=false)
time curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"conversation_id": "...", "message": "test"}'

# Avec reranking (toggle vert ou env RERANKER_ENABLED=true)
time curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"conversation_id": "...", "message": "test"}'
```

Le reranking ajoute ~200ms à la requête.

## Étape 9 : Monitoring et Logs

### 9.1 Consulter les Logs

```bash
# Logs de tous les services
docker-compose logs -f

# Logs d'un service spécifique
docker logs -f ragfab-reranker
docker logs -f ragfab-api
```

### 9.2 Messages de Log Clés

**Recherche avec reranking** :
```
🎚️ Préférence conversation <UUID>: reranking=True
🔄 Reranking activé: recherche de 20 candidats
🎯 Application du reranking sur 20 candidats
✅ 5 sources sauvegardées dans _current_request_sources
```

**Recherche sans reranking** :
```
🌐 Préférence globale (env): reranking=False
📊 Reranking désactivé: recherche vectorielle directe (top-5)
✅ 5 sources sauvegardées dans _current_request_sources
```

### 9.3 Métriques de Performance

Surveillez :
- **Temps de réponse API** : doit rester < 3s
- **Utilisation RAM embeddings** : ~4-8GB stable
- **Utilisation RAM reranker** : ~2-4GB stable
- **Utilisation disque PostgreSQL** : croissance linéaire avec documents

## Étape 10 : Mises à Jour

### 10.1 Mise à Jour du Code

```bash
git pull origin main
docker-compose build ragfab-api ragfab-frontend
docker-compose up -d ragfab-api ragfab-frontend
```

### 10.2 Mise à Jour des Modèles

Pour mettre à jour les modèles d'embeddings ou de reranking :

```bash
# Modifier les variables d'environnement dans Coolify
RERANKER_MODEL=BAAI/bge-reranker-v2-m3-new-version

# Redémarrer le service
docker-compose restart ragfab-reranker
```

## Dépannage

### Problème : Service Reranker ne Démarre Pas

**Symptômes** :
```
ragfab-reranker | ERROR: Model not found
```

**Solution** :
- Vérifiez que le modèle existe : `BAAI/bge-reranker-v2-m3`
- Augmentez la RAM allouée (minimum 2GB)
- Vérifiez les logs : `docker logs ragfab-reranker`

### Problème : Erreur "Connection Refused" au Reranker

**Symptômes** :
```
⚠️ Erreur lors du reranking (fallback vers vector search): Connection refused
```

**Solution** :
1. Vérifiez que le service est démarré : `docker ps | grep reranker`
2. Vérifiez le healthcheck : `curl http://localhost:8002/health`
3. Vérifiez l'URL dans les variables : `RERANKER_API_URL=http://ragfab-reranker.internal:8002`

### Problème : Toggle Reranking ne Fonctionne Pas

**Symptômes** :
- Le toggle ne change pas d'état
- Erreur 404 ou 500 lors du clic

**Solution** :
1. Vérifiez la migration : `docker exec ragfab-postgres psql -U raguser -d ragdb -c "SELECT reranking_enabled FROM conversations LIMIT 1;"`
2. Vérifiez les logs API : `docker logs -f ragfab-api | grep reranking`
3. Vérifiez la console navigateur (F12) pour les erreurs frontend

### Problème : RAM Insuffisante

**Symptômes** :
```
ragfab-embeddings | Killed
ragfab-reranker | Out of memory
```

**Solution** :
- Désactivez le reranking globalement : `RERANKER_ENABLED=false`
- Augmentez la RAM serveur à minimum 8GB
- Utilisez un modèle plus léger (non recommandé pour la qualité)

## Bonnes Pratiques

1. **Backups Réguliers** : Sauvegardez `postgres_data` quotidiennement
2. **Monitoring** : Configurez des alertes Coolify pour RAM > 80%
3. **Logs** : Activez la rotation des logs Docker
4. **Sécurité** :
   - Utilisez des mots de passe forts pour JWT_SECRET et ADMIN_PASSWORD
   - Activez HTTPS via Traefik
   - Limitez l'accès SSH au serveur
5. **Performance** :
   - Commencez avec `RERANKER_ENABLED=false`
   - Activez le reranking par conversation pour les tests A/B
   - Ajustez `RERANKER_TOP_K` selon vos besoins (10-30)

## Support

En cas de problème, consultez :
- Logs : `docker-compose logs -f`
- Documentation : `RERANKING_GUIDE.md`
- GitHub Issues : <votre-repo>/issues
