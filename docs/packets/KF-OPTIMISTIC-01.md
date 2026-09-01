# KF-OPTIMISTIC-01 — Safe settings and schedule actions feel immediate without lying

**Initiative:** `kitty-opens-the-doors-20260831-v1`
**Owner:** interactive
**Depends on:** none
**Free or paid:** free
**Base:** `origin/main` `546565246289e6730b518961de64b7f371013b3b`

## Why this has no manifest
This packet is frontend-only. Builder cannot run its Node/Vitest/Playwright proof, so it is deliberately absent from the initiative manifest.

## What Jacob can do after this
Change settings and schedules and see the intended state immediately, with a visible saving state and an automatic truthful rollback if the gateway rejects it.

## Why this is the next thing
The audit count needs one correction: `queries.ts` contains 35 textual `useMutation` occurrences only because line 2 imports `useMutation`. There are 34 actual mutation hooks; four already have `onMutate` (`useCompleteTodo`, `useDeleteTodo`, `useToggleLoop`, `useDismissInsight`), leaving **30**, not 31, without it.

Blindly making all 30 optimistic would violate Kitty's truth rule. Image generation, agent execution, action approval/execution, repair commands, Builder approval, uploads, triage, sweeps and similar operations cannot be represented as completed before the server says so. This packet is therefore bounded to six deterministic existing-value mutations whose intended state can be shown as pending and rolled back exactly. Cron creation stays pending-only because its durable id is server-generated.

**Optimistic-cache scope:** `useSaveProviders` (`queries.ts:156-165`), `useUpdatePersonality` (`176-181`), `useUpdateCronSchedule` (`476-482`), `useDeleteCronSchedule` (`485-490`), `useToggleCronSchedule` (`493-498`), and `useTogglePlugin` (`731-737`). `useCreateCronSchedule` (`467-473`) is in the UI proof only as pending-only: its server-generated id must never be fabricated optimistically.

## Plan
1. In `queries.ts`, give exactly those six optimistic-cache hooks an `onMutate` snapshot/cancel/update contract, `onError` rollback, and `onSettled` reconciliation with the authoritative query.
2. Optimistic state must be visibly pending, never presented as persisted success. Do not insert a fake cron creation row into the schedule cache. The existing create form already exposes `createSchedule.isPending` as `saving…`; preserve that pending-only behavior and add a visible plain-language create failure instead of inventing a client id.
3. In `ProviderCenter.tsx`, keep provider reorder/disable/active-provider and plugin toggles responsive while pending, and replace raw mutation messages with plain-language failure copy that remains visible after rollback.
4. In `SettingsPanel.tsx`, show the edited personality immediately as saving, then either reconcile to the server value or restore the previous value and keep the existing human-readable save failure visible.
5. In `CronPanel.tsx`, show update/delete/toggle intent immediately with a per-row pending marker backed by the optimistic cache. Creation remains form-level pending-only until the server returns its real id. Any rejection restores the exact previous schedule list where applicable and shows a plain-language failure beside the affected control/form.
6. Add focused tests in the existing `ProviderCenter.test.tsx`, `SettingsPanel.test.tsx`, and `CronPanel.test.tsx` plus a hook-level test if needed to prove snapshot, rollback, reconciliation, and that cron creation never inserts a fabricated-id row.
7. Add a smoke spec `tests/smoke/optimistic-settings.spec.ts` that delays then rejects one provider/settings mutation and one cron mutation: the UI must react immediately, visibly say it is saving, roll back after rejection, and explain the failure.

## Explicitly not made optimistic
`useAddTodo`, `useRespondToLoopInsight`, `useAddMonitor`, `useRemoveMonitor`, `useSpawnAgent`, `useStopAgent`, `useCreateCronSchedule` (pending-only), `useRetryAutomationRun`, `useGenerateImage`, `useApproveAction`, `useRejectAction`, `useExecuteAction`, `useSnapshotState`, `useRunInboxTriage`, `useSetActiveProject`, `useRefreshProject`, `useDeadlineSweep`, `useIngestKnowledge`, `useExecuteRepair`, `useOperatorCommand`, `useProposeBuilderJob`, `useApproveBuilderJob`, `useUploadCapture`, and `useSubmitMessageFeedback`.

The todo/monitor hooks are deliberately left alone because PR #723 is merged and those surfaces already carry their own tested interaction semantics. The long-running/consequential hooks need truthful immediate *working* feedback, not optimistic success, and belong in a separate interaction-state pass rather than being smuggled into this packet.

## Not in scope
The already-landed PR #723 Todo/Monitor/WorkCard/ViewRenderer/Automations files are not needed here. No backend changes, no new frontend state machine/queue/registry, and no optimistic treatment of externally consequential work.

## Verification
**Tier 1 — mechanical.** Interactive lane: `cd gateway/kitty-chat && npx vitest run tests/ProviderCenter.test.tsx tests/SettingsPanel.test.tsx tests/CronPanel.test.tsx --reporter=dot` plus any new hook test, then `npx tsc --noEmit`. The rollback/pending assertions are expected RED against the base because the six optimistic-cache hooks have no `onMutate`; this is asserted from source reading, not an observed pre-change run.

**Tier 2 — running app.** `cd gateway/kitty-chat && npx playwright test tests/smoke/optimistic-settings.spec.ts`. Run under desktop and iPhone-14 projects. Route-stub a delayed success and a delayed rejection; useful visual feedback must appear before the response, and rejected state must return to the exact pre-click value with a plain-language failure.

**Tier 3 — product acceptance.** An independent reviewer changes personality/provider/plugin settings and a cron schedule at both widths, then repeats with one server rejection and confirms the UI never leaves the optimistic state standing.

Standing visible criteria: every primary control completes or is disabled with one reason; raw server/status/port/env/path text is never the primary failure; a rejected optimistic update visibly reverts; no horizontal overflow, clipping, or obscured action exists at either viewport.

## Stop condition
If any of the six optimistic-cache mutations cannot reconstruct its exact previous cache value or needs a fabricated server id/state to look successful, stop on that mutation and leave it pending-only. Never trade truth for animation.

## Recovery
Frontend cache changes are reversible. Restore the captured query data on error, then invalidate against the server; if implementation fails part-way, revert only this packet's files and restart from the six-hook list plus pending-only cron creation.