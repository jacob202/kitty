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
  updateCronSchedule,
  deleteCronSchedule,
  toggleCronSchedule,
  type CronScheduleType,
  // image
  fetchImageStatus,
  generateImage,
  fetchImageHistory,
  // state / actions / inbox
  fetchStateChanges,
  fetchActions,
  approveAction,
  rejectAction,
  fetchNeedsJacob,
  // payload types used by optimistic updates
  type GatewayTodo,
  type GatewayLoopsPayload,
  type GatewayInsightsPayload,
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
    // Optimistic: flip the row to completed instantly so the user sees feedback.
    onMutate: async (id) => {
      await qc.cancelQueries({ queryKey: ['todos'] })
      const previous = qc.getQueryData<GatewayTodo[]>(['todos'])
      qc.setQueryData<GatewayTodo[]>(['todos'], (old) =>
        old?.map((t) => (t.id === id ? { ...t, status: 'completed' } : t)) ?? old
      )
      return { previous }
    },
    onError: (_err, _id, ctx) => {
      if (ctx?.previous !== undefined) qc.setQueryData(['todos'], ctx.previous)
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ['todos'] }),
  })
}

export function useDeleteTodo() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteGatewayTodo(id),
    // Optimistic: drop the row from the list instantly.
    onMutate: async (id) => {
      await qc.cancelQueries({ queryKey: ['todos'] })
      const previous = qc.getQueryData<GatewayTodo[]>(['todos'])
      qc.setQueryData<GatewayTodo[]>(['todos'], (old) =>
        old?.filter((t) => t.id !== id) ?? old
      )
      return { previous }
    },
    onError: (_err, _id, ctx) => {
      if (ctx?.previous !== undefined) qc.setQueryData(['todos'], ctx.previous)
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ['todos'] }),
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
    // Optimistic: flip running ↔ paused immediately. Real status comes back on refetch.
    onMutate: async (loopId) => {
      await qc.cancelQueries({ queryKey: ['loops'] })
      const previous = qc.getQueryData<GatewayLoopsPayload>(['loops'])
      qc.setQueryData<GatewayLoopsPayload>(['loops'], (old) => {
        if (!old) return old
        return {
          ...old,
          loops: old.loops.map((l) => {
            if (l.loop_id !== loopId) return l
            if (l.status === 'running') return { ...l, status: 'paused' }
            if (l.status === 'paused') return { ...l, status: 'running' }
            return l
          }),
        }
      })
      return { previous }
    },
    onError: (_err, _id, ctx) => {
      if (ctx?.previous !== undefined) qc.setQueryData(['loops'], ctx.previous)
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ['loops'] }),
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
    // Optimistic: drop the insight from the feed instantly. Patches every
    // ['insights', limit] cache entry so any active limit picks it up.
    onMutate: async (id) => {
      await qc.cancelQueries({ queryKey: ['insights'] })
      const previous = qc.getQueriesData<GatewayInsightsPayload>({ queryKey: ['insights'] })
      qc.setQueriesData<GatewayInsightsPayload>({ queryKey: ['insights'] }, (old) => {
        if (!old) return old
        return { ...old, insights: old.insights.filter((i) => i.insight_id !== id) }
      })
      return { previous }
    },
    onError: (_err, _id, ctx) => {
      ctx?.previous?.forEach(([key, value]) => {
        if (value !== undefined) qc.setQueryData(key, value)
      })
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ['insights'] }),
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

export function useUpdateCronSchedule() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (args: { id: string; name: string; action: string; scheduleType: CronScheduleType; scheduleValue: string }) =>
      updateCronSchedule(args.id, args.name, args.action, args.scheduleType, args.scheduleValue),
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

export function useStateChanges() {
  return useQuery({
    queryKey: ['state', 'changes'],
    queryFn: fetchStateChanges,
    refetchInterval: 60_000,
    retry: false,
  })
}

export function useActions(status?: string) {
  return useQuery({
    queryKey: ['actions', status ?? 'all'],
    queryFn: () => fetchActions(status),
    refetchInterval: 30_000,
    retry: false,
  })
}

export function useApproveAction() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => approveAction(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['actions'] }),
  })
}

export function useRejectAction() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => rejectAction(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['actions'] }),
  })
}

// ── Inbox triage (needs_jacob) ────────────────────────────────────────────────

export function useNeedsJacob() {
  return useQuery({
    queryKey: ['inbox', 'needs_jacob'],
    queryFn: () => fetchNeedsJacob(),
    refetchInterval: 60_000,
    retry: false,
  })
}
