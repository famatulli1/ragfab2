# Guide de déploiement RAGFab sur Coolify

## Prérequis

- Un serveur Coolify configuré avec Traefik
- Un nom de domaine (ou sous-domaines) configuré dans votre DNS
- Clés API Mistral (ou autre LLM)

## Étapes de déploiement

### 1. Créer un nouveau projet dans Coolify

1. Connectez-vous à votre instance Coolify
2. Créez un nouveau projet : `RAGFab`
3. Ajoutez une nouvelle ressource de type **Docker Compose**

### 2. Configuration du repository

1. **Source** : Connectez votre repository Git contenant le projet RAGFab
2. **Branche** : `main` (ou votre branche de production)
3. **Docker Compose File** : `docker-compose.coolify.yml`

### 3. Variables d'environnement

Dans Coolify, configurez les variables d'environnement suivantes :

#### Variables obligatoires

```bash
# Base de données
POSTGRES_USER=raguser
POSTGRES_PASSWORD=VotreMot DePasseSecurisé123!
POSTGRES_DB=ragdb

# Sécurité
JWT_SECRET=VotreCléJWTSecrète256bitsMinimum!
ADMIN_USERNAME=admin
ADMIN_PASSWORD=VotreMotDePasseAdmin123!

# LLM API
MISTRAL_API_KEY=votre_clé_mistral_api
```

#### Variables de domaine

```bash
# Domaines (remplacez par vos vrais domaines)
FRONTEND_DOMAIN=ragfab.votredomaine.com
API_DOMAIN=api-ragfab.votredomaine.com

# Optionnel : exposer le service d'embeddings
EMBEDDINGS_DOMAIN=embeddings-ragfab.votredomaine.com
```

#### Variables optionnelles

```bash
# Modèles LLM
MISTRAL_MODEL_NAME=mistral-small-latest
CHOCOLATINE_API_URL=https://apigpt.mynumih.fr
CHOCOLATINE_MODEL_NAME=jpacifico/Chocolatine-2-14B-Instruct-v2.0.3
```

### 4. Configuration DNS

Ajoutez les enregistrements DNS suivants (Type A ou CNAME) :

```
ragfab.votredomaine.com          → IP de votre serveur Coolify
api-ragfab.votredomaine.com      → IP de votre serveur Coolify
embeddings-ragfab.votredomaine.com → IP de votre serveur Coolify (optionnel)
```

### 5. Configuration Traefik dans Coolify

Vérifiez que Traefik est configuré avec :

- **Entrypoint `websecure`** (port 443)
- **Certificate Resolver `letsencrypt`** pour les certificats SSL automatiques

Ces paramètres sont normalement configurés par défaut dans Coolify.

### 6. Déploiement

1. Cliquez sur **Deploy** dans Coolify
2. Attendez que tous les services se construisent et démarrent
3. Surveillez les logs pour détecter d'éventuelles erreurs

### 7. Ordre de démarrage des services

Les services démarreront dans cet ordre (grâce aux `depends_on`) :

1. **postgres** - Base de données PostgreSQL avec PGVector
2. **embeddings** - Service d'embeddings (peut prendre 2-3 minutes au premier démarrage)
3. **ragfab-api** - API Backend FastAPI (peut prendre 5-10 minutes si docling est installé)
4. **ragfab-frontend** - Interface web React

### 8. Vérification

Une fois le déploiement terminé :

1. Accédez à `https://ragfab.votredomaine.com`
2. Vous devriez voir l'interface de chat
3. Connectez-vous à `/admin` avec vos identifiants (`ADMIN_USERNAME` / `ADMIN_PASSWORD`)
4. Testez l'upload d'un document

### 9. Ressources serveur recommandées

| Service | CPU | RAM | Stockage |
|---------|-----|-----|----------|
| postgres | 1 core | 1 GB | 20 GB |
| embeddings | 2-4 cores | 4-8 GB | 10 GB |
| ragfab-api | 2-4 cores | 4-8 GB | 20 GB (pour docling) |
| ragfab-frontend | 0.5 core | 512 MB | 1 GB |
| **TOTAL** | **6-10 cores** | **10-18 GB** | **51 GB** |

### 10. Troubleshooting

#### Service embeddings ne démarre pas

```bash
# Vérifier les logs
docker logs ragfab-embeddings-1

# Le service peut prendre jusqu'à 2 minutes pour télécharger le modèle
```

#### Service ragfab-api échoue

```bash
# Vérifier que postgres est démarré
docker logs ragfab-postgres-1

# Vérifier que embeddings est ready
curl http://embeddings:8001/health
```

#### Erreur SSL/TLS

- Vérifiez que vos domaines pointent vers le serveur Coolify
- Attendez que Let's Encrypt génère les certificats (peut prendre 1-2 minutes)
- Vérifiez les logs Traefik dans Coolify

#### CORS errors

- Vérifiez que `FRONTEND_DOMAIN` est correctement configuré dans les variables d'environnement
- Le middleware Traefik CORS devrait être automatiquement appliqué via les labels

### 11. Mise à jour

Pour mettre à jour l'application :

1. Poussez vos changements sur Git
2. Dans Coolify, cliquez sur **Redeploy**
3. Coolify va automatiquement :
   - Pull les derniers changements
   - Rebuilder les images modifiées
   - Redémarrer les services

### 12. Sauvegarde

#### Base de données

```bash
# Backup PostgreSQL
docker exec ragfab-postgres-1 pg_dump -U raguser ragdb > backup.sql

# Restore
docker exec -i ragfab-postgres-1 psql -U raguser ragdb < backup.sql
```

#### Documents uploadés

Les documents sont stockés dans le volume `api_uploads`. Utilisez Coolify pour gérer les volumes persistants.

## Architecture des labels Traefik

Les services sont exposés via Traefik avec cette configuration :

```yaml
# Frontend
traefik.http.routers.ragfab-frontend.rule=Host(`ragfab.votredomaine.com`)
traefik.http.services.ragfab-frontend.loadbalancer.server.port=80

# API Backend
traefik.http.routers.ragfab-api.rule=Host(`api-ragfab.votredomaine.com`)
traefik.http.services.ragfab-api.loadbalancer.server.port=8000

# Middleware CORS automatique pour l'API
traefik.http.middlewares.ragfab-api-cors.headers.accesscontrolalloworiginlist=${FRONTEND_DOMAIN}
```

## Support

Pour toute question, consultez les logs dans Coolify ou contactez l'administrateur système.
