# 🚀 Guide Pas à Pas : Déploiement du Reranking sur Coolify

Ce guide t'explique comment ajouter le service de reranking à ton installation RAGFab existante sur Coolify.

---

## 📋 Étape 1 : Créer le Service Reranker sur Coolify

### 1.1 Créer un Nouveau Service

Dans ton projet Coolify RAGFab :

1. Clique sur **"+ New Resource"**
2. Sélectionne **"Docker Compose"**
3. Configure :
   - **Name** : `ragfab-reranker`
   - **Repository** : (ton repo GitHub/GitLab)
   - **Branch** : `main` (ou ta branche)
   - **Docker Compose Location** : `coolify/5-reranker/docker-compose.yml`

### 1.2 Variables d'Environnement

Dans la section **Environment Variables** du service, ajoute :

```bash
RERANKER_MODEL=BAAI/bge-reranker-v2-m3
LOG_LEVEL=INFO
```

### 1.3 Ressources

Configure les ressources :
- **CPU Limit** : 2 cores
- **Memory Limit** : 4GB
- **Memory Reservation** : 2GB

### 1.4 Déployer

Clique sur **"Deploy"** et attends que le service démarre.

**Logs à surveiller** :
```
INFO: Chargement du modèle BAAI/bge-reranker-v2-m3...
INFO: Modèle chargé en XX.XXs
INFO: Application startup complete
INFO: Uvicorn running on http://0.0.0.0:8002
```

⏱️ **Premier démarrage** : ~2-3 minutes (téléchargement du modèle ~500MB)

---

## 📋 Étape 2 : Mettre à Jour le Backend

### 2.1 Ajouter les Variables d'Environnement

Va dans ton service **`ragfab-backend`** existant → **Environment Variables** → Ajoute :

```bash
# Reranking Configuration
RERANKER_ENABLED=false
RERANKER_API_URL=http://ragfab-reranker:8002
RERANKER_MODEL=BAAI/bge-reranker-v2-m3
RERANKER_TOP_K=20
RERANKER_RETURN_K=5
```

### 2.2 Redéployer le Backend

Clique sur **"Redeploy"** pour que le backend charge les nouvelles variables.

---

## 📋 Étape 3 : Migrer la Base de Données

Tu dois ajouter une colonne `reranking_enabled` à la table `conversations`.

### Option A : Via la Console Coolify (RECOMMANDÉ)

1. Va dans ton service **`ragfab-postgres`**
2. Clique sur **"Console"** ou **"Execute Command"**
3. Exécute :
   ```bash
   psql -U raguser -d ragdb
   ```

4. **Dans psql**, copie-colle ceci :
   ```sql
   -- Ajouter la colonne reranking_enabled
   ALTER TABLE conversations
   ADD COLUMN IF NOT EXISTS reranking_enabled BOOLEAN DEFAULT NULL;

   -- Ajouter un commentaire explicatif
   COMMENT ON COLUMN conversations.reranking_enabled IS
   'Contrôle du reranking: NULL=global, TRUE=activé, FALSE=désactivé';

   -- Créer un index pour optimiser les requêtes
   CREATE INDEX IF NOT EXISTS idx_conversations_reranking
   ON conversations(reranking_enabled)
   WHERE reranking_enabled IS NOT NULL;

   -- Vérifier que ça a marché
   \d conversations
   ```

5. **Vérification** : Tu devrais voir dans la sortie :
   ```
   reranking_enabled | boolean |           |
   ```

6. **Quitter psql** :
   ```sql
   \q
   ```

### Option B : Via Script Automatique (si tu redéploies PostgreSQL)

Si tu prévois de redéployer PostgreSQL, le script de migration s'exécutera automatiquement au prochain démarrage (fichier `database/04_auto_migration_reranking.sh` déjà inclus dans le code).

---

## 📋 Étape 4 : Redéployer le Frontend

Pour avoir le nouveau code avec le bouton toggle :

1. Va dans ton service **`ragfab-frontend`**
2. Clique sur **"Redeploy"**

Attends que le déploiement se termine (~1-2 minutes).

---

## ✅ Étape 5 : Vérification

### 5.1 Vérifier le Service Reranker

**Dans les logs de `ragfab-reranker`** :
```
✅ INFO: Modèle chargé en XX.XXs
✅ INFO: Uvicorn running on http://0.0.0.0:8002
```

**Test healthcheck** (via console backend ou reranker) :
```bash
curl http://ragfab-reranker:8002/health
```

Devrait retourner :
```json
{"status": "healthy", "model": "BAAI/bge-reranker-v2-m3"}
```

### 5.2 Vérifier la Migration PostgreSQL

**Via console PostgreSQL** :
```bash
psql -U raguser -d ragdb -c "\d conversations"
```

Tu dois voir :
```
reranking_enabled | boolean |           |
```

### 5.3 Tester le Toggle dans l'Interface

1. Ouvre ton frontend RAGFab
2. Crée une nouvelle conversation
3. Dans l'en-tête, tu devrais voir un bouton **"Reranking: Global"** (gris) 🌐
4. Clique dessus :
   - 1er clic → **"Reranking: ON"** (vert) 🟢
   - 2ème clic → **"Reranking: OFF"** (rouge) 🔴
   - 3ème clic → retour au **"Reranking: Global"** (gris) 🌐

### 5.4 Vérifier les Logs Backend

**Dans les logs de `ragfab-backend`**, envoie un message et cherche :

Avec toggle **VERT** (activé) :
```
🎚️ Préférence conversation <UUID>: reranking=True
🔄 Reranking activé: recherche de 20 candidats
🎯 Application du reranking sur 20 candidats
```

Avec toggle **ROUGE** (désactivé) :
```
🎚️ Préférence conversation <UUID>: reranking=False
📊 Reranking désactivé: recherche vectorielle directe (top-5)
```

Avec toggle **GRIS** (global) :
```
🌐 Préférence globale (env): reranking=false
```

---

## 🎯 Résumé des Services

Après déploiement, tu auras **5 services** :

| Service | Description | Port Interne | Ressources |
|---------|-------------|--------------|------------|
| ragfab-postgres | Base de données | 5432 | 1 core, 2GB |
| ragfab-embeddings | Génération embeddings | 8001 | 4 cores, 8GB |
| **ragfab-reranker** | **Reranking (NOUVEAU)** | **8002** | **2 cores, 4GB** |
| ragfab-backend | API FastAPI | 8000 | 2 cores, 2GB |
| ragfab-frontend | Interface React | 3000 | 1 core, 512MB |

**Total recommandé** : 10 cores, 16.5GB RAM

---

## 🔧 Configuration Recommandée

### Pour Documentation Médicale (ton cas)

```bash
# Backend
RERANKER_ENABLED=false  # Désactivé globalement par défaut
RERANKER_TOP_K=20       # 20 candidats pour le reranking
RERANKER_RETURN_K=5     # Retourner 5 meilleurs résultats
```

**Stratégie** :
- Laisse le reranking **désactivé globalement** (`RERANKER_ENABLED=false`)
- Active-le **par conversation** via le toggle pour les conversations complexes
- Économise des ressources sur les conversations simples

### Tests A/B

Pour tester l'impact du reranking :

1. Crée 2 conversations
2. **Conversation A** : Toggle gris (désactivé)
3. **Conversation B** : Toggle vert (activé)
4. Pose la **même question** dans les deux
5. Compare les résultats

---

## 🐛 Dépannage

### Problème 1 : Service Reranker ne Démarre Pas

**Logs** :
```
ERROR: Model not found
```

**Solution** :
- Vérifie que le modèle est correct : `BAAI/bge-reranker-v2-m3`
- Augmente la RAM à 4GB minimum
- Vérifie que le serveur a accès à Hugging Face

### Problème 2 : Backend ne Trouve Pas le Reranker

**Logs** :
```
Connection refused to http://ragfab-reranker:8002
```

**Solutions** :
1. Vérifie que le service `ragfab-reranker` est **démarré**
2. Vérifie que l'URL est bien `http://ragfab-reranker:8002` (pas `.internal`)
3. Vérifie que les deux services sont dans le **même projet Coolify**

### Problème 3 : Toggle ne Fonctionne Pas

**Symptôme** : Le bouton ne change pas d'état

**Solutions** :
1. Vérifie que la migration PostgreSQL a été faite
2. Vérifie les logs backend pour des erreurs
3. Ouvre la console navigateur (F12) et cherche des erreurs

### Problème 4 : Migration SQL Échoue

**Erreur** :
```
ERROR: column "reranking_enabled" already exists
```

**Solution** : C'est normal si tu as déjà fait la migration. Ignore l'erreur.

**Vérification** :
```bash
psql -U raguser -d ragdb -c "SELECT column_name FROM information_schema.columns WHERE table_name='conversations' AND column_name='reranking_enabled';"
```

Devrait retourner :
```
 column_name
-------------------
 reranking_enabled
```

---

## 📊 Performances Attendues

### Latence

| Configuration | Temps de Réponse | Use Case |
|---------------|------------------|----------|
| Sans reranking | ~1-2s | FAQ simples |
| Avec reranking (TOP_K=20) | ~1.5-2.5s | Documentation technique |

**Coût du reranking** : ~200-300ms

### Qualité

Pour documentation **médicale technique** :
- **Amélioration pertinence** : +15-30%
- **Réduction faux positifs** : -20-40%
- **Meilleure précision** : Terminologie médicale mieux comprise

---

## 🎉 C'est Fini !

Tu as maintenant :
- ✅ Service reranker déployé
- ✅ Backend configuré
- ✅ Base de données migrée
- ✅ Frontend avec toggle

**Prochaines étapes** :
1. Teste le toggle dans différentes conversations
2. Compare avec/sans reranking sur tes documents médicaux
3. Ajuste `TOP_K` et `RETURN_K` selon tes besoins

---

## 📞 Besoin d'Aide ?

Si tu bloques, vérifie :
1. **Logs reranker** : Modèle chargé ?
2. **Logs backend** : Connexion au reranker OK ?
3. **Logs postgres** : Migration réussie ?
4. **Console navigateur** : Erreurs frontend ?

Bonne chance ! 🚀
