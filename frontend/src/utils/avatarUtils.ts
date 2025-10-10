/**
 * Palette de couleurs vives pour les avatars utilisateurs
 * Évite le blanc et les gris clairs pour garantir la lisibilité
 */
const AVATAR_COLORS = [
  '#3B82F6', // Bleu
  '#10B981', // Vert
  '#F59E0B', // Orange
  '#EF4444', // Rouge
  '#8B5CF6', // Violet
  '#EC4899', // Rose
  '#06B6D4', // Cyan
  '#84CC16', // Lime
];

/**
 * Génère une couleur cohérente pour un utilisateur basée sur son ID
 * @param userId - UUID de l'utilisateur
 * @returns Couleur hex (ex: '#3B82F6')
 */
export function getUserAvatarColor(userId: string): string {
  // Hash simple de l'UUID pour obtenir un index
  let hash = 0;
  for (let i = 0; i < userId.length; i++) {
    hash = userId.charCodeAt(i) + ((hash << 5) - hash);
    hash = hash & hash; // Convert to 32bit integer
  }

  // Modulo pour obtenir un index dans la palette
  const index = Math.abs(hash) % AVATAR_COLORS.length;
  return AVATAR_COLORS[index];
}

/**
 * Extrait la première lettre du prénom (ou username si pas de prénom)
 * @param firstName - Prénom de l'utilisateur
 * @param username - Nom d'utilisateur (fallback)
 * @returns Lettre majuscule (ex: 'J')
 */
export function getUserAvatarInitial(firstName: string | undefined, username: string): string {
  const name = firstName || username;
  return name.charAt(0).toUpperCase();
}
