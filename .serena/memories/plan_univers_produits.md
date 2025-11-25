# Plan d'implémentation - Univers Produits RAGFab

## Contexte
Segmentation des documents par univers produit (Medimail, Magh2, Sillage, etc.) pour éviter les mélanges de résultats RAG et permettre un contrôle d'accès par utilisateur.

---

## Feature 1 : Table et API Univers
**Objectif** : Créer l'entité "univers" en base et exposer les endpoints CRUD

### Tâches
- [ ] Migration SQL : `CREATE TABLE product_universes` (id, name, slug, description, detection_keywords, is_active, created_at)
- [ ] Modèle Pydantic : `ProductUniverse`, `ProductUniverseCreate`, `ProductUniverseResponse`
- [ ] Route admin : `POST/GET/PUT/DELETE /api/admin/universes`
- [ ] Test : créer/lister/modifier/supprimer un univers

### Fichiers impactés
- `database/migrations/19_product_universes.sql`
- `web-api/app/models.py`
- `web-api/app/routes/admin.py`

---

## Feature 2 : Liaison Documents → Univers
**Objectif** : Chaque document appartient à un univers

### Tâches
- [ ] Migration SQL : `ALTER TABLE documents ADD COLUMN universe_id UUID REFERENCES product_universes(id)`
- [ ] Modifier modèle `Document` pour inclure `universe_id`
- [ ] Modifier endpoint `GET /api/documents` pour filtrer par univers
- [ ] Interface admin : afficher l'univers de chaque document + filtre

### Fichiers impactés
- `database/migrations/20_documents_universe.sql`
- `web-api/app/models.py`
- `web-api/app/routes/documents.py`
- `frontend/src/pages/admin/Documents.tsx`

---

## Feature 3 : Liaison Users → Univers (droits)
**Objectif** : Un utilisateur a accès à N univers avec un univers par défaut

### Tâches
- [ ] Migration SQL : `CREATE TABLE user_universe_access` (user_id, universe_id, is_default, granted_at, granted_by)
- [ ] Modèles Pydantic : `UserUniverseAccess`, mise à jour `UserResponse`
- [ ] Routes admin : `POST/DELETE /api/admin/users/{id}/universes` (assigner/retirer univers)
- [ ] Route admin : `PUT /api/admin/users/{id}/default-universe` (définir défaut)
- [ ] Interface admin : gestion des univers par utilisateur

### Fichiers impactés
- `database/migrations/21_user_universe_access.sql`
- `web-api/app/models.py`
- `web-api/app/routes/users.py`
- `frontend/src/pages/admin/Users.tsx`

---

## Feature 4 : Sélecteur d'univers utilisateur
**Objectif** : L'utilisateur peut voir et changer son univers actif

### Tâches
- [ ] Route : `GET /api/me/universes` (liste des univers autorisés)
- [ ] Route : `PUT /api/me/active-universe` (changer univers actif en session)
- [ ] Stocker univers actif en session/JWT ou cookie
- [ ] Frontend : dropdown univers dans le header
- [ ] Persister le choix (localStorage ou session backend)

### Fichiers impactés
- `web-api/app/routes/auth.py`
- `web-api/app/auth.py` (contexte utilisateur)
- `frontend/src/components/Header.tsx`
- `frontend/src/contexts/UniverseContext.tsx` (nouveau)

---

## Feature 5 : Ingestion avec choix d'univers
**Objectif** : À l'upload, l'admin choisit l'univers cible

### Tâches
- [ ] Modifier endpoint ingestion : ajouter paramètre `universe_id` obligatoire
- [ ] Modifier `ingestion_jobs` : ajouter `universe_id`
- [ ] Worker ingestion : propager `universe_id` au document créé
- [ ] Interface admin upload : dropdown sélection univers
- [ ] Alerte incohérence (optionnel phase 1) : log warning si keywords univers différent détectés

### Fichiers impactés
- `database/migrations/22_ingestion_universe.sql`
- `web-api/app/routes/documents.py` (endpoint upload)
- `ingestion-worker/worker.py`
- `frontend/src/pages/admin/Upload.tsx`

---

## Feature 6 : Filtrage RAG par univers
**Objectif** : La recherche vectorielle filtre par univers actif

### Tâches
- [ ] Modifier fonction `match_chunks` : ajouter paramètre `universe_id`
- [ ] Modifier `hybrid_search.py` : passer `universe_id` depuis contexte user
- [ ] Ajouter index : `CREATE INDEX idx_documents_universe ON documents(universe_id)`
- [ ] Jointure chunks → documents → universe dans la recherche
- [ ] Test : vérifier qu'un user Medimail ne voit pas les chunks Sillage

### Fichiers impactés
- `database/schema.sql` ou migration
- `web-api/app/hybrid_search.py`
- `rag-app/rag_agent.py` (si applicable)

---

## Feature 7 : Option multi-univers
**Objectif** : Toggle "Rechercher dans tous mes univers"

### Tâches
- [ ] Ajouter paramètre `search_all_universes: bool` à l'endpoint chat
- [ ] Si true : filtrer sur tous les `universe_id` autorisés du user
- [ ] Frontend : checkbox/toggle dans l'interface chat
- [ ] Stocker préférence utilisateur (optionnel)

### Fichiers impactés
- `web-api/app/models.py` (ChatRequest)
- `web-api/app/hybrid_search.py`
- `frontend/src/pages/Chat.tsx`

---

## Feature 8 : Migration documents existants
**Objectif** : Interface pour classer les documents sans univers

### Tâches
- [ ] Vue admin : liste documents où `universe_id IS NULL`
- [ ] Action bulk : sélectionner plusieurs docs → assigner univers
- [ ] Action unitaire : modifier univers d'un document
- [ ] Indicateur : nombre de documents non classés dans dashboard

### Fichiers impactés
- `web-api/app/routes/admin.py`
- `frontend/src/pages/admin/Documents.tsx`
- `frontend/src/pages/admin/Dashboard.tsx`

---

## État d'avancement

| Feature | Status |
|---------|--------|
| F1 - Table & API Univers | ✅ DONE |
| F2 - Documents → Univers | ✅ DONE |
| F3 - Users → Univers | ✅ DONE |
| F4 - Sélecteur univers UI | ✅ DONE |
| F5 - Ingestion avec univers | ✅ DONE |
| F6 - Filtrage RAG | ✅ DONE |
| F7 - Option multi-univers | ✅ DONE |
| F8 - Migration docs existants | ✅ DONE (Backend) |

## Ordre d'implémentation recommandé

```
Feature 1 (Univers)     ████████░░  Base
Feature 2 (Doc→Univ)    ████████░░  Base  
Feature 3 (User→Univ)   ████████░░  Base
    ↓
Feature 5 (Ingestion)   ██████░░░░  Fonctionnel
Feature 6 (Filtrage)    ██████░░░░  Fonctionnel
    ↓
Feature 4 (Sélecteur)   ████░░░░░░  UX
Feature 7 (Multi-univ)  ████░░░░░░  UX
Feature 8 (Migration)   ████░░░░░░  UX
```

---

## Notes techniques

### Schéma DB final
```sql
product_universes (id, name, slug, description, detection_keywords[], is_active, created_at)
documents.universe_id → product_universes.id
user_universe_access (user_id, universe_id, is_default, granted_at, granted_by)
ingestion_jobs.universe_id → product_universes.id
```

### Contexte utilisateur enrichi
```python
class CurrentUser:
    id: UUID
    username: str
    is_admin: bool
    allowed_universes: list[UUID]
    default_universe_id: UUID
    active_universe_id: UUID  # celui en cours de session
```

---

## Commandes pour démarrer chaque feature

```bash
# Feature 1
/implement Feature 1 - Tables et API Univers (voir plan_univers_produits.md)

# Feature 2  
/implement Feature 2 - Liaison Documents → Univers (voir plan_univers_produits.md)

# etc.
```
