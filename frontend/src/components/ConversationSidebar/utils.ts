import type { ConversationWithStats, TimeGroup, GroupedConversations } from '../../types';

/**
 * Group conversations by time period
 */
export function groupConversationsByTime(
  conversations: ConversationWithStats[]
): GroupedConversations {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today.getTime() - 24 * 60 * 60 * 1000);
  const last7Days = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);
  const last30Days = new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000);

  const groups: GroupedConversations = {
    today: [],
    yesterday: [],
    last7days: [],
    last30days: [],
    older: [],
  };

  conversations.forEach((conv) => {
    const convDate = new Date(conv.updated_at);

    if (convDate >= today) {
      groups.today.push(conv);
    } else if (convDate >= yesterday) {
      groups.yesterday.push(conv);
    } else if (convDate >= last7Days) {
      groups.last7days.push(conv);
    } else if (convDate >= last30Days) {
      groups.last30days.push(conv);
    } else {
      groups.older.push(conv);
    }
  });

  return groups;
}

/**
 * Group conversations by universe
 */
export function groupConversationsByUniverse(
  conversations: ConversationWithStats[]
): Record<string, ConversationWithStats[]> {
  const groups: Record<string, ConversationWithStats[]> = {};

  conversations.forEach((conv) => {
    const key = conv.universe_id || 'no-universe';
    if (!groups[key]) {
      groups[key] = [];
    }
    groups[key].push(conv);
  });

  return groups;
}

/**
 * Get the label for a time group
 */
export function getTimeGroupLabel(group: TimeGroup): string {
  switch (group) {
    case 'today':
      return "Aujourd'hui";
    case 'yesterday':
      return 'Hier';
    case 'last7days':
      return '7 derniers jours';
    case 'last30days':
      return '30 derniers jours';
    case 'older':
      return 'Plus ancien';
    default:
      return '';
  }
}

/**
 * Format a date relative to now
 */
export function formatRelativeDate(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / (1000 * 60));
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffMins < 1) {
    return "A l'instant";
  } else if (diffMins < 60) {
    return `Il y a ${diffMins} min`;
  } else if (diffHours < 24) {
    return `Il y a ${diffHours}h`;
  } else if (diffDays < 7) {
    return `Il y a ${diffDays}j`;
  } else {
    return date.toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' });
  }
}

/**
 * Debounce function
 */
export function debounce<T extends (...args: any[]) => any>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: NodeJS.Timeout | null = null;

  return (...args: Parameters<T>) => {
    if (timeout) {
      clearTimeout(timeout);
    }
    timeout = setTimeout(() => {
      func(...args);
    }, wait);
  };
}
