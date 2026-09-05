# DEFECTS-rc0

Candidate: `rc0` / `6aa79cf543bb1d4875041b1ac0f1e2da5e6a6799`
Runtime: exact checkout `/private/tmp/kitty-lead-rc0-20260903`
Acceptance data root: `/private/tmp/kitty-lead-rc0-data-20260903`
Viewports exercised: desktop 1440×1000; iPhone-class 393×852

- With the isolated acceptance data root active, Home still shows pre-existing personal/product state including two projects (`kitty`, `benefits-admin`) and the prior session “Session State — PR conflicts review and close-out.”
- Opening Builder lands on Work, which is a status-only surface; there is no ordinary-language request field on that surface.
- Work provides no visible proposal/edit/approve flow for starting new Builder work.
- Work provides no visible model/provider choice or estimated/actual spend information for Builder work.
- The desktop Work surface says “No Builder work is currently projected” and offers only “Builder details” and “Run ready work now,” leaving no obvious way to create the first job there.
- The iPhone-class Work surface has the same status-only Builder experience and the same missing request/proposal/approval path.
- A real Chat request asking Builder to make a tiny bounded change fails before any proposal is shown.
- The failed Chat request reports that the selected model provider did not accept the request and identifies `kitty-sonnet` as requested.
- After the failed request, the visible next-message model override offers only `Daily Kitty`; it does not present an alternate model/provider choice for recovering the failed request.
- The failed request tells the user to retry or check Settings for a different model, so recovery requires leaving the failed conversation rather than resolving the route at the failure point.
