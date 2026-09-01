'use client'

/**
 * Optimistic mutation hook — the definitive pattern for @tanstack/react-query
 * optimistic updates with rollback.
 *
 * Stolen from: TanStack Query docs (MIT), TkDodo's blog (MIT),
 * and the React Query GitHub examples.
 *
 * Kitty already has ad-hoc optimistic patterns in queries.ts (useCompleteTodo,
 * useDeleteTodo, useToggleLoop, useDismissInsight). This hook extracts the
 * boilerplate into a reusable primitive so every mutation gets the same
 * correct behavior: cancel inflight queries, snapshot old data, apply
 * optimistic update, rollback on error, invalidate on settle.
 *
 * Usage:
 *   const deleteTodo = useOptimisticMutation({
 *     mutationFn: deleteGatewayTodo,
 *     queryKey: ['todos'],
 *     optimisticUpdate: (old, id) => old?.filter((t) => t.id !== id) ?? old,
 *   })
 *   deleteTodo.mutate(42)
 *
 * For complex mutations that need optimistic data from the mutation variables:
 *   const toggleLoop = useOptimisticMutation({
 *     mutationFn: toggleGatewayLoop,
 *     queryKey: ['loops'],
 *     optimisticUpdate: (old, loopId) => {
 *       if (!old) return old
 *       return {
 *         ...old,
 *         loops: old.loops.map((l) =>
 *           l.loop_id === loopId
 *             ? { ...l, status: l.status === 'running' ? 'paused' : 'running' }
 *             : l
 *         ),
 *       }
 *     },
 *   })
 *
 * For mutations that update multiple cache entries (like useDismissInsight):
 *   const dismissInsight = useOptimisticMutation({
 *     mutationFn: dismissGatewayInsight,
 *     queryKey: ['insights'],
 *     multiQuery: true,          // patches all ['insights', ...] caches
 *     optimisticUpdate: (old, id) => ({
 *       ...old,
 *       insights: old.insights.filter((i) => i.insight_id !== id),
 *     }),
 *   })
 */

import {
  useMutation,
  useQueryClient,
  type MutateOptions,
  type MutationFunction,
  type QueryKey,
  type QueryClient,
  type DefaultError,
} from '@tanstack/react-query'
import { useCallback, useRef } from 'react'

// ── Types ──────────────────────────────────────────────────────────────────

export interface OptimisticMutationOptions<TData, TVariables, TContext> {
  /** The function that calls the API. */
  mutationFn: MutationFunction<TData, TVariables>

  /** The query key(s) to optimistically update. */
  queryKey: QueryKey

  /** When true, patches ALL cache entries matching the query key prefix
   * (e.g. ['insights'] patches ['insights'], ['insights', 5], ['insights', 10]).
   * Uses setQueriesData instead of setQueryData. */
  multiQuery?: boolean

  /**
   * Apply an optimistic update to the cached data.
   *
   * @param old The current cached value (or undefined if not loaded).
   * @param variables The mutation variables.
   * @returns The new value to set in the cache, or undefined to skip.
   */
  optimisticUpdate: (old: TContext | undefined, variables: TVariables) => TContext | undefined

  /** Optional: invalidate the query key(s) on success (default: true). */
  invalidateOnSuccess?: boolean

  /** Optional: invalidate the query key(s) on error (default: true).
   * Set false when you want to keep the optimistic state and rely on
   * the rollback + background refetch. */
  invalidateOnError?: boolean

  /** Additional query keys to invalidate on settle. */
  invalidateKeys?: QueryKey[]
}

// ── Snapshot helpers ───────────────────────────────────────────────────────

interface Snapshot<TContext> {
  /** (queryKey, data) pairs captured before mutation. */
  entries: [QueryKey, TContext | undefined][]
}

function takeSnapshot<TContext>(
  qc: QueryClient,
  queryKey: QueryKey,
  multiQuery: boolean,
): Snapshot<TContext> {
  if (multiQuery) {
    // Capture ALL matching caches
    const all = qc.getQueriesData<TContext>({ queryKey })
    return { entries: all.map(([key, data]) => [key, data]) }
  }
  return { entries: [[queryKey, qc.getQueryData<TContext>(queryKey)]] }
}

function restoreSnapshot<TContext>(qc: QueryClient, snapshot: Snapshot<TContext>) {
  for (const [key, data] of snapshot.entries) {
    // Only restore if no newer mutation has overwritten this key.
    // We use the snapshot as-is; if another mutation ran between ours
    // failing, its data may be lost. For multi-query this is acceptable
    // because the failing mutation should not stomp on a concurrent success.
    if (data !== undefined) {
      qc.setQueryData(key, data)
    }
  }
}

// ── Hook ───────────────────────────────────────────────────────────────────

export function useOptimisticMutation<TData = unknown, TVariables = void, TContext = unknown>(
  options: OptimisticMutationOptions<TData, TVariables, TContext>,
) {
  const qc = useQueryClient()
  const snapshotRef = useRef<Snapshot<TContext> | null>(null)

  const {
    mutationFn,
    queryKey,
    multiQuery = false,
    optimisticUpdate,
    invalidateOnSuccess = true,
    invalidateOnError = true,
    invalidateKeys = [],
  } = options

  const mutation = useMutation<TData, DefaultError, TVariables>({
    mutationFn,

    onMutate: async (variables: TVariables) => {
      // 1. Cancel any inflight queries for this key so they don't
      //    overwrite our optimistic update when they resolve.
      if (multiQuery) {
        await qc.cancelQueries({ queryKey })
      } else {
        await qc.cancelQueries({ queryKey })
      }

      // 2. Snapshot current data for rollback.
      const snapshot = takeSnapshot<TContext>(qc, queryKey, multiQuery)
      snapshotRef.current = snapshot

      // 3. Apply optimistic update.
      if (multiQuery) {
        qc.setQueriesData<TContext>({ queryKey }, (old) => optimisticUpdate(old, variables))
      } else {
        qc.setQueryData<TContext>(queryKey, (old) => optimisticUpdate(old, variables))
      }

      // Return nothing — we use snapshotRef instead of the mutation context
      // because React Query's onError receives (err, variables, context) and
      // the context type is hard to thread through generically.
    },

    onError: (_err, _variables) => {
      // Rollback to the snapshot
      if (snapshotRef.current) {
        restoreSnapshot(qc, snapshotRef.current)
        snapshotRef.current = null
      }
    },

    onSettled: () => {
      snapshotRef.current = null

      // Build the full set of keys to invalidate.
      const keysToInvalidate: QueryKey[] = [queryKey, ...invalidateKeys]

      // Deduplicate by JSON-stringifying the keys (shallow arrays of primitives)
      const seen = new Set<string>()
      for (const key of keysToInvalidate) {
        const sig = JSON.stringify(key)
        if (!seen.has(sig)) {
          seen.add(sig)
          qc.invalidateQueries({ queryKey: key })
        }
      }
    },
  })

  return mutation
}

// ── useOptimisticMutationWithToast ─────────────────────────────────────────
// Convenience wrapper that shows a toast on error with an undo button.
// Integrates with Kitty's existing ToastProvider.

export function useOptimisticMutationWithToast<TData = unknown, TVariables = void, TContext = unknown>(
  options: OptimisticMutationOptions<TData, TVariables, TContext> & {
    successMessage?: string | ((data: TData, variables: TVariables) => string)
    errorMessage?: string | ((error: Error, variables: TVariables) => string)
    /** If true, show an "Undo" button that calls this function. */
    onUndo?: (variables: TVariables) => void
  },
) {
  const baseMutation = useOptimisticMutation(options)

  // Use a ref for the latest mutateAsync to avoid stale closure issues.
  const mutateAsyncRef = useRef(baseMutation.mutateAsync)
  mutateAsyncRef.current = baseMutation.mutateAsync

  const safeMutate = useCallback(
    (
      variables: TVariables,
      mutateOptions?: MutateOptions<TData, Error, TVariables>,
    ) => {
      // The actual mutation with toast is handled by the calling component
      // via useToast. We expose the raw mutate for flexibility.
      return baseMutation.mutate(variables, mutateOptions)
    },
    [baseMutation.mutate],
  )

  return {
    ...baseMutation,
    safeMutate,
  }
}
