# Guide de Test - Système de Validation Thumbs Down

## Vue d'ensemble du système

Le système de validation des thumbs down permet de :
1. ✅ Analyser automatiquement les thumbs down avec classification IA
2. ✅ Identifier les problèmes légitimes vs erreurs utilisateur
3. ✅ Accompagner les utilisateurs avec mauvaises formulations
4. ✅ Marquer les documents pour réingestion
5. ✅ Interface admin complète pour validation manuelle

## Architecture du workflow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         WORKFLOW COMPLET                            │
│                                                                     │
│  1. Utilisateur met un thumbs down dans le chat                   │
│                          ↓                                          │
│  2. Frontend enregistre le rating via POST /api/ratings            │
│                          ↓                                          │
│  3. PostgreSQL trigger émet notification pg_notify                 │
│                          ↓                                          │
│  4. Thumbs Down Worker écoute et reçoit notification              │
│                          ↓                                          │
│  5. Worker déclenche ThumbsDownAnalyzer.analyze_thumbs_down()     │
│                          ↓                                          │
│  6. Récupère contexte (question, réponse, sources, feedback)      │
│                          ↓                                          │
│  7. Appel LLM avec prompt de classification                        │
│                          ↓                                          │
│  8. Parse JSON response → Classification + Confidence              │
│                          ↓                                          │
│  9. Sauvegarde validation dans thumbs_down_validations            │
│                          ↓                                          │
│ 10. Si bad_question + AUTO_NOTIFICATIONS → Crée notification      │
│                          ↓                                          │
│ 11. Admin voit validation dans QualityManagementPage              │
│                          ↓                                          │
│ 12. Admin valide/override via ThumbsDownValidationModal           │
│                          ↓                                          │
│ 13. Actions automatiques (accompagnement, réingestion)            │
└─────────────────────────────────────────────────────────────────────┘
```

## Prérequis

### 1. Migrations de base de données appliquées

```bash
# Vérifier que les migrations 14 et 15 sont appliquées
docker-compose exec postgres psql -U raguser -d ragdb \
  -c "SELECT filename, applied_at, success FROM schema_migrations WHERE filename IN ('14_add_user_to_ratings.sql', '15_thumbs_down_validation.sql');"

# Devrait retourner 2 lignes avec success = true
```

### 2. Variables d'environnement configurées

Vérifier dans `.env` :
```bash
# Thumbs Down Configuration
THUMBS_DOWN_AUTO_ANALYSIS=true
THUMBS_DOWN_CONFIDENCE_THRESHOLD=0.7
THUMBS_DOWN_LLM_PROVIDER=mistral
THUMBS_DOWN_AUTO_NOTIFICATIONS=true

# LLM Configuration (nécessaire pour l'analyse)
LLM_API_URL=https://api.mistral.ai
LLM_API_KEY=your_mistral_api_key_here
LLM_MODEL_NAME=mistral-small-latest
LLM_TIMEOUT=120.0
```

### 3. Services démarrés

```bash
# Rebuild et démarrer tous les services (y compris le nouveau worker)
docker-compose up -d --build

# Vérifier que le worker thumbs-down est démarré
docker-compose ps thumbs-down-worker

# Devrait afficher : Status = Up
```

## Plan de test E2E

### Test 1 : Worker écoute les notifications PostgreSQL

**Objectif** : Vérifier que le worker est bien connecté et écoute les notifications.

```bash
# 1. Voir les logs du worker
docker-compose logs -f thumbs-down-worker

# Devrait afficher :
# "🔔 Thumbs Down Worker started"
# "📡 Listening for thumbs down notifications on channel 'thumbs_down_created'..."
# "✅ Connected to PostgreSQL notification channel"
```

**Critères de succès** :
- ✅ Worker démarre sans erreur
- ✅ Se connecte à PostgreSQL
- ✅ Écoute le channel pg_notify

### Test 2 : Classification automatique d'un thumbs down

**Objectif** : Vérifier que le workflow complet fonctionne (notification → analyse → sauvegarde).

**Étapes** :

1. **Créer une conversation et poser une question** :
   - Aller sur http://localhost:3000
   - Se connecter (admin / admin)
   - Poser une question : "Quelle est la politique de télétravail ?"

2. **Mettre un thumbs down avec feedback** :
   - Cliquer sur l'icône 👎 dans la réponse
   - Ajouter un feedback : "La réponse ne répond pas à ma question"
   - Soumettre

3. **Vérifier les logs du worker** :
   ```bash
   docker-compose logs -f thumbs-down-worker
   ```

   **Devrait afficher** :
   ```
   🔔 Received notification for rating: <rating_id>
   📊 Analyzing thumbs down rating: <rating_id>
   ✅ Thumbs down analysis completed: <rating_id>
   Classification: bad_answer | Confidence: 0.85 | Needs review: False
   ```

4. **Vérifier dans la base de données** :
   ```bash
   docker-compose exec postgres psql -U raguser -d ragdb -c \
     "SELECT id, ai_classification, ai_confidence, needs_admin_review, admin_action
      FROM thumbs_down_validations
      ORDER BY created_at DESC LIMIT 1;"
   ```

   **Devrait retourner** :
   - Une ligne avec `ai_classification` définie
   - `ai_confidence` entre 0.0 et 1.0
   - `needs_admin_review` = true si confidence < 0.7
   - `admin_action` = 'pending' par défaut

**Critères de succès** :
- ✅ Worker reçoit la notification
- ✅ Analyse IA s'exécute sans erreur
- ✅ Validation enregistrée dans `thumbs_down_validations`
- ✅ Classification correcte selon le contexte

### Test 3 : Notification utilisateur automatique (bad_question)

**Objectif** : Vérifier que les notifications pédagogiques sont créées pour les mauvaises questions.

**Étapes** :

1. **Créer un thumbs down avec mauvaise formulation** :
   - Poser une question mal formulée : "teletravai"
   - Mettre un thumbs down

2. **Attendre analyse automatique** (logs worker)

3. **Vérifier la notification créée** :
   ```bash
   docker-compose exec postgres psql -U raguser -d ragdb -c \
     "SELECT notification_type, title, message, read
      FROM user_notifications
      WHERE user_id = (SELECT user_id FROM thumbs_down_validations ORDER BY created_at DESC LIMIT 1)
      ORDER BY created_at DESC LIMIT 1;"
   ```

   **Devrait retourner** :
   - `notification_type` = 'quality_feedback'
   - `title` contenant "améliorer vos questions"
   - `message` avec reformulation suggérée
   - `read` = false

**Critères de succès** :
- ✅ Classification = `bad_question`
- ✅ Notification créée automatiquement
- ✅ Message pédagogique pertinent
- ✅ Reformulation suggérée présente

### Test 4 : Interface admin - Onglet "Validation Thumbs Down"

**Objectif** : Vérifier que l'interface admin affiche correctement les validations.

**Étapes** :

1. **Accéder à la page Quality Management** :
   - Aller sur http://localhost:3000/admin/quality
   - Cliquer sur l'onglet "Validation Thumbs Down" (5ème onglet)

2. **Vérifier les 3 sections affichées** :
   - **Validations en attente** : Liste des thumbs down nécessitant révision
   - **Utilisateurs à accompagner** : Tableau des utilisateurs avec bad_question
   - **Documents à réingérer** : Liste des documents problématiques

3. **Vérifier qu'une validation s'affiche** :
   - Devrait voir la validation créée au Test 2
   - Badge de classification coloré (rouge/orange/jaune/violet)
   - Badge "Révision requise" si confidence < 0.7
   - Bouton "Valider" pour ouvrir le modal

**Critères de succès** :
- ✅ Onglet s'affiche sans erreur
- ✅ Validations chargées et affichées
- ✅ Badges de classification corrects
- ✅ Données utilisateur affichées (nom, email)

### Test 5 : Modal de validation admin

**Objectif** : Vérifier que l'admin peut valider/modifier une classification.

**Étapes** :

1. **Ouvrir le modal de validation** :
   - Dans l'onglet "Validation Thumbs Down"
   - Cliquer sur "Valider" pour une validation en attente

2. **Vérifier le contenu du modal** :
   - ✅ Informations utilisateur (nom, email, username)
   - ✅ Question de l'utilisateur affichée
   - ✅ Réponse de l'assistant affichée
   - ✅ Feedback utilisateur (si présent)
   - ✅ Sources utilisées (avec score de similarité)
   - ✅ Classification IA avec badge coloré
   - ✅ Confiance IA en pourcentage
   - ✅ Raisonnement de l'IA
   - ✅ Reformulation suggérée (si présente)

3. **Tester la validation admin** :
   - Sélectionner un override de classification (optionnel)
   - Choisir une action admin : "Accompagner utilisateur"
   - Ajouter des notes admin : "L'utilisateur a mal orthographié 'télétravail'"
   - Cliquer "Valider"

4. **Vérifier la sauvegarde** :
   ```bash
   docker-compose exec postgres psql -U raguser -d ragdb -c \
     "SELECT admin_override, admin_action, admin_notes, validated_at, validated_by
      FROM thumbs_down_validations
      WHERE id = '<validation_id>';"
   ```

   **Devrait afficher** :
   - `admin_override` = classification choisie (si modifiée)
   - `admin_action` = 'contact_user'
   - `admin_notes` = texte saisi
   - `validated_at` = timestamp actuel
   - `validated_by` = UUID de l'admin

5. **Vérifier que la validation disparaît de la liste "En attente"**

**Critères de succès** :
- ✅ Modal s'ouvre avec toutes les données
- ✅ Override et action admin fonctionnent
- ✅ Validation sauvegardée en base
- ✅ UI se met à jour après validation

### Test 6 : Widgets Analytics Page

**Objectif** : Vérifier que les statistiques thumbs down s'affichent correctement.

**Étapes** :

1. **Accéder à la page Analytics** :
   - Aller sur http://localhost:3000/analytics

2. **Vérifier les 2 widgets thumbs down** :

   **Widget 1 : "Résumé Thumbs Down"**
   - Total des thumbs down
   - Nombre en attente de révision
   - Répartition par classification (4 catégories)
   - Confiance IA moyenne
   - Nombre d'overrides admin

   **Widget 2 : "Actions Requises"**
   - Utilisateurs à accompagner (avec compte)
   - Documents à réingérer (avec compte)
   - Boutons de navigation vers Quality Management

3. **Vérifier les chiffres** :
   ```bash
   docker-compose exec postgres psql -U raguser -d ragdb -c \
     "SELECT
        COUNT(*) as total,
        COUNT(*) FILTER (WHERE needs_admin_review = true AND validated_at IS NULL) as pending,
        COUNT(*) FILTER (WHERE COALESCE(admin_override, ai_classification) = 'bad_question') as bad_questions,
        AVG(ai_confidence) as avg_confidence
      FROM thumbs_down_validations;"
   ```

   **Les chiffres du widget doivent correspondre à la requête SQL**

**Critères de succès** :
- ✅ Widgets s'affichent sans erreur
- ✅ Statistiques correctes (correspondent à la base)
- ✅ Navigation vers Quality Management fonctionne

### Test 7 : Endpoint "Utilisateurs à accompagner"

**Objectif** : Vérifier que l'API retourne correctement les utilisateurs nécessitant un accompagnement.

**Étapes** :

1. **Créer 2-3 thumbs down classifiés "bad_question"** (répéter Test 2)

2. **Appeler l'endpoint via curl** :
   ```bash
   curl -X GET "http://localhost:8000/api/analytics/thumbs-down/users-to-contact" \
     -H "Authorization: Bearer <admin_jwt_token>"
   ```

3. **Vérifier la réponse** :
   ```json
   {
     "users_to_contact": [
       {
         "user_id": "uuid",
         "username": "john_doe",
         "email": "john@example.com",
         "first_name": "John",
         "last_name": "Doe",
         "bad_questions_count": 3,
         "recent_questions": ["question1", "question2", "question3"],
         "last_bad_question_date": "2025-01-31T10:30:00",
         "validation_ids": ["uuid1", "uuid2", "uuid3"]
       }
     ],
     "total_users": 1
   }
   ```

**Critères de succès** :
- ✅ Endpoint retourne HTTP 200
- ✅ Liste des utilisateurs avec bad_question validés
- ✅ Données utilisateur complètes
- ✅ Questions récentes incluses

### Test 8 : Endpoint "Documents à réingérer"

**Objectif** : Vérifier que l'API retourne les documents marqués pour réingestion.

**Étapes** :

1. **Créer un thumbs down classifié "missing_sources"**
2. **Valider avec action = "mark_for_reingestion"**

3. **Appeler l'endpoint** :
   ```bash
   curl -X GET "http://localhost:8000/api/analytics/thumbs-down/reingestion-candidates" \
     -H "Authorization: Bearer <admin_jwt_token>"
   ```

4. **Vérifier la réponse** :
   ```json
   {
     "documents": [
       {
         "document_id": "uuid",
         "document_title": "Politique télétravail.pdf",
         "source": "rh_docs",
         "occurrences_count": 2,
         "last_occurrence": "2025-01-31T11:00:00",
         "chunk_ids": ["chunk_uuid1", "chunk_uuid2"],
         "user_questions": ["question1", "question2"]
       }
     ],
     "total_documents": 1
   }
   ```

**Critères de succès** :
- ✅ Endpoint retourne HTTP 200
- ✅ Documents avec sources manquantes listés
- ✅ Nombre d'occurrences correct
- ✅ Questions utilisateur incluses

### Test 9 : Statistiques temporelles

**Objectif** : Vérifier que les statistiques sur 30 jours fonctionnent.

**Étapes** :

1. **Appeler l'endpoint stats** :
   ```bash
   curl -X GET "http://localhost:8000/api/analytics/thumbs-down/stats?days=30" \
     -H "Authorization: Bearer <admin_jwt_token>"
   ```

2. **Vérifier la structure de réponse** :
   ```json
   {
     "summary": {
       "total_thumbs_down": 5,
       "pending_review": 2,
       "bad_questions": 1,
       "bad_answers": 2,
       "missing_sources": 1,
       "unrealistic_expectations": 1,
       "avg_confidence": 0.75,
       "admin_overrides": 1,
       "users_to_contact": 1,
       "documents_to_reingest": 1
     },
     "temporal_distribution": [
       {
         "date": "2025-01-31",
         "count": 3,
         "avg_confidence": 0.80
       },
       {
         "date": "2025-01-30",
         "count": 2,
         "avg_confidence": 0.70
       }
     ]
   }
   ```

**Critères de succès** :
- ✅ Summary contient toutes les métriques
- ✅ Distribution temporelle sur N jours
- ✅ Confiance moyenne calculée correctement

## Tests de robustesse

### Test 10 : Gestion d'erreur - Worker sans LLM credentials

**Objectif** : Vérifier que le worker gère gracieusement l'absence de credentials LLM.

**Étapes** :

1. **Arrêter le worker** :
   ```bash
   docker-compose stop thumbs-down-worker
   ```

2. **Retirer temporairement LLM_API_KEY** :
   ```bash
   docker-compose run --rm -e LLM_API_KEY="" thumbs-down-worker
   ```

3. **Créer un thumbs down**

4. **Vérifier les logs** :
   ```
   ❌ Error analyzing thumbs down: LLM API credentials not configured
   ```

5. **Vérifier que la validation n'est PAS créée** (échec silencieux)

**Critères de succès** :
- ✅ Worker ne crash pas
- ✅ Erreur loggée clairement
- ✅ Pas de validation partielle enregistrée

### Test 11 : Gestion d'erreur - Réponse LLM invalide

**Objectif** : Vérifier la gestion des réponses LLM malformées.

**Simulation** : Le LLM peut retourner du texte non-JSON ou un JSON invalide.

**Critères de succès** :
- ✅ Erreur loggée : "Invalid JSON response from LLM"
- ✅ Classification par défaut : `bad_answer` avec confidence 0.5
- ✅ Validation créée avec `needs_admin_review = true`

### Test 12 : Performance - Multiple thumbs down simultanés

**Objectif** : Vérifier que le worker gère plusieurs notifications en parallèle.

**Étapes** :

1. **Créer 10 thumbs down rapidement** (script ou API)

2. **Observer les logs du worker** :
   ```bash
   docker-compose logs -f thumbs-down-worker
   ```

3. **Vérifier que toutes les validations sont créées** :
   ```bash
   docker-compose exec postgres psql -U raguser -d ragdb -c \
     "SELECT COUNT(*) FROM thumbs_down_validations WHERE created_at > NOW() - INTERVAL '1 minute';"
   ```

**Critères de succès** :
- ✅ Toutes les notifications traitées (10/10)
- ✅ Pas de timeouts ou crashes
- ✅ Ordre de traitement maintenu (FIFO)

## Checklist finale de validation

Avant de considérer la feature complète, vérifier :

### Backend
- [x] Migration 14 appliquée (user_id dans message_ratings)
- [x] Migration 15 appliquée (thumbs_down_validations + trigger)
- [x] ThumbsDownAnalyzer fonctionne (classification IA)
- [x] UserAccompanimentService crée notifications
- [x] Worker écoute pg_notify et traite les événements
- [x] 7 endpoints API retournent données correctes
- [x] Service Docker thumbs-down-worker démarré

### Frontend
- [x] Types TypeScript définis (thumbsDown.ts)
- [x] 7 méthodes API client implémentées
- [x] ThumbsDownValidationModal fonctionne
- [x] QualityManagementPage affiche 5ème onglet
- [x] 3 sections du tab fonctionnent (pending, users, docs)
- [x] 2 widgets Analytics affichent stats

### Workflow E2E
- [ ] Thumbs down → Notification → Analyse → Validation créée
- [ ] Classification IA correcte selon contexte
- [ ] Notifications utilisateur automatiques (bad_question)
- [ ] Interface admin affiche validations
- [ ] Modal validation fonctionne (override, actions, notes)
- [ ] Widgets analytics affichent statistiques correctes

### Gestion d'erreurs
- [ ] Worker gère absence credentials LLM
- [ ] Worker gère réponses LLM invalides
- [ ] Multiple notifications traitées sans perte

## Commandes utiles pour debugging

### Logs
```bash
# Worker thumbs down
docker-compose logs -f thumbs-down-worker

# API backend
docker-compose logs -f ragfab-api

# PostgreSQL
docker-compose logs postgres | grep "thumbs_down"
```

### Base de données

```bash
# Voir toutes les validations
docker-compose exec postgres psql -U raguser -d ragdb -c \
  "SELECT
     tv.id,
     tv.ai_classification,
     tv.ai_confidence,
     tv.needs_admin_review,
     tv.admin_action,
     u.username,
     tv.created_at
   FROM thumbs_down_validations tv
   JOIN users u ON tv.user_id = u.id
   ORDER BY tv.created_at DESC
   LIMIT 10;"

# Voir les notifications utilisateur
docker-compose exec postgres psql -U raguser -d ragdb -c \
  "SELECT
     notification_type,
     title,
     LEFT(message, 50) as message_preview,
     read,
     created_at
   FROM user_notifications
   WHERE notification_type = 'quality_feedback'
   ORDER BY created_at DESC
   LIMIT 5;"

# Statistiques globales
docker-compose exec postgres psql -U raguser -d ragdb -c \
  "SELECT
     COUNT(*) as total,
     COUNT(*) FILTER (WHERE needs_admin_review = true) as needs_review,
     COUNT(*) FILTER (WHERE validated_at IS NOT NULL) as validated,
     ROUND(AVG(ai_confidence)::numeric, 2) as avg_confidence
   FROM thumbs_down_validations;"
```

### Forcer une analyse manuelle
```bash
curl -X POST "http://localhost:8000/api/analytics/thumbs-down/analyze/<rating_id>" \
  -H "Authorization: Bearer <admin_jwt_token>"
```

## Résolution de problèmes courants

### Worker ne démarre pas
```bash
# Vérifier les logs
docker-compose logs thumbs-down-worker

# Erreurs possibles :
# - "Connection refused" → PostgreSQL pas démarré
# - "Import error" → Dépendances manquantes (rebuild)
# - "Environment variable missing" → .env incomplet

# Solution : Rebuild
docker-compose up -d --build thumbs-down-worker
```

### Notifications pas reçues
```bash
# Vérifier que le trigger existe
docker-compose exec postgres psql -U raguser -d ragdb -c \
  "\df+ notify_thumbs_down_created"

# Tester manuellement la notification
docker-compose exec postgres psql -U raguser -d ragdb -c \
  "NOTIFY thumbs_down_created, 'test-rating-id';"

# Devrait apparaître dans les logs du worker
```

### Classification IA incorrecte
```bash
# Vérifier le prompt système
# Voir: web-api/app/services/thumbs_down_analyzer.py

# Ajuster le threshold de confidence si trop de false positives
# Dans .env :
THUMBS_DOWN_CONFIDENCE_THRESHOLD=0.8  # Plus strict (moins de révisions auto)
```

## Prochaines étapes après validation

Si tous les tests passent :
1. ✅ Documenter la feature dans le README principal
2. ✅ Ajouter des exemples d'utilisation
3. ✅ Créer guide admin pour interpréter classifications
4. ✅ Configurer monitoring (métriques Prometheus si applicable)
5. ✅ Planifier analyse des patterns de mauvaises questions

## Conclusion

Une fois tous les tests passés, la feature "Validation Thumbs Down" est **complètement implémentée** et prête pour la production.

**Bénéfices attendus** :
- 📊 Meilleure visibilité sur la qualité des réponses RAG
- 🎯 Détection automatique des problèmes légitimes
- 📚 Accompagnement utilisateurs pour améliorer formulations
- 🔄 Processus de réingestion optimisé (documents problématiques ciblés)
- 👨‍💼 Interface admin complète pour validation et actions
