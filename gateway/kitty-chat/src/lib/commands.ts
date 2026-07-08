import { House, MessageSquare, CheckSquare, Terminal, Wrench, Plus, PanelLeft, Flag, FileText, Plug, Bot, Image, Settings, type LucideIcon } from 'lucide-react';
import type { Chat } from '@/lib/types';
import type { GatewayProject } from '@/lib/gateway';

export interface CommandItem {
  id: string;
  label: string;
  icon: LucideIcon;
  shortcut?: string;
  onSelect: () => void;
}

export interface CommandGroupDef {
  id: string;
  heading: string;
  commands: CommandItem[];
}

export function getGlobalCommands(actions: {
  onNewChat: () => void;
  onToggleSidebar: () => void;
}): CommandGroupDef {
  return {
    id: 'global-actions',
    heading: 'Actions',
    commands: [
      {
        id: 'new-chat',
        label: 'New chat',
        icon: Plus,
        shortcut: 'N',
        onSelect: actions.onNewChat,
      },
      {
        id: 'toggle-sidebar',
        label: 'Toggle sidebar',
        icon: PanelLeft,
        onSelect: actions.onToggleSidebar,
      },
    ],
  };
}

export function getViewCommands(onViewChange: (view: string) => void): CommandGroupDef {
  const views = [
    { id: 'home', label: 'home', icon: House },
    { id: 'chat', label: 'chat', icon: MessageSquare },
    { id: 'projects', label: 'projects', icon: Flag },
    { id: 'docs', label: 'documents', icon: FileText },
    { id: 'providers', label: 'providers', icon: Plug },
    { id: 'agents', label: 'agents', icon: Bot },
    { id: 'images', label: 'image lab', icon: Image },
    { id: 'settings', label: 'settings', icon: Settings },
    { id: 'tasks', label: 'tasks', icon: CheckSquare },
    { id: 'tools', label: 'tools', icon: Wrench },
    { id: 'terminal', label: 'terminal', icon: Terminal },
  ];

  return {
    id: 'views',
    heading: 'Go to',
    commands: views.map(v => ({
      id: `view-${v.id}`,
      label: v.label,
      icon: v.icon,
      onSelect: () => onViewChange(v.id),
    })),
  };
}

export function getChatCommands(chats: Chat[], onSelectChat: (id: string) => void): CommandGroupDef | null {
  const recentChats = [...chats]
    .filter(c => c.messages.length > 0)
    .sort((a, b) => +new Date(b.updatedAt) - +new Date(a.updatedAt))
    .slice(0, 8);

  if (recentChats.length === 0) return null;

  return {
    id: 'recent-chats',
    heading: 'Recent chats',
    commands: recentChats.map(c => ({
      id: `chat-${c.id}`,
      label: c.title || 'Untitled chat',
      icon: MessageSquare,
      onSelect: () => onSelectChat(c.id),
    })),
  };
}

export function getProjectCommands(projects: GatewayProject[], onViewChange: (view: string) => void): CommandGroupDef | null {
  const activeProjects = projects.filter(p => p.status === 'active');
  if (activeProjects.length === 0) return null;

  return {
    id: 'active-projects',
    heading: 'Active projects',
    commands: activeProjects.map(p => ({
      id: `project-${p.id}`,
      label: p.name,
      icon: Flag,
      onSelect: () => onViewChange('projects'),
    })),
  };
}
