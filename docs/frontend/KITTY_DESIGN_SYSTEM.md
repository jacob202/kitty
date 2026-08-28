# Kitty Design System

## Principles

- Calm before clever: hierarchy and state truth outrank decoration.
- Chat is the product center; other surfaces support work without turning chat into a dashboard.
- Prefer open layouts, lists, rails, and focused canvases over nested card grids.
- Show product concepts (`Work`, `Image Lab`, `Projects`) rather than backend implementation language.
- Every asynchronous state must say what is happening, whether it succeeded, and what the user can do next.
- Empty, loading, degraded, blocked, and error states are designed states, not afterthoughts.
- Kitty personality is sparse and functional; the mascot may indicate state but does not decorate every surface.

## Semantic color tokens

`src/app/globals.css` is the runtime token source. New UI uses semantic tokens directly; legacy aliases exist only for progressive migration.

| Purpose | Token |
| --- | --- |
| Canvas | `--color-canvas` |
| Surface | `--color-surface` |
| Elevated surface | `--color-surface-elevated` |
| Separator/border | `--color-separator` |
| Primary text | `--color-text-primary` |
| Secondary text | `--color-text-secondary` |
| Muted text | `--color-text-muted` |
| Accent | `--color-accent` |
| Success | `--color-success` |
| Warning | `--color-warning` |
| Destructive | `--color-destructive` |
| Hover | `--color-interactive-hover` |
| Selected | `--color-selected` |
| Focus | `--color-focus-ring` |
| Disabled | `--color-disabled` |

`cosmic` is retained as the persisted ID for Kitty's canonical neutral-light theme while migration is in progress. `day` is the warm-light variant and `night` is the deliberately designed dark variant. New components must not branch visually on theme names; consume semantic tokens instead.

## Typography and spacing

Use the existing system-first stacks. Body and UI chrome use `--font-body`; display type is reserved for genuine headings, not status labels or controls. Prefer 15–16px readable body copy, 12px minimum for persistent controls, and avoid monospaced text unless the content is genuinely technical.

Spacing follows the existing 4/8px-derived scale (`--s-1` through `--s-8`). Use fewer, stronger gaps rather than wrapping every region in another panel. Surface radius is `--r-surface`; control radius is `--r-control`; pills are reserved for compact status or selection states.

## Component conventions

- Navigation uses product-facing names and always exposes `aria-current` for the active destination.
- Primary actions use the accent; routine controls use neutral surfaces and separators.
- Status color never carries meaning alone; pair it with clear text or an accessible label.
- Borders separate structure only when whitespace or elevation cannot do the job.
- Raw logs, provider details, queue internals, and technical evidence live behind disclosure.
- Destructive actions require explicit treatment and confirmation when the effect cannot be trivially undone.
## Responsive rules

Phone layouts are composed for touch rather than compressed desktop layouts. Validate at approximately 390px and 430px plus tablet, laptop, and large desktop widths. Persistent touch targets are at least 44px high; critical actions should target 48px where space permits.

The mobile bottom navigation owns safe-area spacing. Composers and scroll containers must reserve its height. Long project names, artifact names, model names, and statuses truncate or wrap intentionally instead of forcing horizontal scrolling.

Dialogs become sheets when that better preserves usable phone width. Dense tables become prioritized rows or disclosed detail rather than horizontally squeezed columns.

## Interaction and state conventions

Keyboard focus uses the global semantic focus ring. Do not remove outlines without an equivalent visible replacement. Motion should clarify state changes, not decorate idle screens; `prefers-reduced-motion` collapses animation and transitions globally.

Use optimistic UI only when the underlying operation is safely reversible and the UI can reconcile truthfully. Loading uses stable skeleton geometry where content shape is known. Errors preserve the failed context and expose a concrete retry/recovery action when one exists.

Selected, hover, disabled, waiting, blocked, failed, and completed states must remain visually distinct in both light and dark themes. Do not invent success while durable backend state is still pending.

## Chat surface

Conversation content outranks routing and execution metadata. Assistant replies use the elevated neutral surface; user messages use the selected/accent-tint surface rather than a saturated accent fill. Both keep primary text color and a subtle separator so long-form copy remains comfortable in light and dark themes.

Response actions are quiet but reachable. On touch layouts they remain visible with at least 44px targets; on pointer layouts they may reveal on hover/focus. Recovery actions for interrupted or failed turns stay visible without hover. Meaningless single-branch labels such as `1 response / showing 1` are omitted.

Provider, requested-model, tools, routing, and memory evidence are subordinate details. Preserve their truth, but render them as muted disclosure/detail UI rather than competing with the answer. Technical metadata must never imply that a requested model actually produced a response when only the request is known.

The composer is a neutral surface at rest and uses the accent/focus ring only while focused. Phone textarea text is at least 16px to avoid browser zoom, and persistent attachment/model/voice/send controls use touch-sized targets. The composer must remain fully above the fixed phone navigation and safe area.

Desktop chat history is supportive navigation, not a competing call-to-action column. `New chat` and the active thread use the shared selected treatment; saturated accent is reserved for genuinely primary actions.
