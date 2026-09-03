# Siri Shortcut — retired compatibility pointer

**Status:** Retired 2026-09-03. Do not use the previous direct-Tailnet Gateway instructions.

The former guide told an iPhone shortcut to call the Gateway directly at a Tailnet host on port `8000`. Current architecture intentionally keeps Gateway/LiteLLM loopback-only, and native Kitty's authenticated remote edge is not yet complete. Exposing or addressing the Gateway directly would contradict that security boundary.

Use [`reference/LAUNCHER_CONTRACT.md`](reference/LAUNCHER_CONTRACT.md) for the supported runtime boundary and [`packets/KH-REMOTE-01.md`](packets/KH-REMOTE-01.md) for the authenticated phone/Tailnet repair. The previous shortcut instructions remain recoverable from Git history for archaeology only.
