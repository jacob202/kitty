# OK-MEMORY-01 — Memory and Personal Context Are Useful, Inspectable, and Correctable

**Status:** draft candidate; not activated
**Roadmap phase:** 3 — companion completion

## Mission
Make Kitty's memory feel like trustworthy continuity rather than invisible prompt magic: useful facts return when relevant, Jacob can inspect/correct important memory, and sensitive context stays appropriately bounded.

## Depends on
- `KF-MEMORY-01` memory actions.
- `KF-TELOS-01` editable user context.
- Existing `memory_graph`, memory policy, consolidation and provenance authorities remain canonical.

## Product acceptance moment
Tell Kitty something worth remembering, later see it used in a relevant conversation, inspect why it was recalled, correct or forget it, pin something important, and confirm the correction/forget/pin survives reload. A sensitive topic that is not the conversation subject does not become the default lens.

## Required behavior
- Remembered facts use the existing governed memory write path and carry stable identity/provenance where supported.
- Retrieval is relevant and bounded; unavailable memory infrastructure produces partial context/warning rather than fabricated absence.
- Pin/correct/explain/forget act on the durable memory record and reconcile after reload.
- Forget/destructive semantics retain the existing confirmation/grace/undo policy where applicable.
- TELOS/personal context is editable, inspectable, and not duplicated into a second profile system.
- Sensitive-context suppression/policy remains intact and is testable as a negative case.
- User-visible explanations say why a memory mattered without exposing chain-of-thought or internal prompt dumps.
- Memory failures never block unrelated Chat from functioning with partial context.

## Verification
**Tier 1:** memory policy/graph/action/context tests including relevant recall, correction persistence, forget, pin, source unavailable, and sensitive-context negative case.

**Tier 2:** running Chat at desktop + iPhone-class: remember → new conversation recall → explain → correct/pin → reload → forget; one memory source unavailable path.

**Tier 3:** independent reviewer confirms both continuity value and the negative privacy case.

## Non-goals
- A new vector database or memory platform.
- Exposing all stored memories by default on Home.
- Using sensitive history as ambient personalization.

## Done when
Jacob can trust that Kitty remembers useful things, can correct what matters, and does not let memory infrastructure or sensitive history hijack unrelated conversations.
