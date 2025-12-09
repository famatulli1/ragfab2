# Migration vers sessionStorage - 2025-01-09

## Résumé des Changements

**Problème résolu** : Les tokens d'authentification persistaient après fermeture du navigateur, créant une faille de sécurité.

**Solution implémentée** : Migration de `localStorage` vers `sessionStorage` pour le stockage des tokens d'authentification.

## Détails Techniques

### Changements de Stockage

| Avant | Après | Impact |
|-------|-------|--------|
| `localStorage.getItem('access_token')` | `sessionStorage.getItem('access_token')` | Token effacé à la fermeture du navigateur |
| `localStorage.setItem('access_token', ...)` | `sessionStorage.setItem('access_token', ...)` | Token stocké uniquement pour la session |
| `localStorage.removeItem('access_token')` | `sessionStorage.removeItem('access_token')` | Nettoyage dans sessionStorage |

### Fichiers Modifiés

1. **`frontend/src/api/client.ts`** (4 changements + migration)
   - Ligne 93 : Request interceptor (token retrieval)
   - Ligne 106 : Response interceptor 401 (token cleanup)
   - Ligne 120 : Login method (token storage)
   - Ligne 131 : Logout method (token removal)
   - **+ Nouveau** : Fonction `migrateTokenToSessionStorage()` (lignes 61-75)

2. **`frontend/src/components/ProtectedRoute.tsx`** (2 changements)
   - Ligne 16 : Token check for authentication
   - Ligne 28 : Token cleanup on auth failure

3. **`frontend/src/components/PdfViewerModal.tsx`** (1 changement)
   - Ligne 72 : Token retrieval for authenticated PDF fetch

**Total** : 7 remplacements + 1 nouvelle fonction de migration

## Fonction de Migration (Rétrocompatibilité)

Une fonction de migration a été ajoutée pour assurer une transition en douceur :

```typescript
/**
 * Migration utility: Moves token from localStorage to sessionStorage
 * Backward compatibility for users with existing localStorage tokens
 */
function migrateTokenToSessionStorage(): void {
  const oldToken = localStorage.getItem('access_token');
  if (oldToken && !sessionStorage.getItem('access_token')) {
    console.log('🔄 Migrating access_token from localStorage to sessionStorage');
    sessionStorage.setItem('access_token', oldToken);
    localStorage.removeItem('access_token');
  }
}

// Run migration immediately on module load
migrateTokenToSessionStorage();
```

**Comportement** :
- S'exécute automatiquement au chargement du module `client.ts`
- Détecte les tokens existants dans `localStorage`
- Les migre vers `sessionStorage`
- Nettoie `localStorage`
- Affiche un message de confirmation dans la console

**Note** : Cette fonction peut être supprimée après 30 jours (tous les utilisateurs migrés).

## Impact Utilisateur

### ✅ Comportements Maintenus

- **Navigation dans l'application** : L'authentification persiste pendant la navigation
- **Rafraîchissement de page** : Le token reste valide après un rafraîchissement (F5)
- **Logout manuel** : Le bouton "Déconnexion" fonctionne normalement
- **Erreur 401** : Déconnexion automatique et redirection vers login

### 🆕 Nouveaux Comportements (Sécurité Renforcée)

1. **Fermeture du navigateur** → Déconnexion automatique
   - Le token est effacé quand l'utilisateur ferme complètement le navigateur
   - L'utilisateur doit se reconnecter à la prochaine visite

2. **Onglets multiples** → Login indépendant par onglet
   - Chaque onglet a sa propre session d'authentification
   - Ouvrir un nouvel onglet nécessite un nouveau login
   - Fermer un onglet n'affecte pas les autres onglets

3. **Migration transparente** → Pas d'interruption pour les utilisateurs actuels
   - Les utilisateurs déjà connectés avec `localStorage` sont automatiquement migrés
   - Aucune déconnexion forcée lors du déploiement

### ⚠️ Changements Notables

- **Session limitée** : L'authentification ne persiste plus indéfiniment
- **Multi-onglets** : Chaque onglet nécessite sa propre authentification
- **Sécurité** : Protection renforcée contre les accès non autorisés

## Configuration Backend (Inchangée)

Les paramètres JWT backend restent inchangés :

```python
# web-api/app/config.py
JWT_EXPIRATION_MINUTES = 60 * 24 * 7  # 7 jours
JWT_ALGORITHM = "HS256"
JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
```

**Durée de vie du token** : 7 jours OU fermeture du navigateur (le premier des deux)

## Tests de Validation

### Test 1 : Login et Persistence
- [x] Login réussi avec admin/admin
- [x] Token présent dans `sessionStorage` (DevTools > Application > Session Storage)
- [x] Token absent de `localStorage`
- [x] Navigation fonctionnelle
- [x] Rafraîchissement page maintient l'authentification

### Test 2 : Fermeture Navigateur
- [x] Login réussi
- [x] Fermeture complète du navigateur
- [x] Réouverture → Redirection vers `/login`
- [x] Token effacé (vérification DevTools)

### Test 3 : Migration Backward Compatibility
- [x] Token manuel ajouté dans `localStorage` (DevTools Console)
- [x] Rafraîchissement page
- [x] Token migré vers `sessionStorage`
- [x] `localStorage` nettoyé
- [x] Message de migration dans console : `🔄 Migrating access_token...`

### Test 4 : Logout Manuel
- [x] Login réussi
- [x] Clic sur "Déconnexion"
- [x] `sessionStorage` vide
- [x] Redirection vers `/login`

### Test 5 : PDF Viewer avec Authentification
- [x] Login réussi
- [x] Message chat envoyé
- [x] Clic sur "Voir le PDF annoté"
- [x] PDF chargé sans erreur 401

### Test 6 : Erreur 401 (Token Expiré)
- [x] Token invalide dans `sessionStorage`
- [x] Requête API déclenchée
- [x] Token supprimé automatiquement
- [x] Redirection vers `/login`

## Déploiement

### Étapes de Déploiement

```bash
# 1. Rebuild frontend
cd frontend
npm run build

# 2. Rebuild container Docker
docker-compose build ragfab-frontend

# 3. Restart service
docker-compose up -d ragfab-frontend

# 4. Vérifier logs
docker-compose logs -f ragfab-frontend
```

### Rollback si Nécessaire

```bash
# Option 1 : Git revert
git revert HEAD
docker-compose restart ragfab-frontend

# Option 2 : Rollback manuel
# Remplacer sessionStorage → localStorage dans les 3 fichiers
```

## Métriques de Sécurité

| Métrique | Avant | Après | Amélioration |
|----------|-------|-------|--------------|
| Durée max session | 7 jours | Session navigateur | ✅ Limitée |
| Persistence après fermeture | Oui | Non | ✅ Sécurisé |
| Risque d'accès non autorisé | Moyen | Faible | ✅ Réduit |
| Isolation multi-onglets | Non | Oui | ✅ Renforcé |

## Limitations Connues

1. **Multi-onglets non synchronisés** : Logout dans un onglet n'affecte pas les autres
   - **Impact** : Faible (comportement standard pour sessionStorage)
   - **Amélioration possible** : Utiliser BroadcastChannel API (non prioritaire)

2. **Pas de "Remember Me"** : Tous les logins sont session-only
   - **Impact** : Moyen (les utilisateurs doivent se reconnecter à chaque session)
   - **Amélioration possible** : Ajouter une checkbox "Se souvenir de moi" (future feature)

## Améliorations Futures (Optionnelles)

### 1. Cross-Tab Logout (BroadcastChannel API)
**Effort** : 1 heure
**Bénéfice** : Logout dans un onglet déconnecte tous les onglets
**Priorité** : Basse (à implémenter si demandé par les utilisateurs)

### 2. "Remember Me" Checkbox
**Effort** : 2 heures
**Bénéfice** : Utilisateurs peuvent choisir entre session-only et persistent
**Priorité** : Moyenne (améliore UX sans compromettre sécurité)

### 3. Session Timeout Warning
**Effort** : 3 heures
**Bénéfice** : Avertir l'utilisateur avant expiration du token
**Priorité** : Basse (nice-to-have)

## Contacts

**Implémenté par** : Claude Code (claude.ai/code)
**Date** : 2025-01-09
**Révision** : v1.0

**Questions ou problèmes** : Consulter le plan détaillé dans `/Users/famatulli/.claude/plans/graceful-conjuring-truffle.md`

---

## Checklist de Validation Post-Déploiement

### Semaine 1
- [ ] Surveiller les plaintes utilisateurs sur "trop de logins"
- [ ] Vérifier les logs console pour messages de migration
- [ ] Confirmer absence d'erreurs 401 inattendues

### Semaine 2-4
- [ ] Vérifier que tous les utilisateurs ont migré (aucun token dans localStorage)
- [ ] Considérer suppression de `migrateTokenToSessionStorage()` après 30 jours

### Mois 2-3
- [ ] Évaluer feedback utilisateur
- [ ] Décider si "Remember Me" est nécessaire
- [ ] Planifier améliorations futures si besoin

---

**Status** : ✅ Migration complétée et testée
**Risque** : Faible
**Impact utilisateur** : Positif (sécurité renforcée)
