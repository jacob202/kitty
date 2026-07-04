import type { GatewayBrief, GatewayHeadline, GatewayTodo } from '@/lib/gateway'
import type { PriorityItem } from '@/components/TodayCompass'

export function greetingTime(): string {
  const h = new Date().getHours()
  if (h < 5) return 'still up'
  if (h < 12) return 'good morning'
  if (h < 17) return 'good afternoon'
  if (h < 21) return 'good evening'
  return 'late night'
}

export function headlineText(h: string | GatewayHeadline): string {
  return typeof h === 'string' ? h : h.title
}

export function activeTodos(todos: GatewayTodo[]): GatewayTodo[] {
  return todos.filter(t => t.status === 'pending' || t.status === 'in_progress')
}

export function buildCompassItems(
  brief: GatewayBrief | null | undefined,
  todos: GatewayTodo[],
  onPrompt: (text: string) => void,
): PriorityItem[] {
  const items: PriorityItem[] = []
  const open = activeTodos(todos)

  if (brief?.intention?.trim()) {
    items.push({
      id: 'intention',
      title: brief.intention.trim(),
      description: brief.memory_snippet?.slice(0, 120) || undefined,
      priority: 'high',
      icon: '🎯',
      onSelect: () => onPrompt(brief.intention!.trim()),
    })
  }

  brief?.headlines?.slice(0, 4).forEach((headline, index) => {
    const title = headlineText(headline)
    if (!title) return
    items.push({
      id: `headline-${index}`,
      title,
      description: typeof headline === 'object' ? headline.snippet?.slice(0, 120) : undefined,
      priority: index === 0 ? 'medium' : 'low',
      icon: '📰',
    })
  })

  open.slice(0, 3).forEach(todo => {
    items.push({
      id: `todo-${todo.id}`,
      title: todo.content,
      description: todo.active_form || undefined,
      priority: todo.status === 'in_progress' ? 'high' : 'medium',
      icon: '☐',
      onSelect: () => onPrompt(todo.content),
    })
  })

  return items
}
