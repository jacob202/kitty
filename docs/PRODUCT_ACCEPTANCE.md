# Product Acceptance Gate

This gate applies to every pull request that changes a user-visible workflow in Home, Chat, Work, Studio, Library, Settings, notifications, or onboarding.

A feature is not accepted because its route exists, its component renders, or its unit tests pass. It is accepted only when an independent reviewer can complete the intended user task in the running product and understand the result.

## Required evidence

Every user-facing PR must include a task receipt containing:

- the user goal in ordinary language;
- the exact starting state, including which dependent services are available;
- the steps taken in the running application;
- the visible result;
- the failure or recovery path tested;
- the viewport and device class;
- the exact tests and build commands with results;
- remaining limitations and known dead ends.

Evidence must include an ordered screenshot sequence or short screen recording from the running application. Component previews and generated mockups do not count as runtime proof.

## Required scenarios

Test at minimum:

1. An iPhone 14 Pro-class viewport.
2. A normal desktop viewport.
3. The required service available.
4. The required service unavailable or misconfigured.
5. Restart or reload when the workflow claims persistence or resumability.

The reviewer must verify that:

- there is no document-level horizontal scrolling;
- primary controls are visible, tappable, and not covered by fixed navigation;
- each primary control either completes its task or is disabled with one clear recovery action;
- success states show the actual result, not merely that work was queued;
- errors explain what failed and what the user can do next;
- internal names, packet IDs, routes, ports, environment variables, YAML, and raw stack details are hidden from the normal workflow;
- the workflow does not require terminal interaction unless the surface is explicitly marked Developer or Diagnostics.

## Independent review

The implementer cannot provide the final product acceptance approval.

A separate reviewer must use the running application without relying on the implementation notes. The reviewer should begin with only the user goal and report:

- whether the task could be completed;
- where they hesitated or became confused;
- every control that appeared actionable but was not;
- whether the result and next step were understandable;
- whether the evidence supports the PR's success claim.

Code review remains required, but it does not replace this task-completion review.

## Automatic failure conditions

A user-facing PR fails this gate when any primary path contains:

- horizontal page scrolling;
- clipped, obscured, or off-screen controls;
- a dead button or form;
- an enabled action backed by a known unavailable service;
- a raw server error without an actionable explanation;
- unexplained internal jargon;
- a terminal or config-file instruction where an in-app action is expected;
- conflicting counts or states with no explanation;
- a success claim without a completed live scenario;
- evidence produced by a mock, substitute, or different execution path.

## Scope control

Do not add another user-visible surface to work around a broken one. Repair or remove the existing path first.

Backend capability may merge independently when it is genuinely reusable infrastructure, but it must not be described as a shipped user feature until a coherent user workflow passes this gate.

Issue #346 is the current P0 application of this policy. Until its phone dogfood acceptance test passes, new primary navigation destinations and broad user-facing feature surfaces are frozen.
