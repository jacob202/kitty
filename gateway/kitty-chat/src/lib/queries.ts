'use client'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  // brief / models / search / weather (full payloads)
  fetchGatewayBrief,
  fetchGatewayModels,
  fetchGatewaySearch,
  fetchGatewayWeather,
  // todos
  fetchGatewayTodos,
  addGatewayTodo,
  completeGatewayTodo,
  deleteGatewayTodo,
  // loops / insights / prompts
  fetchGatewayLoops,
  toggleGatewayLoop,
  fetchGatewayInsights,
  dismissGatewayInsight,
  fetchGatewayPrompts,
  // monitors
  fetchGatewayMonitors,
  addGatewayMonitor,
  removeGatewayMonitor,
  // tasks
  fetchGatewayTasks,
  createGatewayTask,
  cancelGatewayTask,
  type TaskType,
  // agents
  fetchAgentSessions,
  spawnAgent,
  stopAgent,
  type AgentType,
  // cron
  fetchCronSchedules,
  fetchCronActions,
  createCronSchedule,
  deleteCronSchedule,
  toggleCronSchedule,
  type CronScheduleType,
  // image
  fetchImageStatus,
  generateImage,
  fetchImageHistory,
} from '@/lib/gateway'

// ── Dashboard payload queries ────────────────────────────────────────────────
// These keep the existing payload shape ({data, fromLiveGateway, error}) so
// callers see no change beyond wrapping in `useQuery`.

export function useGatewayBrief() {
  return useQuery({
    queryKey: ['brief'],
    queryFn: fetchGatewayBrief,
    refetchInterval: 5 * 60_000,
  })
}

export function useGatewayModels() {
  return useQuery({
    queryKey: ['models'],
    queryFn: fetchGatewayModels,
  })
}

export function useGatewaySearch(query: string, limit = 3) {
  return useQuery({
    queryKey: ['search', query, limit],
    queryFn: ({ signal }) => fetchGatewaySearch(query, limit, signal),
    enabled: query.trim().length > 0,
    staleTime: 30_000,
  })
}

export function useGatewayWeather() {
  return useQuery({
    queryKey: ['weather'],
    queryFn: fetchGatewayWeather,
    refetchInterval: 15 * 60_000,
  })
}

// ── Todos ────────────────────────────────────────────────────────────────────

export function useTodos() {
  return useQuery({ queryKey: ['todos'], queryFn: fetchGatewayTodos })
}

export function useAddTodo() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (content: string) => addGatewayTodo(content),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['todos'] }),
  })
}

export function useCompleteTodo() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => completeGatewayTodo(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['todos'] }),
  })
}

export function useDeleteTodo() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteGatewayTodo(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['todos'] }),
  })
}

// ── Loops / Insights ─────────────────────────────────────────────────────────

export function useLoops() {
  return useQuery({
    queryKey: ['loops'],
    queryFn: fetchGatewayLoops,
    refetchInterval: 30_000,
  })
}

export function useToggleLoop() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (loopId: string) => toggleGatewayLoop(loopId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['loops'] }),
  })
}

export function useInsights(limit = 10) {
  return useQuery({
    queryKey: ['insights', limit],
    queryFn: () => fetchGatewayInsights(limit),
    refetchInterval: 60_000,
  })
}

export function useDismissInsight() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => dismissGatewayInsight(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['insights'] }),
  })
}

export function usePrompts() {
  return useQuery({
    queryKey: ['prompts'],
    queryFn: fetchGatewayPrompts,
    staleTime: 5 * 60_000,
  })
}

// ── Monitors ────────────────────────────────────────────────────────────────

export function useMonitors() {
  return useQuery({
    queryKey: ['monitors'],
    queryFn: fetchGatewayMonitors,
    refetchInterval: 60_000,
  })
}

export function useAddMonitor() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ url, label }: { url: string; label: string }) => addGatewayMonitor(url, label),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['monitors'] }),
  })
}

export function useRemoveMonitor() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => removeGatewayMonitor(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['monitors'] }),
  })
}

// ── Tasks ───────────────────────────────────────────────────────────────────

export function useTasks(limit = 20) {
  return useQuery({
    queryKey: ['tasks', limit],
    queryFn: () => fetchGatewayTasks(limit),
    refetchInterval: 3_000,
  })
}

export function useCreateTask() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ goal, taskType }: { goal: string; taskType: TaskType }) =>
      createGatewayTask(goal, taskType),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['tasks'] }),
  })
}

export function useCancelTask() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => cancelGatewayTask(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['tasks'] }),
  })
}

// ── Agents ──────────────────────────────────────────────────────────────────

export function useAgentSessions(limit = 8) {
  return useQuery({
    queryKey: ['agents', limit],
    queryFn: () => fetchAgentSessions(limit),
    refetchInterval: 4_000,
  })
}

export function useSpawnAgent() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ goal, agentType }: { goal: string; agentType: AgentType }) =>
      spawnAgent(goal, agentType),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['agents'] }),
  })
}

export function useStopAgent() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (sessionId: number) => stopAgent(sessionId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['agents'] }),
  })
}

// ── Cron ────────────────────────────────────────────────────────────────────

export function useCronSchedules() {
  return useQuery({ queryKey: ['cron', 'schedules'], queryFn: fetchCronSchedules })
}

export function useCronActions() {
  return useQuery({ queryKey: ['cron', 'actions'], queryFn: fetchCronActions, staleTime: 5 * 60_000 })
}

export function useCreateCronSchedule() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (args: { name: string; action: string; scheduleType: CronScheduleType; scheduleValue: string }) =>
      createCronSchedule(args.name, args.action, args.scheduleType, args.scheduleValue),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['cron', 'schedules'] }),
  })
}

export function useDeleteCronSchedule() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => deleteCronSchedule(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['cron', 'schedules'] }),
  })
}

export function useToggleCronSchedule() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => toggleCronSchedule(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['cron', 'schedules'] }),
  })
}

// ── Image generation ────────────────────────────────────────────────────────

export function useImageStatus() {
  return useQuery({
    queryKey: ['image', 'status'],
    queryFn: fetchImageStatus,
    refetchInterval: 30_000,
  })
}

export function useImageHistory() {
  return useQuery({ queryKey: ['image', 'history'], queryFn: () => fetchImageHistory() })
}

export function useGenerateImage() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (prompt: string) => generateImage(prompt),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['image', 'history'] }),
  })
}
