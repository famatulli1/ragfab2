# Session Timeout System

**Date**: 2025-01-09
**Objectif**: Empêcher la reconnexion automatique après avoir quitté l'application

## Problème Résolu

### Symptôme
Après avoir ajouté une durée de session plus courte, l'utilisateur se reconnectait automatiquement en revenant sur ragbot, même après avoir quitté l'application.

### Cause Root
1. **SessionStorage persiste pendant toute la session du navigateur** : Tant que l'onglet n'est pas fermé, le token reste en `sessionStorage`, même si l'utilisateur navigue ailleurs et revient.
2. **Pas de vérification d'inactivité côté frontend** : Aucun mécanisme pour détecter et nettoyer les sessions inactives.
3. **Token JWT avec longue durée de vie** : 7 jours par défaut (10080 minutes), pas configurable via variable d'environnement.

## Solution Implémentée

### 1. Configuration JWT Backend ✅

**Fichier**: `web-api/app/config.py`

```python
# JWT_EXPIRATION_MINUTES est maintenant configurable via variable d'environnement
JWT_EXPIRATION_MINUTES: int = int(os.getenv("JWT_EXPIRATION_MINUTES", str(60 * 24 * 7)))  # 7 jours par défaut
```

**Fichier**: `.env.example`

```bash
# JWT Token Expiration (in minutes)
# Exemples:
#   - 30 = 30 minutes (session courte)
#   - 480 = 8 heures (journée de travail)
#   - 10080 = 7 jours (défaut)
# RECOMMANDÉ: 480 minutes (8h) pour équilibre sécurité/UX
JWT_EXPIRATION_MINUTES=10080
```

### 2. Système de Timeout d'Inactivité Frontend ✅

**Fichier**: `frontend/src/utils/sessionTimeout.ts`

#### Fonctionnalités

- **Timeout d'inactivité**: 30 minutes par défaut
- **Détection d'activité**: Mouse, keyboard, scroll, touch, click
- **Vérification périodique**: Toutes les minutes
- **Nettoyage automatique**: Supprime token + timestamp à l'expiration
- **Redirection**: Vers `/login` après expiration

#### API

```typescript
// Initialiser le système (appelé dans App.tsx au montage)
initSessionTimeout(): void

// Mettre à jour le timestamp de dernière activité (automatique)
updateLastActivity(): void

// Vérifier si la session a expiré
isSessionExpired(): boolean

// Nettoyer la session (token + timestamp)
clearSession(): void
```

### 3. Intégration dans l'Application ✅

**Fichier**: `frontend/src/App.tsx`

```typescript
import { initSessionTimeout } from './utils/sessionTimeout';

// Initialiser au montage du composant
useEffect(() => {
  initSessionTimeout();
}, []);
```

**Fichier**: `frontend/src/api/client.ts`

```typescript
import { clearSession, updateLastActivity } from '../utils/sessionTimeout';

// Login: Initialiser le timestamp d'activité
async login(credentials: LoginRequest): Promise<TokenResponse> {
  const { data } = await this.client.post<TokenResponse>('/api/auth/login', credentials);
  sessionStorage.setItem('access_token', data.access_token);
  updateLastActivity();  // ✅ Nouveau
  return data;
}

// Logout: Nettoyer complètement la session
async logout(): Promise<void> {
  await this.client.post('/api/auth/logout');
  clearSession();  // ✅ Nouveau (au lieu de sessionStorage.removeItem())
}

// Intercepteur 401: Nettoyer la session
this.client.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      clearSession();  // ✅ Nouveau
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);
```

## Flux de Session

### Connexion Réussie
```
1. User login → API /auth/login
2. Token JWT sauvegardé → sessionStorage
3. Timestamp d'activité initialisé → sessionStorage
4. Event listeners activés → mousedown, keydown, scroll, etc.
```

### Pendant la Session Active
```
1. User interagit → Event listener déclenché
2. Timestamp mis à jour → sessionStorage
3. Vérification périodique (1 min) → Toujours actif
```

### Session Inactive (30 min écoulées)
```
1. Vérification périodique détecte expiration
2. clearSession() appelé → Supprime token + timestamp
3. Redirection automatique → /login
4. Message console: "⏰ Session expirée par inactivité"
```

### User Quitte et Revient (< 30 min)
```
1. User revient sur ragbot
2. initSessionTimeout() vérifie timestamp
3. Temps écoulé < 30 min → Session encore active
4. Timestamp mis à jour → Session prolongée
```

### User Quitte et Revient (> 30 min)
```
1. User revient sur ragbot
2. initSessionTimeout() vérifie timestamp
3. Temps écoulé > 30 min → Session expirée
4. clearSession() appelé → Supprime token + timestamp
5. Redirection automatique → /login
6. Message console: "⏰ Session expirée par inactivité"
```

## Configuration Recommandée

### Production (Équilibre Sécurité/UX)
```bash
# Backend (.env)
JWT_EXPIRATION_MINUTES=480  # 8 heures (journée de travail)

# Frontend (sessionTimeout.ts)
INACTIVITY_TIMEOUT_MS = 30 * 60 * 1000  # 30 minutes
```

### Développement (Sessions Courtes pour Tests)
```bash
# Backend (.env)
JWT_EXPIRATION_MINUTES=30  # 30 minutes

# Frontend (sessionTimeout.ts)
INACTIVITY_TIMEOUT_MS = 5 * 60 * 1000  # 5 minutes
```

### Sécurité Élevée (Banque, Santé)
```bash
# Backend (.env)
JWT_EXPIRATION_MINUTES=60  # 1 heure

# Frontend (sessionTimeout.ts)
INACTIVITY_TIMEOUT_MS = 10 * 60 * 1000  # 10 minutes
```

## Déploiement

### Docker Compose
```bash
# 1. Configurer JWT_EXPIRATION_MINUTES dans .env
echo "JWT_EXPIRATION_MINUTES=480" >> .env

# 2. Rebuild et redémarrer
docker-compose up -d --build ragfab-frontend ragfab-api
```

### Coolify
```
1. Aller dans Settings → Environment Variables
2. Ajouter: JWT_EXPIRATION_MINUTES=480
3. Redéployer l'application
```

## Testing

### Test 1: Session Active
```bash
# 1. Se connecter
# 2. Utiliser l'application normalement (< 30 min)
# 3. Quitter et revenir immédiatement
# Résultat attendu: Toujours connecté
```

### Test 2: Session Inactive
```bash
# 1. Se connecter
# 2. Ne rien faire pendant 30+ minutes
# 3. Essayer d'interagir
# Résultat attendu: Redirection automatique vers /login
```

### Test 3: Quitter et Revenir (< Timeout)
```bash
# 1. Se connecter
# 2. Quitter l'application (aller sur Google par ex)
# 3. Revenir sur ragbot après 5 minutes
# Résultat attendu: Toujours connecté (< 30 min)
```

### Test 4: Quitter et Revenir (> Timeout)
```bash
# 1. Se connecter
# 2. Quitter l'application
# 3. Revenir sur ragbot après 35 minutes
# Résultat attendu: Redirection automatique vers /login
```

### Test 5: Token JWT Expiré (Backend)
```bash
# 1. Configurer JWT_EXPIRATION_MINUTES=5 (5 minutes)
# 2. Se connecter
# 3. Attendre 6 minutes sans fermer l'onglet
# 4. Essayer d'interagir
# Résultat attendu: HTTP 401 → clearSession() → /login
```

## Logs Console

### Connexion Réussie
```
✅ Connexion réussie pour: username
```

### Session Expirée (Inactivité)
```
⏰ Session expirée par inactivité
```

### Session Expirée (Vérification Périodique)
```
⏰ Session expirée par inactivité (vérification périodique)
```

### Token JWT Expiré (401)
```
⚠️ HTTP 401 Unauthorized
→ clearSession() appelé
→ Redirection vers /login
```

## Considérations Techniques

### Pourquoi sessionStorage et non localStorage ?

**sessionStorage** :
- ✅ Se vide automatiquement à la fermeture de l'onglet
- ✅ Isolé par onglet (chaque onglet = session indépendante)
- ✅ Plus sécurisé (pas de persistance entre sessions)
- ❌ Ne persiste pas entre onglets (mais c'est le comportement voulu ici)

**localStorage** :
- ❌ Persiste indéfiniment (même après fermeture)
- ❌ Partagé entre onglets (risque de confusion)
- ✅ Utile pour les préférences (theme, settings)

### Pourquoi 30 minutes d'inactivité ?

Basé sur les standards de sécurité :
- **OWASP** : 15-30 minutes pour applications sensibles
- **NIST** : 30 minutes maximum recommandé
- **Banking** : 10-15 minutes typiquement
- **Corporate** : 30-60 minutes

30 minutes est un bon équilibre pour une application corporate.

### Sécurité Multi-Couches

1. **Backend JWT** : Token expire côté serveur (JWT_EXPIRATION_MINUTES)
2. **Frontend Timeout** : Session expire par inactivité (30 min)
3. **SessionStorage** : Token se vide à la fermeture de l'onglet

Ces 3 couches offrent une protection robuste contre :
- **Token Replay Attacks** : Token expire côté serveur
- **Session Hijacking** : Timeout d'inactivité détecte sessions abandonnées
- **Cross-Tab Leaks** : SessionStorage isolé par onglet

## Migration Notes

### Breaking Changes
❌ Aucun breaking change

### Backward Compatibility
✅ Migration automatique de localStorage → sessionStorage (existing tokens)
✅ Users existants : Première déconnexion après 30 min d'inactivité

### Rollback Plan
Si problème détecté :
```bash
# 1. Commenter l'initialisation dans App.tsx
# useEffect(() => {
#   initSessionTimeout();
# }, []);

# 2. Rebuild frontend
docker-compose build ragfab-frontend

# 3. Redémarrer
docker-compose up -d ragfab-frontend
```

## Troubleshooting

### Symptôme: Déconnexion trop fréquente
**Cause**: Timeout trop court (30 min par défaut)
**Solution**: Augmenter `INACTIVITY_TIMEOUT_MS` dans `sessionTimeout.ts`

### Symptôme: Pas de déconnexion automatique
**Cause**: `initSessionTimeout()` pas appelé
**Solution**: Vérifier import et useEffect dans `App.tsx`

### Symptôme: Reconnexion automatique après quitter
**Cause**: Timeout d'inactivité > temps d'absence
**Solution**: Réduire `INACTIVITY_TIMEOUT_MS` (ex: 10 minutes)

### Symptôme: HTTP 401 trop fréquents
**Cause**: `JWT_EXPIRATION_MINUTES` trop court côté backend
**Solution**: Augmenter `JWT_EXPIRATION_MINUTES` dans `.env`

## Références

- **OWASP Session Management**: https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html
- **NIST Digital Identity Guidelines**: https://pages.nist.gov/800-63-3/sp800-63b.html#sec4
- **JWT Best Practices**: https://datatracker.ietf.org/doc/html/rfc8725

## Auteur

Claude Code - Session timeout implementation (2025-01-09)
