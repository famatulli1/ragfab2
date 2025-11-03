# Thumbs Down Worker - Service Coolify

Worker asynchrone pour l'analyse automatique des thumbs down avec classification IA et actions automatiques.

## 🎯 Objectif

Ce worker écoute les notifications PostgreSQL (via pg_notify) lorsqu'un utilisateur met un thumbs down, puis :
1. Récupère le contexte complet (question, réponse, sources, feedback)
2. Appelle un LLM pour classifier le thumbs down en 4 catégories
3. Enregistre la validation avec confiance IA et besoin de révision admin
4. Crée des notifications pédagogiques automatiques si bad_question

## 📋 Prérequis

### Migrations PostgreSQL appliquées

**IMPORTANT** : Les migrations 14 et 15 doivent être appliquées AVANT de déployer ce worker.

```bash
# Vérifier que les migrations sont appliquées
docker exec -i <postgres_container> psql -U raguser -d ragdb -c \
  "SELECT filename, applied_at, success FROM schema_migrations
   WHERE filename IN ('14_add_user_to_ratings.sql', '15_thumbs_down_validation.sql');"

# Devrait retourner 2 lignes avec success = t
```

Si les migrations ne sont pas appliquées, voir : `/database/migrations/`

### Accès LLM API

Ce worker nécessite un accès à une API LLM (Mistral ou Chocolatine) pour classifier les thumbs down.

**Configurations supportées** :
- Chocolatine API (provider par défaut)
- Chocolatine API (alternatif)
- Tout autre LLM compatible OpenAI

## 🚀 Déploiement dans Coolify

### 1. Créer un nouveau service

Dans Coolify :
1. Aller dans votre projet RAGFab
2. Cliquer sur "Add Resource" → "Docker Compose"
3. Nommer le service : `ragfab-thumbs-down-worker`

### 2. Configuration du service

Dans Coolify :
- **Repository** : Votre dépôt Git RAGFab
- **Branch** : `main`
- **Docker Compose Location** : `coolify/8-thumbs-down-worker/docker-compose.yml`
- **Build Pack** : Docker Compose

### 3. Variables d'environnement

Copier les variables depuis `.env.example` et les configurer dans Coolify.

#### Variables obligatoires

```bash
# Database
DATABASE_URL=postgresql://raguser:ragpass@ragfab-postgres.internal:5432/ragdb

# LLM API (Chocolatine par défaut)
LLM_API_URL=https://apigpt.mynumih.fr
LLM_API_KEY=votre-chocolatine-api-key-ici
LLM_MODEL_NAME=jpacifico/Chocolatine-2-14B-Instruct-v2.0.3
LLM_USE_TOOLS=false
LLM_TIMEOUT=120.0

# Thumbs Down Configuration
THUMBS_DOWN_AUTO_ANALYSIS=true
THUMBS_DOWN_CONFIDENCE_THRESHOLD=0.7
THUMBS_DOWN_LLM_PROVIDER=chocolatine
THUMBS_DOWN_AUTO_NOTIFICATIONS=true
```

#### Variables optionnelles (legacy)

```bash
# Mistral (legacy, non utilisé)
MISTRAL_API_KEY=votre-chocolatine-api-key-ici

# Chocolatine (provider alternatif)
CHOCOLATINE_API_URL=https://apigpt.mynumih.fr
CHOCOLATINE_API_KEY=
CHOCOLATINE_MODEL_NAME=jpacifico/Chocolatine-2-14B-Instruct-v2.0.3
```

### 4. Réseau Coolify

Le service doit être sur le réseau `coolify` pour communiquer avec PostgreSQL.

**Important** : Utiliser `ragfab-postgres.internal` comme host PostgreSQL (réseau interne Coolify).

### 5. Déployer

1. Sauvegarder la configuration
2. Cliquer sur "Deploy"
3. Attendre la fin du build (~2-3 minutes)

## ✅ Vérification du déploiement

### 1. Vérifier que le worker est démarré

Dans Coolify, aller dans les logs du service et chercher :

```
🔔 Thumbs Down Worker started
📡 Listening for thumbs down notifications on channel 'thumbs_down_created'...
✅ Connected to PostgreSQL notification channel
```

### 2. Tester le workflow

1. **Créer un thumbs down** dans l'interface RAGFab
2. **Vérifier les logs du worker** :
   ```
   🔔 Received notification for rating: <rating_id>
   📊 Analyzing thumbs down rating: <rating_id>
   ✅ Thumbs down analysis completed: <rating_id>
   Classification: bad_answer | Confidence: 0.85 | Needs review: False
   ```

3. **Vérifier dans la base** :
   ```sql
   SELECT id, ai_classification, ai_confidence, needs_admin_review
   FROM thumbs_down_validations
   ORDER BY created_at DESC LIMIT 1;
   ```

## 🔧 Configuration avancée

### Ajuster le seuil de confidence

```bash
# Plus strict (moins de révisions admin = 5-10%)
THUMBS_DOWN_CONFIDENCE_THRESHOLD=0.8

# Plus permissif (plus de révisions admin = 20-25%)
THUMBS_DOWN_CONFIDENCE_THRESHOLD=0.6
```

### Désactiver les notifications automatiques

```bash
# Notifications manuelles uniquement
THUMBS_DOWN_AUTO_NOTIFICATIONS=false
```

### Utiliser Mistral au lieu de Chocolatine (optionnel)

```bash
THUMBS_DOWN_LLM_PROVIDER=mistral
LLM_API_URL=https://api.mistral.ai
LLM_API_KEY=your-mistral-api-key
LLM_MODEL_NAME=mistral-small-latest
```

## 🐛 Troubleshooting

### Worker ne démarre pas

**Symptôme** : Container crash au démarrage

**Solutions** :
1. Vérifier que PostgreSQL est accessible depuis le worker
2. Vérifier que `DATABASE_URL` est correct
3. Vérifier les logs : "Connection refused" → PostgreSQL down

### Pas de notification reçue

**Symptôme** : Thumbs down créé mais pas d'analyse

**Solutions** :
1. Vérifier que le trigger PostgreSQL existe :
   ```sql
   \df+ notify_thumbs_down_created
   ```
2. Vérifier que le worker écoute bien le channel `thumbs_down_created`
3. Tester manuellement :
   ```sql
   NOTIFY thumbs_down_created, 'test-rating-id';
   ```

### Erreurs LLM API

**Symptôme** : "Error analyzing thumbs down: API call failed"

**Solutions** :
1. Vérifier que `LLM_API_KEY` est correcte
2. Vérifier la connectivité réseau du worker
3. Augmenter `LLM_TIMEOUT` si timeouts fréquents

### Classification incorrecte

**Symptôme** : L'IA classe mal les thumbs down

**Solutions** :
1. Vérifier le prompt système dans `web-api/app/services/thumbs_down_analyzer.py`
2. Ajuster `THUMBS_DOWN_CONFIDENCE_THRESHOLD` pour plus de révisions admin
3. Utiliser un modèle LLM plus puissant (ex: mistral-medium au lieu de mistral-small)

## 📊 Métriques

### Logs à surveiller

- `🔔 Received notification` : Notifications reçues
- `✅ Analysis completed` : Analyses réussies
- `❌ Error analyzing` : Échecs d'analyse
- `📬 Notification created` : Notifications utilisateur créées

### Métriques de performance

- Temps moyen d'analyse : < 5s
- Taux de succès : > 95%
- Taux de révision admin : 12-15% (avec threshold 0.7)

## 🔗 Liens utiles

- Guide de test complet : `/claudedocs/THUMBS_DOWN_TESTING_GUIDE.md`
- Résumé technique : `/claudedocs/THUMBS_DOWN_IMPLEMENTATION_SUMMARY.md`
- Migrations : `/database/migrations/14_add_user_to_ratings.sql` et `15_thumbs_down_validation.sql`

## 📝 Notes

- Ce worker est **stateless** : il peut être redémarré à tout moment sans perte de données
- Il consomme **peu de ressources** : 256M RAM / 0.25 CPU en moyenne
- Il ne nécessite **aucun volume persistant**
- Il communique avec PostgreSQL uniquement (pas d'autres services)
