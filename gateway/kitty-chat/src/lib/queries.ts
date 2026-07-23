'use client'
import { useQuery, useQueries, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  // brief / models / search / weather (full payloads)
  fetchGatewayBrief,
  fetchGatewayModels,
  fetchGatewayPersonality,
  updateGatewayPersonality,
  fetchGatewaySessionContext,
  fetchGatewayUsageSummary,
  fetchGatewayRuntimeManifest,
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
  snapshotState,
  fetchStateNow,
  runInboxTriage,
  // projects
  fetchProjects,
  fetchActiveProject,
  setActiveProject,
  fetchProjectNext,
  fetchProjectNextSteps,
  refreshProject,
  type GatewayProject,
  // deadlines
  fetchDeadlines,
  runDeadlineSweep,
  // cockpit health
  fetchGatewayHealth,
  fetchChatsPersistence,
  fetchGatewayTailnet,
  // repairs
  fetchRepairs,
  executeRepair,
  // builder control
  executeBuilderAction,
  // experts
  fetchExpertList,
  // knowledge
  fetchKnowledgeSources,
  searchKnowledge,
  ingestKnowledge,
  uploadCaptureFile,
  // providers
  fetchPlugins,
  setPluginEnabled,
  fetchMcpServers,
  fetchMcpTools,
  // payload types used by optimistic updates
  type GatewayTodo,
  type GatewayLoopsPayload,
  type GatewayInsightsPayload,
  type GatewayPersonality,
  type GatewayRuntimeManifest,
} from '@/lib/gateway'

// ── Dashboard payload queries ────────────────────────────────────────────────
// These keep the existing payload shape ({data, fromLiveGateway, error}) so
// callers see no change beyond wrapping in `useQuery`.

export function useGatewayBrief() {
  return useQuery({
    queryKey: ['brief'],
    queryFn: fetchGatewayBrief,
    // Brief can be slower than the health probe on a cold gateway. Retry and
    // refresh it quickly so one startup timeout does not pin the dashboard
    // into an offline state for five minutes.
    refetchInterval: 30_000,
    staleTime: 10_000,
  })
}

export function useGatewayModels() {
  return useQuery({
    queryKey: ['models'],
    queryFn: fetchGatewayModels,
    refetchInterval: 30_000,
    staleTime: 10_000,
  })
}

export function usePersonality() {
  return useQuery({
    queryKey: ['settings', 'personality'],
    queryFn: fetchGatewayPersonality,
    staleTime: 30_000,
  })
}

export function useUpdatePersonality() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: GatewayPersonality) => updateGatewayPersonality(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['settings', 'personality'] }),
  })
}

export function useSessionContext() {
  return useQuery({
    queryKey: ['session', 'context'],
    queryFn: fetchGatewaySessionContext,
    staleTime: 30_000,
  })
}

export function useUsageSummary() {
  return useQuery({
    queryKey: ['usage', 'summary'],
    queryFn: fetchGatewayUsageSummary,
    refetchInterval: 60_000,
  })
}

export function useGatewayRuntimeManifest(projectId?: number) {
  return useQuery({
    queryKey: ['runtime-manifest', projectId ?? null],
    queryFn: () => fetchGatewayRuntimeManifest(projectId),
    refetchInterval: (query) => hasActiveBuilderRun(query.state.data) ? 5_000 : 15_000,
    staleTime: 10_000,
  })
}

export function hasActiveBuilderRun(manifest: GatewayRuntimeManifest | undefined): boolean {
  const initiatives = manifest?.execution.builder.value?.initiatives
  return initiatives?.some((initiative) => initiative.packets.some((packet) => (
    packet.run?.state === 'starting'
    || packet.run?.state === 'running'
    || packet.run?.state === 'cancel_requested'
  ))) ?? false
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
  return useQuery({
    queryKey: ['todos'],
    queryFn: fetchGatewayTodos,
    refetchInterval: 30_000,
    staleTime: 10_000,
  })
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
    mutationFn: (args: string | { prompt: string; engine: string }) =>
      typeof args === 'string' ? generateImage(args) : generateImage(args.prompt, args.engine),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['image', 'history'] }),
  })
}

export function useStateChanges() {
  return useQuery({
    queryKey: ['state', 'changes'],
    queryFn: fetchStateChanges,
    refetchInterval: 30_000,
    retry: 2,
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

export function useSnapshotState() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => snapshotState(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['state'] }),
  })
}

export function useStateNow() {
  return useQuery({
    queryKey: ['state', 'now'],
    queryFn: fetchStateNow,
    refetchInterval: 30_000,
    retry: 2,
  })
}

export function useRunInboxTriage() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (limit?: number) => runInboxTriage(limit),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['state'] })
      qc.invalidateQueries({ queryKey: ['inbox'] })
    },
  })
}

// ── Projects ────────────────────────────────────────────────────────────────

export function useProjects() {
  return useQuery({ queryKey: ['projects'], queryFn: fetchProjects, refetchInterval: 60_000 })
}

export function useActiveProject() {
  return useQuery({ queryKey: ['active-project'], queryFn: fetchActiveProject, staleTime: 30_000 })
}

export function useSetActiveProject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (projectId: number) => setActiveProject(projectId),
    onSuccess: (payload) => {
      qc.setQueryData(['active-project'], payload)
      void qc.invalidateQueries({ queryKey: ['runtime-manifest'] })
    },
  })
}

export function useProjectNext(projectId: number) {
  return useQuery({
    queryKey: ['projects', projectId, 'next'],
    queryFn: () => fetchProjectNext(projectId),
    staleTime: 60_000,
  })
}

export function useRefreshProject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (projectId: number) => refreshProject(projectId),
    onSettled: (_data, _err, projectId) => {
      qc.invalidateQueries({ queryKey: ['projects'] })
      qc.invalidateQueries({ queryKey: ['projects', projectId, 'next'] })
    },
  })
}

// ── Deadlines (urgent paper) ──────────────────────────────────────────────────

export function useDeadlines(status = 'open') {
  return useQuery({
    queryKey: ['deadlines', status],
    queryFn: () => fetchDeadlines(status),
    refetchInterval: 60_000,
    retry: false,
  })
}

export function useDeadlineSweep() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => runDeadlineSweep(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['deadlines'] }),
  })
}

// ── Knowledge (Documents) ───────────────────────────────────────────────────

export function useKnowledgeSources() {
  return useQuery({ queryKey: ['knowledge', 'sources'], queryFn: fetchKnowledgeSources })
}

export function useKnowledgeSearch(q: string, limit = 8) {
  return useQuery({
    queryKey: ['knowledge', 'search', q, limit],
    queryFn: () => searchKnowledge(q, limit),
    enabled: q.trim().length > 0,
    staleTime: 30_000,
  })
}

export function useIngestKnowledge() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { path?: string; url?: string; collection?: string; tags?: string[] }) =>
      ingestKnowledge(body),
    onSettled: () => qc.invalidateQueries({ queryKey: ['knowledge', 'sources'] }),
  })
}

// ── Providers ───────────────────────────────────────────────────────────────

export function usePlugins() {
  return useQuery({ queryKey: ['plugins'], queryFn: fetchPlugins })
}

export function useTogglePlugin() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ name, enabled }: { name: string; enabled: boolean }) =>
      setPluginEnabled(name, enabled),
    onSettled: () => qc.invalidateQueries({ queryKey: ['plugins'] }),
  })
}

export function useMcpServers() {
  return useQuery({ queryKey: ['mcp', 'servers'], queryFn: fetchMcpServers })
}

export function useMcpTools() {
  return useQuery({ queryKey: ['mcp', 'tools'], queryFn: fetchMcpTools })
}

// ── Cockpit (Home) ──────────────────────────────────────────────────────────

export function useGatewayHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: fetchGatewayHealth,
    refetchInterval: 30_000,
  })
}

export function useRepairs() {
  return useQuery({
    queryKey: ['repairs'],
    queryFn: fetchRepairs,
    refetchInterval: 60_000,
    staleTime: 10_000,
  })
}

export function useExecuteRepair() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ repairId, actionKind, checkName }: { repairId: string; actionKind: string; checkName: string }) =>
      executeRepair(repairId, actionKind, checkName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['repairs'] })
    },
  })
}

export function useBuilderAction() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      action,
      initiativeId,
      packetId,
      reason,
    }: {
      action: string
      initiativeId?: string
      packetId?: string
      reason?: string
    }) => executeBuilderAction(action, initiativeId, packetId, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['runtime'] })
    },
  })
}

export function useExpertList() {
  return useQuery({
    queryKey: ['experts'],
    queryFn: fetchExpertList,
    staleTime: 300_000,
  })
}

export function useTailnet() {
  return useQuery({
    queryKey: ['network', 'tailnet'],
    queryFn: fetchGatewayTailnet,
    refetchInterval: 30_000,
    retry: false,
  })
}

export function useChatsPersistence() {
  return useQuery({
    queryKey: ['chats', 'persistence'],
    queryFn: fetchChatsPersistence,
    refetchInterval: 120_000,
  })
}

/** Life-first ordered next steps for the Home "What's Next" card (ADR 0016). */
export function useWhatsNextSteps() {
  return useQuery({
    queryKey: ['projects', 'next-steps'],
    queryFn: () => fetchProjectNextSteps(3),
    staleTime: 60_000,
  })
}

/** One next-step query per project, sharing the ['projects', id, 'next']
 *  cache entries with useProjectNext so ProjectsPanel and Home never
 *  double-fetch. */
export function useProjectNextSteps(projects: GatewayProject[]) {
  return useQueries({
    queries: projects.map(p => ({
      queryKey: ['projects', p.id, 'next'],
      queryFn: () => fetchProjectNext(p.id),
      staleTime: 60_000,
    })),
  })
}

export function useUploadCapture() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (file: File) => uploadCaptureFile(file),
    // Indexing runs as a gateway background task; the invalidation gives the
    // fast path, the sources card's refresh button covers the slow one.
    onSuccess: () => qc.invalidateQueries({ queryKey: ['knowledge', 'sources'] }),
  })
}

// ── Chat feedback ───────────────────────────────────────────────────────────

export type MessageFeedbackRating = 'up' | 'down'

export interface MessageFeedbackInput {
  chatId: string
  messageIndex: number
  rating: MessageFeedbackRating
}

export function useSubmitMessageFeedback() {
  return useMutation({
    mutationFn: async ({ chatId, messageIndex, rating }: MessageFeedbackInput) => {
      const controller = new AbortController()
      const timeoutId = window.setTimeout(() => controller.abort(), 8000)
      try {
        const response = await fetch('/proxy/feedback', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ chat_id: chatId, message_index: messageIndex, rating }),
          signal: controller.signal,
        })
        if (!response.ok) {
          throw new Error(`Gateway returned ${response.status} ${response.statusText}`.trim())
        }
        const payload = await response.json() as { ok?: unknown }
        if (payload.ok !== true) {
          throw new Error('Gateway /feedback returned an invalid acknowledgment')
        }
      } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') {
          throw new Error('Feedback request timed out — is the Kitty gateway running?')
        }
        throw error
      } finally {
        window.clearTimeout(timeoutId)
      }
    },
  })
}
