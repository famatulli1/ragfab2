# Analytics Worker - Coolify Deployment

Worker d'analyse qualité automatique pour RAGFab avec validation IA (Chocolatine).

## Fonctionnalités

- **Analyse automatique programmée** : Lance l'analyse chaque jour à 3h du matin (configurable)
- **Validation IA** : Utilise Chocolatine pour valider les décisions de blacklist/whitelist/réingestion
- **3 étapes d'analyse** :
  1. Calcul des scores de satisfaction par chunk
  2. Blacklist automatique des chunks problématiques
  3. Recommandations de réingestion des documents
- **Progression temps réel** : Updates en base de données (0-100%)
- **Audit trail complet** : Toutes les décisions enregistrées dans `quality_audit_log`

## Déploiement dans Coolify

### 1. Prérequis

- PostgreSQL avec migration 13 appliquée (`13_quality_management.sql`)
- Réseau Docker `coolify` existant
- Variables d'environnement configurées

### 2. Copier le fichier .env

```bash
cd /opt/ragfab/coolify/7-analytics-worker
cp .env.example .env
# Éditer .env avec vos valeurs
nano .env
```

### 3. Variables critiques à configurer

```bash
# ⚠️ IMPORTANT: Adapter selon votre installation
DATABASE_URL=postgresql://raguser:VOTRE_MOT_DE_PASSE@ragfab-postgres.internal:5432/ragdb

# Chocolatine (obligatoire pour validation IA)
CHOCOLATINE_API_URL=https://apigpt.mynumih.fr
CHOCOLATINE_MODEL=jpacifico/Chocolatine-2-14B-Instruct-v2.0.3

# Horaire d'exécution (format HH:MM)
QUALITY_ANALYSIS_SCHEDULE=03:00
```

### 4. Déployer le service

Depuis le répertoire du projet (racine):

```bash
cd /opt/ragfab
docker-compose -f coolify/7-analytics-worker/docker-compose.yml up -d --build
```

### 5. Vérifier le démarrage

```bash
# Voir les logs
docker logs -f ragfab-analytics-worker

# Vérifier le statut
docker ps | grep analytics-worker

# Tester la connexion DB
docker exec -it ragfab-analytics-worker python -c "import asyncpg; print('✅ Import OK')"
```

## Utilisation

### Déclenchement manuel

Via l'interface web:
1. Accéder à `https://votre-domaine.fr/admin/quality-management`
2. Onglet "Déclenchement Manuel"
3. Cliquer "Lancer l'Analyse Maintenant"
4. Observer la progression (0-100%)

Ou via SSH:
```bash
docker exec -it ragfab-analytics-worker python -c "
from worker import run_quality_analysis
import asyncio
asyncio.run(run_quality_analysis())
"
```

### Vérifier l'exécution automatique

Le lendemain matin (après l'heure programmée):
```bash
docker exec -it ragfab-postgres psql -U raguser -d ragdb -c "
SELECT id, status, progress, blacklisted_count, reingestion_recommendations, created_at
FROM analysis_runs
ORDER BY created_at DESC
LIMIT 5;
"
```

### Modifier l'horaire d'exécution

1. Éditer `.env`:
```bash
QUALITY_ANALYSIS_SCHEDULE=02:30  # Pour 2h30 du matin
```

2. Redémarrer le worker:
```bash
docker-compose -f coolify/7-analytics-worker/docker-compose.yml restart
```

## Surveillance

### Logs en temps réel
```bash
docker logs -f ragfab-analytics-worker
```

### Logs d'audit
```bash
docker exec -it ragfab-postgres psql -U raguser -d ragdb -c "
SELECT action, chunk_id, document_id, reason, created_at
FROM quality_audit_log
ORDER BY created_at DESC
LIMIT 20;
"
```

### Statistiques
```bash
docker exec -it ragfab-postgres psql -U raguser -d ragdb -c "
SELECT
  COUNT(*) FILTER (WHERE status='completed') as completed,
  COUNT(*) FILTER (WHERE status='failed') as failed,
  COUNT(*) FILTER (WHERE status='running') as running
FROM analysis_runs;
"
```

## Troubleshooting

### Worker ne démarre pas

```bash
# Vérifier les logs d'erreur
docker logs ragfab-analytics-worker

# Vérifier les variables d'environnement
docker exec -it ragfab-analytics-worker env | grep -E "(DATABASE|CHOCOLATINE|QUALITY)"

# Reconstruire le container
docker-compose -f coolify/7-analytics-worker/docker-compose.yml up -d --build --force-recreate
```

### Erreur de connexion PostgreSQL

```bash
# Vérifier que postgres est accessible
docker exec -it ragfab-analytics-worker ping ragfab-postgres.internal

# Vérifier DATABASE_URL (doit avoir .internal pour Coolify)
docker exec -it ragfab-analytics-worker env | grep DATABASE_URL
```

### Worker ne lance pas l'analyse automatique

```bash
# Vérifier l'horaire programmé dans les logs
docker logs ragfab-analytics-worker | grep "Prochaine exécution"

# Vérifier que le cron est actif
docker exec -it ragfab-analytics-worker ps aux | grep python

# Forcer une exécution manuelle pour tester
docker exec -it ragfab-analytics-worker python -c "
from worker import run_quality_analysis
import asyncio
asyncio.run(run_quality_analysis())
"
```

## Ressources

- **CPU**: 1 core (limite), 0.5 core (réservation)
- **Mémoire**: 1GB (limite), 512MB (réservation)
- **Réseau**: coolify (accès à postgres.internal)
- **Dépendances**: ragfab-postgres (doit être running)

## Mise à jour

```bash
cd /opt/ragfab
git pull
docker-compose -f coolify/7-analytics-worker/docker-compose.yml up -d --build
```
