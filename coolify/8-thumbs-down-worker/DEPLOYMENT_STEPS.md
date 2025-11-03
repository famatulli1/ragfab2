# 🚀 Déploiement Thumbs Down - Étapes Coolify

## ✅ Ce qui a été fait

1. ✅ Migrations PostgreSQL 14 et 15 appliquées sur le serveur
2. ✅ Service `8-thumbs-down-worker` créé dans `/coolify/8-thumbs-down-worker/`
3. ✅ Backend et frontend déjà à jour avec le code thumbs down

---

## 📋 Variables à ajouter au BACKEND (ragfab-api)

### Variables OBLIGATOIRES à ajouter dans Coolify

Allez dans votre service **ragfab-api** (2-backend) → Variables d'environnement → Ajouter :

```bash
# -------------------------------------------
# Thumbs Down Validation System (NOUVEAU)
# -------------------------------------------

# Activer l'analyse IA automatique des thumbs down (true/false)
THUMBS_DOWN_AUTO_ANALYSIS=true

# Seuil de confidence pour déclencher révision admin (0.0-1.0)
# 0.7 = Équilibre (12-15% des cas nécessitent révision)
THUMBS_DOWN_CONFIDENCE_THRESHOLD=0.7

# Provider LLM pour analyse (mistral ou chocolatine)
THUMBS_DOWN_LLM_PROVIDER=chocolatine

# Activer les notifications utilisateurs automatiques (true/false)
THUMBS_DOWN_AUTO_NOTIFICATIONS=true
```

**Note** : Les autres paramètres LLM sont déjà configurés (`LLM_API_URL`, `LLM_API_KEY`, `LLM_MODEL_NAME`) et seront réutilisés.

---

## 📋 Variables pour le FRONTEND

**AUCUNE variable supplémentaire nécessaire** ✅

Le frontend est déjà à jour avec le code thumbs down et communique uniquement via l'API backend.

---

## 🎯 Étapes de déploiement

### Étape 1 : Ajouter les variables au BACKEND

1. **Aller dans Coolify** → Projet RAGFab → Service `ragfab-api`
2. **Onglet "Environment Variables"**
3. **Ajouter les 4 variables** listées ci-dessus :
   - `THUMBS_DOWN_AUTO_ANALYSIS=true`
   - `THUMBS_DOWN_CONFIDENCE_THRESHOLD=0.7`
   - `THUMBS_DOWN_LLM_PROVIDER=chocolatine`
   - `THUMBS_DOWN_AUTO_NOTIFICATIONS=true`
4. **Sauvegarder**

### Étape 2 : Rebuild le BACKEND

1. **Aller dans Coolify** → Service `ragfab-api`
2. **Cliquer sur "Redeploy"**
3. **Attendre la fin du build** (~2-3 minutes)
4. **Vérifier les logs** : pas d'erreur au démarrage

### Étape 3 : Rebuild le FRONTEND

1. **Aller dans Coolify** → Service `ragfab-frontend`
2. **Cliquer sur "Redeploy"**
3. **Attendre la fin du build** (~2-3 minutes)
4. **Vérifier que l'interface charge** correctement

### Étape 4 : Créer le service THUMBS-DOWN-WORKER

1. **Aller dans Coolify** → Projet RAGFab
2. **Cliquer sur "Add Resource"** → "Docker Compose"
3. **Nommer le service** : `ragfab-thumbs-down-worker`

#### Configuration Build

- **Repository** : Votre dépôt Git RAGFab
- **Branch** : `main`
- **Build Context** : `.` (racine du projet)
- **Dockerfile Path** : `web-api/Dockerfile`

#### Docker Compose

Coller le contenu de `/coolify/8-thumbs-down-worker/docker-compose.yml`

#### Variables d'environnement

Copier toutes les variables de `/coolify/8-thumbs-down-worker/.env.example` et les configurer.

**Variables OBLIGATOIRES** :
```bash
DATABASE_URL=postgresql://raguser:ragpass@ragfab-postgres.internal:5432/ragdb
LLM_API_URL=https://apigpt.mynumih.fr
LLM_API_KEY=votre-clé-chocolatine-ici
LLM_MODEL_NAME=jpacifico/Chocolatine-2-14B-Instruct-v2.0.3
LLM_USE_TOOLS=false
LLM_TIMEOUT=120.0
THUMBS_DOWN_AUTO_ANALYSIS=true
THUMBS_DOWN_CONFIDENCE_THRESHOLD=0.7
THUMBS_DOWN_LLM_PROVIDER=chocolatine
THUMBS_DOWN_AUTO_NOTIFICATIONS=true
LOG_LEVEL=INFO
```

4. **Sauvegarder et Déployer**
5. **Attendre la fin du build** (~2-3 minutes)

### Étape 5 : Vérifier que le worker fonctionne

1. **Aller dans les logs du worker** (Coolify → ragfab-thumbs-down-worker → Logs)
2. **Chercher ces messages** :
   ```
   🔔 Thumbs Down Worker started
   📡 Listening for thumbs down notifications on channel 'thumbs_down_created'...
   ✅ Connected to PostgreSQL notification channel
   ```

Si vous voyez ces messages → **Worker OK** ✅

---

## 🧪 Test du workflow complet

### Test rapide

1. **Aller sur RAGFab** (https://votre-domaine.com)
2. **Se connecter** (admin / admin)
3. **Poser une question** : "Quelle est la politique de télétravail ?"
4. **Mettre un thumbs down** 👎 avec feedback : "La réponse est incorrecte"
5. **Vérifier les logs du worker** :
   ```
   🔔 Received notification for rating: <rating_id>
   📊 Analyzing thumbs down rating: <rating_id>
   ✅ Thumbs down analysis completed: <rating_id>
   Classification: bad_answer | Confidence: 0.85
   ```

6. **Aller dans l'interface admin** :
   - Menu → Quality Management
   - Onglet "Validation Thumbs Down" (5ème onglet)
   - Vous devriez voir la validation créée

7. **Cliquer sur "Valider"** → Modal s'ouvre avec toutes les infos

### Test complet

Suivre le guide détaillé : `/claudedocs/THUMBS_DOWN_TESTING_GUIDE.md`

---

## 🎯 Résumé des services

Après déploiement, vous aurez :

| Service | Rôle | Port | Status |
|---------|------|------|--------|
| ragfab-frontend | Interface React | 3000 | ✅ À rebuild |
| ragfab-api | API Backend FastAPI | 8000 | ✅ À rebuild avec nouvelles variables |
| ragfab-postgres | Base de données | 5432 | ✅ OK (migrations appliquées) |
| ragfab-embeddings | Embeddings E5-Large | 8001 | ✅ OK |
| ragfab-reranker | Reranker BGE-M3 | 8002 | ✅ OK |
| ragfab-ingestion-worker | Worker ingestion docs | - | ✅ OK |
| ragfab-analytics-worker | Worker analyse qualité | - | ✅ OK |
| **ragfab-thumbs-down-worker** | **Worker validation thumbs down** | - | 🆕 **À créer** |

---

## 🐛 Troubleshooting

### Backend ne démarre pas après ajout variables

**Cause** : Variable mal formatée ou manquante

**Solution** :
1. Vérifier que toutes les 4 variables sont bien définies
2. Pas d'espaces dans les valeurs (ex: `true` et non ` true`)
3. Redéployer

### Worker ne se connecte pas à PostgreSQL

**Cause** : DATABASE_URL incorrect

**Solution** :
- Utiliser `ragfab-postgres.internal:5432` (réseau interne Coolify)
- Vérifier username/password

### Pas d'analyse IA déclenchée

**Cause** : Trigger PostgreSQL manquant ou worker pas démarré

**Solution** :
1. Vérifier que migrations 14 et 15 sont appliquées
2. Vérifier logs du worker : doit afficher "Connected to PostgreSQL notification channel"
3. Tester manuellement dans PostgreSQL :
   ```sql
   NOTIFY thumbs_down_created, 'test';
   ```
   Le worker doit réagir dans les logs.

---

## 📊 Interface utilisateur

### Quality Management → Tab "Validation Thumbs Down"

**3 sections** :
1. **Validations en attente** : Thumbs down nécessitant révision admin
2. **Utilisateurs à accompagner** : Users avec mauvaises formulations
3. **Documents à réingérer** : Docs avec sources manquantes

### Analytics → Nouveaux widgets

**2 widgets** :
1. **Résumé Thumbs Down** : Total, classifications, confidence moyenne
2. **Actions Requises** : Users à accompagner + Docs à réingérer

---

## ✅ Checklist finale

Avant de considérer le déploiement réussi :

- [ ] Backend rebuild avec nouvelles variables
- [ ] Frontend rebuild
- [ ] Worker thumbs-down créé et démarré
- [ ] Logs worker affichent "Connected to PostgreSQL notification channel"
- [ ] Test thumbs down → analyse automatique fonctionne
- [ ] Onglet "Validation Thumbs Down" visible dans Quality Management
- [ ] Widgets thumbs down visibles dans Analytics
- [ ] Modal de validation fonctionne

---

## 🎉 Conclusion

Une fois toutes ces étapes complétées, le système de validation thumbs down sera **COMPLÈTEMENT OPÉRATIONNEL** en production !

**Bénéfices attendus** :
- 📊 Détection automatique des problèmes de qualité RAG
- 🎯 Accompagnement utilisateurs (notifications pédagogiques)
- 📚 Optimisation réingestion (documents vraiment problématiques)
- 👨‍💼 Interface admin complète pour validation et actions

---

**Support** : Voir `/claudedocs/THUMBS_DOWN_TESTING_GUIDE.md` et `/claudedocs/THUMBS_DOWN_IMPLEMENTATION_SUMMARY.md`
