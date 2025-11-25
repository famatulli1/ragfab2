# Commande /deploy - Déploiement RAGFab

Tu es un expert en déploiement Docker et Coolify. Aide l'utilisateur à déployer ou mettre à jour RAGFab.

## Contexte Projet

- **Stack** : Docker Compose (PostgreSQL + Embeddings + Reranker + FastAPI + React)
- **Target** : Coolify avec Traefik
- **Fichier principal** : `docker-compose.yml`

## Actions Disponibles

### 1. Rebuild et Restart Local

```bash
# Rebuild services modifiés
docker-compose build ragfab-api ingestion-worker ragfab-frontend

# Restart avec les nouvelles images
docker-compose up -d ragfab-api ingestion-worker ragfab-frontend

# Vérifier statut
docker-compose ps
```

### 2. Vérification Santé Services

```bash
# Test endpoints internes
docker exec ragfab-api curl -f http://ragfab-embeddings:8001/health
docker exec ragfab-api curl -f http://ragfab-reranker:8002/health

# Test base de données
docker exec ragfab-postgres pg_isready -U raguser
```

### 3. Mise à Jour Coolify

Pour Coolify :
1. Commit et push les changements : `git add . && git commit -m "Update" && git push`
2. Dans Coolify UI → Service → **"Redeploy"**
3. Surveiller les logs de build

### 4. Rollback si Problème

```bash
# Voir historique des images
docker images | grep ragfab

# Rollback vers version précédente (si tag disponible)
docker-compose down
docker-compose up -d
```

## Checklist Pré-Déploiement

- [ ] Tests passent localement
- [ ] Variables d'environnement à jour
- [ ] Migrations SQL appliquées
- [ ] Build local réussi

## Exécuter

Quelle action souhaitez-vous effectuer ?
1. **rebuild** - Rebuild et restart local
2. **health** - Vérifier santé des services
3. **coolify** - Instructions pour Coolify
4. **rollback** - Rollback en cas de problème
