# Builder Initiative Manifests

These files are proposed/approved inputs to KittyBuilder. A tracked manifest is
not proof that it has been applied to the local Builder queue. Queue truth lives
only in Builder's supported projection and durable store.

## 2026-08-01 workflow-boundary correction

`retired/ktl-001-leverage-and-learning-v1.json.retired` is retained planning
history, not an active Builder manifest. It is deliberately outside the active
manifest set and wrapped in a retired-record envelope, so Builder validation or
application fails closed. Do not recreate or apply its first three workflow
packets as the current interactive/Builder contract.

The obsolete packets are:

```text
KTL-001-next-protocol-verification
KTL-002-session-end-learning-loop
KTL-003-learning-to-queue-promotion
```

They were authored while bare `next` was incorrectly treated as a
cross-tool Builder queue command.

The corrective proving initiative is:

```text
ktl-002-measured-learning-boundary-v1.json
```

It establishes:

- bare `next` continues only the current interactive assignment;
- `builder next`, a named Builder packet/task, or a valid Builder-launched bundle
  is required to enter Builder's execution lane;
- every implementation has exactly one execution owner;
- session-end records hash-chained, tamper-evident KB-effectiveness evidence
  without scheduling Builder;
- Builder autonomy and interactive continuity are proven as parallel, separate
  lanes.

The independent reuse, Chat verification, friction capture, capability,
Product Studio, Agent Canvas, model-bench, and Mission-projection packets in the
retired KTL-001 record remain planning inputs. Their dependency IDs must be
reconciled into a new active manifest before any execution work is considered.
Never apply the retired record or treat its boundary packets as independent work.

Validate a manifest before applying it:

```bash
./kitty builder initiative validate docs/initiatives/<manifest>.json --json
```

Applying or changing a local queue still requires the appropriate Builder
operator authorization. Identical apply is expected to be idempotent; a hash
conflict is a stop condition, not permission to replace durable initiative
identity.
