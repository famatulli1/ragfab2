import { Plus, Settings } from 'lucide-react';

interface SidebarHeaderProps {
  onNewConversation: () => void;
  onOpenSettings: () => void;
}

export default function SidebarHeader({
  onNewConversation,
  onOpenSettings,
}: SidebarHeaderProps) {
  return (
    <div className="p-4 border-b border-gray-700 flex items-center gap-2">
      <button
        onClick={onNewConversation}
        className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg transition-colors"
      >
        <Plus size={20} />
        <span>Nouvelle conversation</span>
      </button>
      <button
        onClick={onOpenSettings}
        className="p-2 hover:bg-gray-800 rounded-lg transition-colors"
        title="Paramètres des conversations"
      >
        <Settings size={20} />
      </button>
    </div>
  );
}
