/**
 * OK-ACTION-01 — Shared Object + Action Contract
 *
 * The smallest reusable product contract that lets Kitty render the same owned
 * object with the same meaningful actions across Home, Chat, Work, Projects,
 * Library, Automations, and Image Lab without introducing a new source of truth.
 *
 * This contract is a projection layer only. Existing per-authority responses
 * remain authoritative. No new store, workflow engine, or generic mutation
 * endpoint is introduced.
 *
 * @file gateway/kitty-chat/src/lib/actions-contract.ts
 *
 * ── Authority Inventory (OK-ACTION-01 §1) ─────────────────────────────────────
 *
 * Inspected actual source files. References relative to
 * gateway/kitty-chat/src/lib/ unless noted.
 *
 * 1. Gateway action/approval/execute routes (backend: gateway/routes/actions.py)
 *    - GatewayAction (gateway.ts:1573): id, kind, title, risk_tier (T0|T1|T2),
 *      status, result, execution_decision, decided_at, executed_at.
 *    - Routes: POST /actions/{id}/approve, /reject, /execute — approval and
 *      execution are separate for T2 (gateway.ts:1595-1618).
 *
 * 2. Project identity & destination
 *    - GatewayProject (gateway.ts:1706): id(number), name, kind(code|life),
 *      status(active|completed|failed|paused), summary.
 *    - Native destination: Projects view with selected project id. The app uses
 *      view state/callbacks, not a /projects/{id} browser route.
 *
 * 3. Work/Builder identity & status
 *    - GatewayProjectWorkItem (gateway.ts:1746): id(string), title,
 *      state(active|blocked|failed|ready|waiting|paused|completed), next_action.
 *    - Native destination: Work view. Current UI does not deep-link to a Work row,
 *      so the destination preserves workId as selection context without inventing a URL.
 *    - NOTE: waiting is not running; the contract maps it to queued.
 *
 * 4. Artifact identity & destination
 *    - GatewayArtifact (gateway.ts:1830): id(string), project_id, kind,
 *      media_type, display_name, state(ready|failed|...), storage_uri,
 *      content_hash, size_bytes, created_by.
 *    - Destination: /artifacts/{id} (actions-adapters.ts:42-48).
 *
 * 5. Automation identity/status/action
 *    - GatewayAutomationRun (gateway.ts:1379): id, automation_id, action,
 *      trigger_kind, status, started_at, completed_at, error.
 *    - WhyStatus (gateway.ts:1413): rich reason model for unavailable
 *      automations — not_yet_due|disabled|already_claimed|...|completed.
 *
 * 6. Deadline identity/action
 *    - GatewayDeadline (gateway.ts:1982): id(number), project_id, due_date,
 *      obligation, amount, confidence(high|medium|low|needs_jacob),
 *      status(open|closed|needs_jacob).
 *    - Current native UI has no canonical deadline-detail destination, so Deadline
 *      is deliberately not one of this packet's two proof adapters.
 *
 * 7. Image Lab identity/status
 *    - ImageEntry (gateway.ts:1496): prompt_id, job_id(IMG-01), filename,
 *      prompt, created_at.
 *    - ImageEngineStatus: available, unavailable_reason, supports_img2img.
 *    - NOTE: No backend-projected run object with canonical lifecycle exists.
 *      Image type cannot safely fit KittyTruthState today. Skipped.
 *
 * 8. Existing frontend types overlapping this contract
 *    - Home uses GatewayStateSection + custom Card mapping; no cross-surface
 *      object normalization exists yet.
 *    - DeadlineCard, ProjectCard, ArtifactAttachment each own their mapping.
 *    - queries.ts has per-domain useQuery hooks — no shared useObject hook.
 *    - No KittyObjectRef/KittyAvailableAction equivalent found. Genuine gap.
 */

// ── Canonical object type ────────────────────────────────────────────────────

/** Categories an object can belong to. Matches existing Kitty domain surfaces. */
export type KittyObjectType =
  | 'project'
  | 'artifact'
  | 'work'
  | 'automation'
  | 'deadline'
  | 'image'
  | 'conversation'
  | 'research'
  | 'action'

// ── Truthful lifecycle state ─────────────────────────────────────────────────

/**
 * Lifecycle states an object can report.
 * Rules (never violated):
 * - queued is never upgraded to running without real evidence.
 * - unknown is never collapsed into failed.
 * - approval is never collapsed into execution.
 * - generated is never upgraded to durably stored.
 */
export type KittyTruthState =
  | 'ready'
  | 'queued'
  | 'running'
  | 'waiting_for_user'
  | 'succeeded'
  | 'failed'
  | 'partial'
  | 'unknown'

// ── Canonical destination ────────────────────────────────────────────────────

/**
 * Where this object opens in the UI.
 * screen is the logical surface name (chat, work, projects, library, etc.).
 * path is a UI router path or anchor.
 */
export interface KittyDestination {
  /** Native Kitty view/surface, e.g. projects or work. */
  screen: string
  /** Selection context consumed by the destination when supported. */
  params?: Record<string, string | number | boolean>
  /** Human-readable navigation label. */
  label: string
}

// ── Shared object reference ──────────────────────────────────────────────────

/**
 * A reference to any owned object in the Kitty system.
 * Renderable without knowing the originating surface.
 */
export interface KittyObjectRef {
  /** Stable type discriminator. */
  type: KittyObjectType
  /** Canonical identifier within its type. */
  id: string
  /** Human-readable title. */
  title: string
  /** Optional subtitle or secondary label. */
  subtitle?: string
  /** Where this object opens on interaction (deterministic per object). */
  destination?: KittyDestination
  /** Truthful current lifecycle state. */
  truthState?: KittyTruthState
  /** The project this object belongs to, if any. */
  projectId?: string
  /** Owner identity (who created or is responsible for this object). */
  owner: string
  /** Raw domain detail preserved alongside the shared shell. */
  detail?: Record<string, unknown>
}

// ── Available action ─────────────────────────────────────────────────────────

/**
 * One action available on an object.
 * An unavailable action carries an explicit unavailableReason instead of
 * silently disappearing.
 */
export interface KittyAvailableAction {
  /** Stable action identifier within this object's domain. */
  id: string
  /** Human-readable label. */
  label: string
  /** Kind discriminator for grouping or icon selection. */
  kind: string
  /** Visual prominence hint. */
  prominence: 'primary' | 'secondary' | 'destructive'
  /** Whether the action is currently executable. */
  enabled: boolean
  /** Required when enabled is false: explains why. */
  unavailableReason?: string
  /** Whether this action requires explicit approval before execution. */
  requiresApproval?: boolean
  /** Where completing this action leads the user. */
  destination?: KittyDestination
  /** Arguments to pass when executing this action. */
  arguments?: Record<string, unknown>
}

// ── Projection result ────────────────────────────────────────────────────────

/** The result of projecting a single owned object into the shared contract. */
export interface KittyObjectProjection {
  object: KittyObjectRef
  actions: KittyAvailableAction[]
}
