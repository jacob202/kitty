import type { Chat } from '@/lib/types'
import type { GatewayBrief, GatewayHeadline, GatewayTodo, GatewayWeather } from '@/lib/gateway'
import type { PriorityItem } from '@/components/TodayCompass'

export const USER_DISPLAY_NAME = 'jacob'

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

export function focusTodo(todos: GatewayTodo[]): GatewayTodo | undefined {
  const open = activeTodos(todos)
  return open.find(t => t.status === 'in_progress') ?? open[0]
}

export function weatherFromHeadlines(headlines: GatewayBrief['headlines'] | undefined): string | null {
  if (!headlines?.length) return null
  const match = headlines.find(h => {
    const text = headlineText(h).toLowerCase()
    return text.includes('weather') || text.includes('forecast') || text.includes('°')
  })
  return match ? headlineText(match) : null
}

export function formatGatewayWeather(weather: GatewayWeather | null | undefined): string | null {
  if (!weather || weather.error) return null
  const desc = weather.description?.trim()
  const temp = weather.temp_c
  if (desc && temp != null) return `${desc}, ${temp}°C`
  if (desc) return desc
  if (temp != null) return `${temp}°C`
  return null
}

export function resolveWeatherText(
  liveWeather: GatewayWeather | null | undefined,
  brief: GatewayBrief | null | undefined,
): string | null {
  return formatGatewayWeather(liveWeather) ?? weatherFromHeadlines(brief?.headlines)
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

export function gatewayBriefIsLive(brief: GatewayBrief | null | undefined): boolean {
  if (!brief) return false
  if (brief.error) return false
  return true
}

export function recentChatsWithMessages(chats: Chat[]): Chat[] {
  return [...chats]
    .filter(c => c.messages.length > 0)
    .sort((a, b) => b.updatedAt.getTime() - a.updatedAt.getTime())
    .slice(0, 6)
}
