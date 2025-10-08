# ✅ Checklist Déploiement Reranker sur Coolify

Utilise cette checklist pour déployer le reranking étape par étape.

---

## 📦 Étape 1 : Créer le Service Reranker

- [ ] Dans Coolify, aller dans le projet RAGFab
- [ ] Cliquer sur **"+ New Resource"** → **"Docker Compose"**
- [ ] Configurer :
  - **Name** : `ragfab-reranker`
  - **Docker Compose Location** : `coolify/5-reranker/docker-compose.yml`
- [ ] Variables d'environnement :
  ```
  RERANKER_MODEL=BAAI/bge-reranker-v2-m3
  LOG_LEVEL=INFO
  ```
- [ ] Ressources : CPU 2 cores, RAM 4GB
- [ ] Cliquer sur **"Deploy"**
- [ ] Attendre 2-3 minutes (téléchargement du modèle)
- [ ] Vérifier les logs : `INFO: Modèle chargé en XX.XXs`

---

## 🔧 Étape 2 : Mettre à Jour le Backend

- [ ] Aller dans le service **`ragfab-backend`**
- [ ] **Environment Variables** → Ajouter :
  ```
  RERANKER_ENABLED=false
  RERANKER_API_URL=http://ragfab-reranker:8002
  RERANKER_MODEL=BAAI/bge-reranker-v2-m3
  RERANKER_TOP_K=20
  RERANKER_RETURN_K=5
  ```
- [ ] Cliquer sur **"Redeploy"**
- [ ] Attendre que le backend redémarre

---

## 🗄️ Étape 3 : Migrer PostgreSQL

- [ ] Aller dans le service **`ragfab-postgres`**
- [ ] Cliquer sur **"Console"** ou **"Execute Command"**
- [ ] Exécuter : `psql -U raguser -d ragdb`
- [ ] Copier-coller ce SQL :
  ```sql
  ALTER TABLE conversations
  ADD COLUMN IF NOT EXISTS reranking_enabled BOOLEAN DEFAULT NULL;

  COMMENT ON COLUMN conversations.reranking_enabled IS
  'Contrôle du reranking: NULL=global, TRUE=activé, FALSE=désactivé';

  CREATE INDEX IF NOT EXISTS idx_conversations_reranking
  ON conversations(reranking_enabled)
  WHERE reranking_enabled IS NOT NULL;

  \d conversations
  ```
- [ ] Vérifier que tu vois : `reranking_enabled | boolean`
- [ ] Quitter psql : `\q`

---

## 🎨 Étape 4 : Redéployer le Frontend

- [ ] Aller dans le service **`ragfab-frontend`**
- [ ] Cliquer sur **"Redeploy"**
- [ ] Attendre 1-2 minutes

---

## ✅ Étape 5 : Vérifications

### Reranker
- [ ] Logs : `INFO: Uvicorn running on http://0.0.0.0:8002`
- [ ] Test : `curl http://ragfab-reranker:8002/health`
- [ ] Retourne : `{"status": "healthy", "model": "BAAI/bge-reranker-v2-m3"}`

### PostgreSQL
- [ ] Console : `psql -U raguser -d ragdb -c "\d conversations"`
- [ ] Voir : `reranking_enabled | boolean`

### Frontend
- [ ] Ouvrir RAGFab dans le navigateur
- [ ] Créer une nouvelle conversation
- [ ] Voir le bouton **"Reranking: Global"** (gris) dans l'en-tête
- [ ] Cliquer → devient vert **"Reranking: ON"**
- [ ] Cliquer → devient rouge **"Reranking: OFF"**
- [ ] Cliquer → retour au gris **"Reranking: Global"**

### Backend
- [ ] Envoyer un message dans une conversation
- [ ] Logs backend : chercher `🎚️ Préférence conversation` ou `🌐 Préférence globale`

---

## 🎉 Terminé !

Si toutes les cases sont cochées, le reranking est déployé et fonctionnel !

**Test final** :
1. Crée 2 conversations
2. Conversation A : Toggle vert (reranking ON)
3. Conversation B : Toggle rouge (reranking OFF)
4. Pose la même question dans les deux
5. Compare les résultats 🔍

---

## 🆘 En Cas de Problème

**Reranker ne démarre pas** → Logs service reranker
**Backend ne trouve pas reranker** → Vérifier URL `http://ragfab-reranker:8002`
**Toggle ne marche pas** → Vérifier migration SQL + logs backend
**Migration SQL échoue** → Vérifier si colonne existe déjà (normal)

Consulte `GUIDE_DEPLOIEMENT_RERANKING.md` pour plus de détails.
