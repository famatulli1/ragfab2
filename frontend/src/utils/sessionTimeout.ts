/**
 * Session Timeout Utility
 *
 * Gère l'expiration automatique de la session basée sur l'inactivité utilisateur.
 * Complète la sécurité JWT en ajoutant un timeout côté frontend.
 */

const INACTIVITY_TIMEOUT_MS = 30 * 60 * 1000; // 30 minutes par défaut
const LAST_ACTIVITY_KEY = 'last_activity';

/**
 * Met à jour le timestamp de dernière activité
 */
export function updateLastActivity(): void {
  sessionStorage.setItem(LAST_ACTIVITY_KEY, Date.now().toString());
}

/**
 * Vérifie si la session a expiré par inactivité
 * @returns true si la session a expiré, false sinon
 */
export function isSessionExpired(): boolean {
  const lastActivity = sessionStorage.getItem(LAST_ACTIVITY_KEY);

  if (!lastActivity) {
    // Pas de timestamp = première visite, initialiser
    updateLastActivity();
    return false;
  }

  const lastActivityTime = parseInt(lastActivity, 10);
  const now = Date.now();
  const elapsedTime = now - lastActivityTime;

  return elapsedTime > INACTIVITY_TIMEOUT_MS;
}

/**
 * Nettoie la session (token + timestamp)
 */
export function clearSession(): void {
  sessionStorage.removeItem('access_token');
  sessionStorage.removeItem(LAST_ACTIVITY_KEY);
}

/**
 * Initialise les listeners d'activité utilisateur
 * Met à jour le timestamp à chaque interaction (mouse, keyboard, touch)
 */
export function initSessionTimeout(): void {
  // Événements qui indiquent une activité utilisateur
  const activityEvents = ['mousedown', 'keydown', 'scroll', 'touchstart', 'click'];

  activityEvents.forEach(event => {
    document.addEventListener(event, updateLastActivity, { passive: true });
  });

  // Vérifier l'expiration à chaque chargement de page
  if (isSessionExpired()) {
    console.log('⏰ Session expirée par inactivité');
    clearSession();
    // Rediriger vers la page de connexion
    if (window.location.pathname !== '/admin') {
      window.location.href = '/admin';
    }
  } else {
    // Session active, mettre à jour le timestamp
    updateLastActivity();
  }

  // Vérifier périodiquement l'expiration (toutes les minutes)
  setInterval(() => {
    if (sessionStorage.getItem('access_token') && isSessionExpired()) {
      console.log('⏰ Session expirée par inactivité (vérification périodique)');
      clearSession();
      window.location.href = '/admin';
    }
  }, 60 * 1000); // Vérifier toutes les minutes
}

/**
 * Configure le timeout d'inactivité (en minutes)
 * @param minutes - Durée d'inactivité avant expiration
 */
export function setInactivityTimeout(minutes: number): void {
  // Cette fonction permet de configurer dynamiquement le timeout
  // Pour l'instant, le timeout est codé en dur dans INACTIVITY_TIMEOUT_MS
  // À implémenter si besoin de configuration dynamique
  console.log(`⚙️ Timeout d'inactivité: ${minutes} minutes`);
}
