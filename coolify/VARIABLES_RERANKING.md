# 📋 Variables d'Environnement - Reranking

Copie-colle direct pour Coolify.

---

## Service : `ragfab-reranker` (NOUVEAU)

```bash
RERANKER_MODEL=BAAI/bge-reranker-v2-m3
LOG_LEVEL=INFO
```

---

## Service : `ragfab-backend` (AJOUTER)

```bash
RERANKER_ENABLED=false
RERANKER_API_URL=http://ragfab-reranker:8002
RERANKER_MODEL=BAAI/bge-reranker-v2-m3
RERANKER_TOP_K=20
RERANKER_RETURN_K=5
```

---

## Migration SQL : `ragfab-postgres`

Via Console PostgreSQL :

```sql
-- Se connecter
psql -U raguser -d ragdb

-- Exécuter la migration
ALTER TABLE conversations
ADD COLUMN IF NOT EXISTS reranking_enabled BOOLEAN DEFAULT NULL;

COMMENT ON COLUMN conversations.reranking_enabled IS
'Contrôle du reranking: NULL=global, TRUE=activé, FALSE=désactivé';

CREATE INDEX IF NOT EXISTS idx_conversations_reranking
ON conversations(reranking_enabled)
WHERE reranking_enabled IS NOT NULL;

-- Vérifier
\d conversations

-- Quitter
\q
```

---

## Résumé

**3 actions Coolify :**

1. **Nouveau service** `ragfab-reranker` → 2 variables
2. **Modifier** `ragfab-backend` → Ajouter 5 variables
3. **Console** `ragfab-postgres` → Exécuter le SQL

**2 redéploiements :**
- `ragfab-backend` → Redeploy
- `ragfab-frontend` → Redeploy

C'est tout ! 🚀
