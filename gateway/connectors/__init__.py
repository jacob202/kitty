"""External connectors — read-only integrations that emit signals (P3).

Each connector is a thin adapter that polls its upstream on a schedule
and writes deduped rows to ``gateway.signal_store``. The connector
shape (§17.2) is shared: cron-polled, signal-emitting, no webhooks,
no per-connector table.

Connectors must:

- Fail loud on transport or credential errors. A quiet inbox is
  indistinguishable from a broken connector — and broken wins.
- Emit *summaries*, never bodies or document contents. Bodies (when
  needed) are fetched on explicit demand and are data class
  ``mail_body`` (or equivalent) under D10 — they must never land in a
  signal row.
- Not push, send, modify, label, or delete upstream. Read-only at
  the protocol level where the provider enforces it (Gmail scope);
  the code adds a second layer of refusal on top.

Public API is per-module; this package collects them.
"""
