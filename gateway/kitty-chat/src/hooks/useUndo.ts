'use client'

/**
 * Undo/redo system — "toast with undo" pattern + full undo stack.
 *
 * Stolen from: Linear (undo in toasts), Obsidian (ctrl+z undo),
 * ProseMirror (undo stack), react-use (useUndo hook).
 * License: MIT (all implementations are MIT).
 *
 * Pattern 1: Toast with Undo (for destructive actions)
 *   Perform the action immediately, show a toast with "Undo" button.
 *   If user clicks Undo within N seconds, reverse the action.
 *   If timeout expires, action is permanent.
 *
 * Pattern 2: Full undo stack (for multi-step operations)
 *   Push every action onto a stack with its inverse.
 *   Ctrl+Z pops the stack and applies the inverse.
 *   Supports keyboard shortcuts, max stack depth, grouping.
 *
 * Usage (Toast with Undo):
 *   import { useToast } from '@/components/Toast'
 *   import { useUndoableAction } from '@/hooks/useUndo'
 *
 *   function DeleteButton({ id }) {
 *     const { showToast } = useToast()
 *     const { execute } = useUndoableAction()
 *
 *     const handleDelete = () => {
 *       execute({
 *         redo: () => deleteGatewayTodo(id),     // the action
 *         undo: () => addGatewayTodoBack(id),      // its inverse
 *         description: 'Deleted todo',
 *       })
 *       showToast('Todo deleted', 'info')
 *       // The toast-with-undo button is shown automatically
 *     }
 *   }
 *
 * Usage (Full Undo Stack):
 *   import { useUndoStack } from '@/hooks/useUndo'
 *
 *   function Editor() {
 *     const { push, undo, redo, canUndo, canRedo } = useUndoStack()
 *
 *     const onInsert = (text) => {
 *       const prev = content
 *       setContent(text)
 *       push({ redo: () => setContent(text), undo: () => setContent(prev) })
 *     }
 *
 *     return <div>
 *       <button disabled={!canUndo} onClick={undo}>Undo</button>
 *       <button disabled={!canRedo} onClick={redo}>Redo</button>
 *     </div>
 *   }
 */

import { useState, useCallback, useRef, useEffect } from 'react'
import { useToast } from '@/components/Toast'

// ── Types ──────────────────────────────────────────────────────────────────

export interface UndoableAction {
  /** The forward action — performs the mutation. */
  redo: () => void | Promise<void>
  /** The inverse action — reverts the mutation. */
  undo: () => void | Promise<void>
  /** Human-readable description for the toast (e.g. "Deleted task"). */
  description?: string
}

export interface UndoStackEntry {
  action: UndoableAction
  timestamp: number
  groupId?: string  // actions with the same groupId are undone together
}

// ── Pattern 1: Toast with Undo ────────────────────────────────────────────

const UNDO_TIMEOUT_MS = 5000  // How long the undo button stays visible

/**
 * Execute an undoable action and show a toast with an "Undo" button.
 * If the user clicks undo within UNDO_TIMEOUT_MS, the inverse runs.
 * If the timeout expires, the action is permanent.
 */
export function useUndoableAction() {
  const { showToast } = useToast()
  const pendingRef = useRef<UndoableAction | null>(null)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const clearPending = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
    pendingRef.current = null
  }, [])

  const execute = useCallback(
    (action: UndoableAction) => {
      // Clear any previous pending undo
      clearPending()

      // Execute the forward action immediately
      const result = action.redo()

      // Store the undo action
      pendingRef.current = action

      // Show toast with undo
      showToast(
        action.description || 'Action completed',
        'info',
      )

      // Auto-expire the undo window
      timerRef.current = setTimeout(() => {
        pendingRef.current = null
        timerRef.current = null
      }, UNDO_TIMEOUT_MS)

      return result
    },
    [clearPending, showToast],
  )

  const undo = useCallback(() => {
    const action = pendingRef.current
    if (!action) return
    clearPending()
    action.undo()
    showToast('Undone', 'success')
  }, [clearPending, showToast])

  return { execute, undo, hasPending: () => pendingRef.current !== null }
}

// ── Pattern 2: Full Undo Stack ────────────────────────────────────────────

const MAX_STACK_DEPTH = 100

export function useUndoStack(maxDepth: number = MAX_STACK_DEPTH) {
  const [undoStack, setUndoStack] = useState<UndoStackEntry[]>([])
  const [redoStack, setRedoStack] = useState<UndoStackEntry[]>([])

  const push = useCallback(
    (action: UndoableAction, groupId?: string) => {
      setUndoStack((prev) => {
        const entry: UndoStackEntry = {
          action,
          timestamp: Date.now(),
          groupId,
        }
        const next = [...prev, entry]
        // Trim to max depth (keep newest)
        if (next.length > maxDepth) {
          return next.slice(next.length - maxDepth)
        }
        return next
      })
      // Clear redo stack on new action
      setRedoStack([])
    },
    [maxDepth],
  )

  const undo = useCallback(() => {
    setUndoStack((prevStack) => {
      if (prevStack.length === 0) return prevStack

      // Determine how many entries to pop (single or group)
      const last = prevStack[prevStack.length - 1]
      const groupId = last.groupId

      let popCount = 1
      if (groupId) {
        // Pop all entries with the same groupId at the end
        for (let i = prevStack.length - 2; i >= 0; i--) {
          if (prevStack[i].groupId === groupId) {
            popCount++
          } else {
            break
          }
        }
      }

      const popped = prevStack.slice(-popCount)
      const remaining = prevStack.slice(0, -popCount)

      // Execute undo actions (in reverse order for groups)
      for (let i = popped.length - 1; i >= 0; i--) {
        popped[i].action.undo()
      }

      // Push to redo stack
      setRedoStack((prev) => {
        const next = [...prev, ...popped]
        if (next.length > maxDepth) {
          return next.slice(next.length - maxDepth)
        }
        return next
      })

      return remaining
    })
  }, [maxDepth])

  const redo = useCallback(() => {
    setRedoStack((prevStack) => {
      if (prevStack.length === 0) return prevStack

      const last = prevStack[prevStack.length - 1]
      const groupId = last.groupId

      let popCount = 1
      if (groupId) {
        for (let i = prevStack.length - 2; i >= 0; i--) {
          if (prevStack[i].groupId === groupId) {
            popCount++
          } else {
            break
          }
        }
      }

      const popped = prevStack.slice(-popCount)
      const remaining = prevStack.slice(0, -popCount)

      // Execute redo actions
      for (const entry of popped) {
        entry.action.redo()
      }

      // Push back to undo stack
      setUndoStack((prev) => {
        const next = [...prev, ...popped]
        if (next.length > maxDepth) {
          return next.slice(next.length - maxDepth)
        }
        return next
      })

      return remaining
    })
  }, [maxDepth])

  const clear = useCallback(() => {
    setUndoStack([])
    setRedoStack([])
  }, [])

  return {
    push,
    undo,
    redo,
    clear,
    canUndo: undoStack.length > 0,
    canRedo: redoStack.length > 0,
    undoCount: undoStack.length,
    redoCount: redoStack.length,
  }
}

// ── Keyboard shortcut integration ─────────────────────────────────────────

export function useUndoKeyboard(undo: () => void, redo: () => void, enabled = true) {
  useEffect(() => {
    if (!enabled) return

    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'z') {
        e.preventDefault()
        if (e.shiftKey) {
          redo()
        } else {
          undo()
        }
      }
      if ((e.metaKey || e.ctrlKey) && e.key === 'y') {
        e.preventDefault()
        redo()
      }
    }

    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [undo, redo, enabled])
}
