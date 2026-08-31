# OK-PRECISION-CHAT — Chat + Composer Precision Migration

## Mission

Apply the shared precision contract to Chat, typed object cards, and the composer without weakening conversation readability or action truth.

## Depends on

- `OK-PRECISION-01`
- accepted WOW Rich Chat + Context Picker
- `OK-CHAT-03`

## Scope

- assistant/user message spacing and width
- typed object card anatomy
- action-card typography/control geometry
- tool/status disclosures
- composer height/padding/icon alignment
- context chips/mentions
- mobile keyboard/safe-area behavior
- response actions/focus states

## Acceptance

- long-form conversation remains dominant;
- object/tool metadata is visibly subordinate;
- action cards use shared control geometry;
- composer controls align optically and meet touch targets;
- textarea stays >=16px on phone;
- composer remains above bottom navigation/safe area;
- context chips wrap/truncate intentionally;
- no horizontal scroll with long artifact/project/model names;
- interrupted/failed recovery actions remain visible.

## Non-goals

- new Chat capability;
- model routing changes;
- new context sources;
- mascot decoration inside normal replies.
