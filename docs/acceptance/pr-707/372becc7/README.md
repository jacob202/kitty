# PR #707 product acceptance — 372becc7

Independent fresh-browser task-completion review of the running product at PR head `372becc79428e80d99eada46bb0546c16736a730`.

User goal: recover blocked Builder work from Work, understand the resulting ready state, and recover when the Gateway becomes unavailable.

Ordered evidence:
1. `screens/01-desktop-blocked.png` — blocked item with Try again.
2. `screens/02-desktop-retried.png` — durable retry succeeded; item ready with preflight.
3. `screens/03-desktop-reload.png` — ready state persisted after reload.
4. `screens/04-iphone-work.png` — iPhone-class viewport, no horizontal overflow, recovery control visible.
5. `screens/05-gateway-down.png` — Gateway unavailable, explicit retry recovery UI.
6. `screens/06-gateway-recovered.png` — Gateway restored; Work, scheduler, and preflight recovered.

Machine-readable assertions are in `receipt.json` (`pass=true`).
