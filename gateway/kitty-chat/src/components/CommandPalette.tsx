'use client'
import { useEffect, useState } from 'react'
import { Command } from 'cmdk'
import type { LucideIcon } from 'lucide-react'
import type { Chat } from '@/lib/types'
import { useProjects } from '@/lib/queries'
import { getGlobalCommands, getViewCommands, getChatCommands, getProjectCommands, type CommandGroupDef } from '@/lib/commands'

interface Props {
  chats: Chat[]
  onNewChat: () => void
  onSelectChat: (id: string) => void
  onViewChange: (view: string) => void
  onToggleSidebar: () => void
}

export function CommandPalette({
  chats,
  onNewChat,
  onSelectChat,
  onViewChange,
  onToggleSidebar,
}: Props) {
  const [open, setOpen] = useState(false)
  const projectsQuery = useProjects()

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        const target = e.target as HTMLElement | null
        const inEditable = !!target?.closest('input, textarea, [contenteditable="true"]')
        if (inEditable && !open) return
        e.preventDefault()
        setOpen(prev => !prev)
      } else if (e.key === 'Escape') {
        setOpen(false)
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open])

  const close = () => setOpen(false)
  const fire = (fn: () => void) => () => {
    fn()
    close()
  }

  if (!open) return null

  const globalCommands = getGlobalCommands({ onNewChat, onToggleSidebar })
  const viewCommands = getViewCommands(onViewChange)
  const chatCommands = getChatCommands(chats, onSelectChat)
  const projectCommands = getProjectCommands(projectsQuery.data ?? [], onViewChange)

  const groups: CommandGroupDef[] = [globalCommands, viewCommands]
  if (chatCommands) groups.push(chatCommands)
  if (projectCommands) groups.push(projectCommands)

  return (
    <div
      onClick={close}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0, 0, 0, 0.6)',
        zIndex: 1000,
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'center',
        paddingTop: '12vh',
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          width: 520,
          maxWidth: 'calc(100vw - 40px)',
          background: 'var(--surface)',
          border: '1px solid var(--border)',
          borderRadius: 4,
          boxShadow: '4px 4px 0 var(--ink-deep)',
          overflow: 'hidden',
        }}
      >
        <Command label="Command palette" loop>
          <Command.Input
            autoFocus
            placeholder="Type a command or search…"
            style={{
              width: '100%',
              border: 'none',
              borderBottom: '1px solid var(--border)',
              background: 'transparent',
              padding: '14px 16px',
              fontFamily: 'var(--font-ui)',
              fontSize: 14,
              color: 'var(--text)',
              outline: 'none',
            }}
          />
          <Command.List style={{ maxHeight: 320, overflowY: 'auto', padding: 6 }}>
            <Command.Empty style={emptyStyle}>No results.</Command.Empty>

            {groups.map(group => (
              <Command.Group key={group.id} heading={group.heading} style={groupStyle}>
                {group.commands.map(cmd => (
                  <Item
                    key={cmd.id}
                    icon={cmd.icon}
                    label={cmd.label}
                    shortcut={cmd.shortcut}
                    onSelect={fire(cmd.onSelect)}
                  />
                ))}
              </Command.Group>
            ))}
          </Command.List>
        </Command>
      </div>
    </div>
  )
}

function Item({
  icon: Icon,
  label,
  shortcut,
  onSelect,
}: {
  icon: LucideIcon
  label: string
  shortcut?: string
  onSelect: () => void
}) {
  return (
    <Command.Item
      onSelect={onSelect}
      style={itemStyle}
      className="cmdk-item"
    >
      <Icon size={14} />
      <span style={{ flex: 1 }}>{label}</span>
      {shortcut && <kbd style={kbdStyle}>{shortcut}</kbd>}
    </Command.Item>
  )
}

const groupStyle: React.CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  letterSpacing: '0.1em',
  color: 'var(--text-muted)',
  textTransform: 'lowercase',
}

const itemStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 10,
  padding: '8px 10px',
  fontFamily: 'var(--font-ui)',
  fontSize: 13,
  color: 'var(--text)',
  borderRadius: 4,
  cursor: 'pointer',
}

const emptyStyle: React.CSSProperties = {
  padding: '20px 10px',
  textAlign: 'center',
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--text-muted)',
}

const kbdStyle: React.CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  padding: '1px 5px',
  border: '1px solid var(--border)',
  borderRadius: 3,
  color: 'var(--text-muted)',
  background: 'var(--surface-mid)',
}
