# Guide de Déploiement RAGFab sur Coolify

## Architecture Cible

```
┌────────────────────────────────────────────────────────────────────┐
│                       COOLIFY STACK                                │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐   │
│  │ PostgreSQL   │  │ Embeddings   │  │ Reranker (optionnel)   │   │
│  │ + PGVector   │  │ E5-Large     │  │ BGE-M3                 │   │
│  │ Port: 5432   │  │ Port: 8001   │  │ Port: 8002             │   │
│  └──────┬───────┘  └──────┬───────┘  └────────┬───────────────┘   │
│         └─────────────────┼──────────────────┬┘                    │
│              ┌────────────▼──────┐  ┌────────▼────────────────┐   │
│              │ Web API (FastAPI) │  │ Ingestion Worker        │   │
│              │ Port: 8000        │◄─┤ Docling + VLM (opt.)    │   │
│              └──────────┬────────┘  └─────────────────────────┘   │
│              ┌──────────▼────────┐      Volume partagé:           │
│              │ Frontend (React)  │      /app/uploads              │
│              │ Port: 5173        │                                │
│              └───────────────────┘                                │
└────────────────────────────────────────────────────────────────────┘
```

## Prérequis

### Ressources Serveur

| Service | CPU | RAM | Stockage |
|---------|-----|-----|----------|
| postgres | 1 core | 2 GB | 20 GB |
| embeddings | 2-4 cores | 4-8 GB | 5 GB |
| reranker | 1-2 cores | 2-4 GB | 3 GB |
| ragfab-api | 1-2 cores | 2-4 GB | 20 GB |
| ingestion-worker | 1 core | 2 GB | - |
| ragfab-frontend | 0.5 core | 512 MB | 1 GB |
| **TOTAL** | **8-10 cores** | **12-20 GB** | **50 GB** |

### Comptes et Clés API

- **Mistral API** : Clé depuis [console.mistral.ai](https://console.mistral.ai)
- **Domaine** : Accès DNS pour créer enregistrements A
- **Coolify** : Instance v4+ avec Traefik + Let's Encrypt

## Variables d'Environnement

### Variables Critiques (à générer)

```bash
# Générer des secrets forts
python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(64))"
python3 -c "import secrets; print('POSTGRES_PASSWORD=' + secrets.token_urlsafe(32))"
python3 -c "import secrets; print('ADMIN_PASSWORD=' + secrets.token_urlsafe(24))"
```

### Configuration Complète

```bash
# ==========================================
# DOMAINES (adapter à votre domaine)
# ==========================================
FRONTEND_DOMAIN=ragfab.votredomaine.com
API_DOMAIN=api.ragfab.votredomaine.com

# ==========================================
# BASE DE DONNÉES
# ==========================================
POSTGRES_USER=raguser
POSTGRES_PASSWORD=<MOT_DE_PASSE_GÉNÉRÉ>
POSTGRES_DB=ragdb
POSTGRES_HOST=ragfab-postgres.internal
DATABASE_URL=postgresql://raguser:<PASSWORD>@ragfab-postgres.internal:5432/ragdb

# ==========================================
# SERVICES INTERNES
# ==========================================
EMBEDDINGS_API_URL=http://ragfab-embeddings.internal:8001
EMBEDDING_DIMENSION=1024

# Reranking (désactivé par défaut - activation via toggle interface)
RERANKER_ENABLED=false
RERANKER_API_URL=http://ragfab-reranker.internal:8002
RERANKER_MODEL=BAAI/bge-reranker-v2-m3
RERANKER_TOP_K=20
RERANKER_RETURN_K=5

# ==========================================
# SÉCURITÉ
# ==========================================
SECRET_KEY=<CLÉ_SECRÈTE_64_CHARS>
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<MOT_DE_PASSE_ADMIN>

# ==========================================
# LLM PROVIDER
# ==========================================
LLM_API_URL=https://api.mistral.ai
LLM_API_KEY=<VOTRE_CLÉ_MISTRAL>
LLM_MODEL_NAME=mistral-small-latest
LLM_USE_TOOLS=true
LLM_TIMEOUT=120.0

# ==========================================
# CORS
# ==========================================
ALLOWED_ORIGINS=https://ragfab.votredomaine.com

# ==========================================
# VLM (optionnel - extraction d'images)
# ==========================================
VLM_ENABLED=false
IMAGE_PROCESSOR_ENGINE=internvl
```

## Déploiement Coolify

### Étape 1 : Créer le Projet

1. Coolify → **"+ New"** → **"Project"** → Nom: `ragfab`
2. **"+ Add New Resource"** → **"Docker Compose"**
3. Repository Git → Branche `main` → Fichier `docker-compose.yml`

### Étape 2 : Configurer les Variables

Dans Coolify → Project Settings → Environment Variables :
- Coller toutes les variables de la section précédente
- Marquer les secrets comme "Secret" (SECRET_KEY, PASSWORD, API_KEY)

### Étape 3 : Configuration DNS

```
ragfab.votredomaine.com      A    <IP_SERVEUR_COOLIFY>
api.ragfab.votredomaine.com  A    <IP_SERVEUR_COOLIFY>
```

Vérifier propagation : `dig ragfab.votredomaine.com`

### Étape 4 : Configurer SSL/Domaines

Pour chaque service public (ragfab-api, ragfab-frontend) :
1. Service Settings → Domains
2. Add Domain → Activer SSL automatique (Let's Encrypt)

### Étape 5 : Déployer

1. Cliquer **"Deploy"**
2. Surveiller les logs (premier déploiement : 10-20 min)

**Ordre de démarrage** :
```
1. ragfab-postgres      ⏱️ ~30s
2. ragfab-embeddings    ⏱️ ~2-3 min (télécharge modèle)
3. ragfab-reranker      ⏱️ ~1-2 min
4. ragfab-api           ⏱️ ~5-10 min (installe docling)
5. ingestion-worker     ⏱️ ~1-2 min
6. ragfab-frontend      ⏱️ ~30s
```

## Vérification Post-Déploiement

### Services Internes

```bash
# SSH sur serveur Coolify
docker ps | grep ragfab  # 6 conteneurs UP

# Tests de santé
docker exec ragfab-postgres pg_isready -U raguser
docker exec ragfab-api curl http://ragfab-embeddings.internal:8001/health
docker exec ragfab-api curl http://ragfab-reranker.internal:8002/health
```

### Endpoints Publics

```bash
curl https://api.ragfab.votredomaine.com/health
# Attendu: {"status":"ok"}

curl https://ragfab.votredomaine.com
# Attendu: HTML de l'interface React
```

### Test Fonctionnel Complet

1. Accéder à `https://ragfab.votredomaine.com`
2. Se connecter : `admin` / votre mot de passe
3. Admin → Upload un document PDF
4. Vérifier ingestion dans logs : `docker logs -f ingestion-worker`
5. Poser une question sur le document uploadé
6. Vérifier sources et réponse pertinente

## Troubleshooting

| Problème | Cause | Solution |
|----------|-------|----------|
| Service ne démarre pas | Variable manquante | `docker exec ragfab-api env \| grep DATABASE_URL` |
| Connection refused postgres | Mauvaise URL | Utiliser `ragfab-postgres.internal` |
| Embeddings timeout | Modèle pas chargé | Attendre 2-3 min au premier démarrage |
| SSL non fonctionnel | DNS pas propagé | Attendre 5-60 min + vérifier `dig` |
| CORS errors | ALLOWED_ORIGINS incorrect | Vérifier domaine exact avec protocole |
| Ingestion ne traite pas | Volume non partagé | Vérifier `uploads_data` partagé API/worker |

## Maintenance

### Mise à Jour

```bash
git pull origin main
# Dans Coolify → Service → "Redeploy"
```

### Backup Base de Données

```bash
# Backup
docker exec ragfab-postgres pg_dump -U raguser ragdb > backup_$(date +%Y%m%d).sql

# Restore
docker exec -i ragfab-postgres psql -U raguser -d ragdb < backup.sql
```

### Monitoring

```bash
# Ressources en temps réel
docker stats --format "table {{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}"

# Logs de tous services
docker-compose logs -f --tail 100

# Chercher erreurs
docker logs ragfab-api 2>&1 | grep -i error
```

## Optimisations RAG (Phase 3)

### Chunking Adaptatif pour Petits Documents

Les documents <800 mots sont désormais traités en 1 seul chunk pour préserver le contexte complet.

### Toggle Reranking

- **Par défaut** : Désactivé (réponses rapides ~1-2s)
- **Activation** : Toggle "Recherche approfondie" dans l'interface (réponses précises ~2-4s)
- L'état est sauvegardé par conversation

## Références Archivées

Pour les détails historiques et guides étendus, voir :
- `claudedocs/archive/COOLIFY_DEPLOYMENT.md` - Guide original complet
- `claudedocs/archive/DEPLOYMENT_PHASE3.md` - Optimisations RAG Phase 3
