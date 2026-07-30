# KTF-005 human-only life-project resume gate

This is a human runbook, not a Builder initiative. It exists because the
free-model packet standard classifies `human` work as outside Builder, and a
project refresh can trigger a phone notification.

## Preconditions

1. KTF-004 has independent T1 review and its controlled proof evidence is
   current.
2. Jacob selects one existing active non-code project through Kitty's supported
   read-only project surface.
3. Job Search is excluded unless Jacob explicitly activates it in the current
   session.

## Selection record

Write only the project ID, name, selection time, and
`delivery_authorized: false` to the ignored local file
`data/kittybuilder/reports/ktf-005-life-project-selection.md`. Do not add it
to Git.

Selection does not authorize refresh, notification, delivery, push, or any
external action.

## Resume and delivery

Before any action, Jacob must explicitly approve that specific action. Do not
call `POST /projects/{project_id}/refresh` unless the approval includes its
possible notification behavior. Record the approved action, outcome, and exact
next action only in
`data/kittybuilder/reports/ktf-005-life-project-outcome.md`.

Stop and report the exact reason if project state is unavailable, no eligible
project exists, approval is absent, or the requested action would exceed the
approval. Never expose private project details in a Git-tracked document.
