# Salvage 03 — physical-reality evidence invariant

## Decision

**Preserve the invariant; retire the old keyword router.**

Historical source:

`git -C "/Users/jacobbrizinnski/Projects (from backup)/kitty" show 'ff62251^:src/core/physical_reality_router.py'`

The historical module tried to detect hardware/sensory questions with keyword lists and then force verification. The classifier was too brittle to restore, but its central rule remains valuable.

## Invariant

> When a claim, diagnosis, or state-changing action depends on the current physical state of a device, machine, environment or object, Kitty must distinguish observed evidence from inference. It must obtain sufficiently fresh evidence before presenting an unobserved physical state as fact or taking an action whose safety depends on that state.

This is an **evidence rule**, not a new domain router.

## Evidence classes

Strong evidence may include:

- a fresh photo/video supplied for the current issue;
- a measured value from a meter/sensor;
- a live status/diagnostic command tied to the actual device;
- a fresh screenshot or computer-use observation when the relevant physical state is represented there;
- an explicit current user observation (“the LED is red now”, “there is a burning smell”);
- a recent machine-readable device diagnostic with known provenance.

Weak/non-observation evidence includes:

- model memory of how similar hardware usually behaves;
- stale logs;
- a schematic/manual alone;
- a previous-session observation without freshness proof;
- a guessed file/device path;
- a verbal assumption introduced by an agent.

Weak evidence can support hypotheses. It cannot be silently upgraded to observation.

## Claim rule

Kitty may say:

- “A failing fan can cause this symptom.”
- “If the voltage is X, the next branch is Y.”
- “The log suggests the drive may be unavailable.”

Kitty should not say:

- “The fan is failing.”
- “That cable is disconnected.”
- “The capacitor is swollen.”
- “The machine is powered off.”

unless there is current evidence supporting that physical fact.

## Action rule

Before an action whose safety depends on physical state, require the necessary observation.

Examples:

- firmware/drive operations -> prove the target device identity;
- power/electrical work -> establish the relevant powered/discharged state using appropriate evidence;
- destructive disk action -> identify the physical/logical target from fresh system evidence;
- process/device shutdown -> distinguish the intended target from neighboring active work.

If evidence is unavailable:

- read-only explanation may continue conditionally;
- the unsafe/state-changing branch blocks;
- Kitty names exactly what observation is missing.

## Freshness

Freshness is domain-dependent. Do not hard-code one global duration.

A useful receipt records:

- observation;
- source;
- observed_at;
- target identity;
- scope;
- freshness rationale;
- any uncertainty.

A photo from today may be fine for a static connector shape and useless for “is the motor running right now?”

## Why the old implementation should stay retired

The historical router relied on broad keyword matches such as “buzzing”, “smell”, “amp”, “electrical” and similar domain words. This causes both false positives and false negatives.

It also treated classification as a front-door routing problem. Modern Kitty should apply the invariant at the **claim/action evidence boundary**, where it knows what fact or action actually requires proof.

## Likely modern integration points

Revalidate before implementation, but the rule belongs near existing evidence/action policy rather than in a new service.

Potential surfaces:

- action proposal/approval policy for state-changing operations;
- tool-use preconditions;
- completion/evidence receipts for claims that depend on real-world state;
- expert/troubleshooting prompts as an explanatory rule.

Do not create:

- another router;
- another approval database;
- another device-state store.

## Minimal acceptance fixtures

A future implementation should demonstrate:

1. hardware symptom + no observation -> conditional diagnosis, explicit missing evidence;
2. fresh measurement/photo -> supported factual branch may proceed;
3. stale observation for a rapidly changing state -> treated as stale;
4. destructive action against an ambiguously identified device -> blocked;
5. software-only question that happens to mention hardware vocabulary -> not spuriously blocked;
6. unavailable evidence source -> unknown, never fabricated as observed.

The goal is epistemic discipline, not more interruptions.
