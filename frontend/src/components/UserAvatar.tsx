import { getUserAvatarColor, getUserAvatarInitial } from '../utils/avatarUtils';
import type { User } from '../types';

interface UserAvatarProps {
  user: User;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export default function UserAvatar({ user, size = 'md', className = '' }: UserAvatarProps) {
  const color = getUserAvatarColor(user.id);
  const initial = getUserAvatarInitial(user.first_name, user.username);

  const sizeClasses = {
    sm: 'w-8 h-8 text-sm',
    md: 'w-10 h-10 text-base',
    lg: 'w-12 h-12 text-lg',
  };

  return (
    <div
      className={`${sizeClasses[size]} rounded-full flex items-center justify-center font-semibold text-white select-none ${className}`}
      style={{ backgroundColor: color }}
      title={`${user.first_name || ''} ${user.last_name || ''}`.trim() || user.username}
    >
      {initial}
    </div>
  );
}
