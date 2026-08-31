# PR #707 product acceptance — c28b522e

Independent fresh-browser task-completion review of the running product at PR head `c28b522ea6ded60b9da69cd3548a2d9a41a72e09`.

User goal: recover blocked Builder work from Work, understand the resulting ready state, and recover when the Gateway becomes unavailable.

Ordered evidence:
1. `screens/01-desktop-blocked.png` — blocked item with Try again.
2. `screens/02-desktop-retried.png` — retry succeeded; item ready with preflight.
3. `screens/03-desktop-reload.png` — ready state persisted after reload.
4. `screens/04-iphone-work.png` — iPhone-class viewport, no horizontal overflow.
5. `screens/05-gateway-down.png` — Gateway unavailable, explicit retry recovery UI.
6. `screens/06-gateway-recovered.png` — Gateway restored; Work, scheduler, and preflight recovered.

Machine-readable measurements and assertions are in `receipt.json`.
