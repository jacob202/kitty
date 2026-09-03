# Kitty Gateway API Reference

**Verified:** 2026-09-03 against `main` `86b8f51d37d90b746cc5c2695f612bd1278cc805`.

This document owns the stable Gateway API discovery, authentication, client,
and tool-surface boundary. It deliberately does **not** duplicate every route.
The generated OpenAPI document and current route source own concrete HTTP
operations and schemas; domain modules own product behavior and state.

## Boundary

```text
native browser/client
  -> /proxy/<path> on kitty-chat
  -> server-side Bearer injection
  -> Kitty Gateway 127.0.0.1:8000

local operator/integration
  -> Kitty Gateway directly with Bearer auth

OpenAI-compatible client
  -> /v1/models
  -> /v1/chat/completions

model/tool integration
  -> /tools/v1/openapi.json
  -> deliberately bounded tool operations
```

The native frontend should normally call its server-side `/proxy` route rather
than the Gateway directly. The proxy resolves `KITTY_GATEWAY_URL`, keeps the
Gateway secret on the server, injects the Bearer header, and preserves the
loopback trust boundary. Do not put `GATEWAY_SECRET` or
`KITTY_GATEWAY_SECRET` in browser JavaScript, localStorage, URL parameters, or
user-visible logs.

## Authentication

`gateway/auth.py` makes `/health` the only HTTP path exempt from Gateway Bearer
authentication.

For every other HTTP path:

- if the Gateway secret is missing outside `KITTY_ENV=test`, the Gateway fails
  closed with HTTP 503;
- a missing or incorrect `Authorization: Bearer <secret>` returns HTTP 401;
- `/openapi.json`, `/docs`, and `/redoc` are therefore protected too.

The native Next.js proxy reads its secret server-side and sends the Bearer
header upstream. A browser should not need to know the secret.

## Discover the exact HTTP schema

Do not maintain a handwritten endpoint inventory. Ask the running Gateway for
its authenticated OpenAPI schema whenever exact methods, paths, parameters, or
response models matter.

This example reads the secret without printing it and writes the schema to a
temporary file:

```bash
venv/bin/python - <<'PY'
import json
from pathlib import Path

import httpx
from dotenv import dotenv_values

secret = (dotenv_values('.env').get('GATEWAY_SECRET') or '').strip()
if not secret:
    raise SystemExit('GATEWAY_SECRET is not configured')

response = httpx.get(
    'http://127.0.0.1:8000/openapi.json',
    headers={'Authorization': f'Bearer {secret}'},
    timeout=5,
)
response.raise_for_status()
schema = response.json()
out = Path('/tmp/kitty-gateway-openapi.json')
out.write_text(json.dumps(schema, indent=2) + '\n', encoding='utf-8')
print(f"{len(schema.get('paths', {}))} paths -> {out}")
PY
```

Use the generated schema for concrete HTTP contracts. OpenAPI generation
warnings are defects to investigate, not noise to suppress.

## Where API truth lives

| Concern | Owner |
|---|---|
| FastAPI app, middleware, app-level routes | `gateway/app.py` |
| Route registration | `gateway/routes/register.py` |
| HTTP handlers and request/response models | `gateway/routes/*.py` |
| Product/domain behavior and storage | owning `gateway/` domain modules |
| Native client calls | `gateway/kitty-chat/src/lib/` through `/proxy` |
| Native proxy/auth injection | `gateway/kitty-chat/src/app/proxy/[...path]/route.ts` |
| OpenAI-compatible discovery | `gateway/routes/openai_compat.py` |
| OpenAI-compatible chat | `gateway/routes/completions.py` |
| Bounded model-tool schema | `gateway/routes/tool_server.py` |

Routes should remain thin projections over domain authority. A new client must
not become a second source of business logic or state.

## Native frontend versus direct Gateway calls

The canonical `kitty-chat` frontend uses `/proxy` as its Gateway boundary. This
avoids browser CORS/auth duplication and keeps the secret server-side.

Direct Gateway calls are appropriate for trusted local operator tools,
integration tests, and clients that can safely hold the Bearer credential. They
must preserve the same authentication and loopback assumptions; direct access
is not a shortcut around the native proxy security model.

Current authenticated phone/Tailnet access is a separate security problem owned
by [`KH-REMOTE-01`](../packets/KH-REMOTE-01.md). Do not weaken Host checks,
expose Gateway/LiteLLM publicly, or move secrets into the browser to make remote
access convenient.

## OpenAI-compatible surface

Kitty exposes the bounded OpenAI-compatible paths needed by compatible clients:

- `GET /v1/models` — truthful current model menu;
- `GET /v1/models/{model_id}` — retrieve a known model entry;
- `POST /v1/chat/completions` — Kitty chat-completion boundary.

Provider/model selection remains Gateway-owned. An explicit provider selection
must not be silently replaced by another provider merely because it fails.

## Deliberately bounded tool schema

The full Gateway schema contains product, operator, diagnostic, and mutation
operations that should not automatically become model tools.

`gateway/routes/tool_server.py` therefore exposes a deliberately smaller tool
surface under `/tools/v1`. Its exact tool schema is:

```text
GET /tools/v1/openapi.json
```

That schema is also Bearer-protected. Tool clients should consume this bounded
schema rather than indiscriminately turning the full Gateway OpenAPI document
into callable model tools.

## Streaming and non-OpenAPI transports

The generated OpenAPI document is authoritative for mounted **HTTP** operations,
not every transport Kitty supports.

- `GET /stream` is an HTTP Server-Sent Events endpoint and remains part of the
  HTTP surface.
- `/voice` is a WebSocket route in `gateway/routes/voice.py`; WebSocket
  contracts are not represented by FastAPI's normal OpenAPI schema. HTTP
  `BearerAuthMiddleware` does not define WebSocket authentication; read the
  route and its focused tests for that transport's actual auth and message
  contract.

Do not infer a WebSocket or event-stream contract from an unrelated REST model.

## Adding or changing an API contract

1. Put the HTTP projection in the owning `gateway/routes/` module and keep
   business logic in the established domain owner.
2. Register each router exactly once.
3. Add focused route/domain tests for success, failure, validation, and auth or
   approval behavior when applicable.
4. Re-generate or inspect OpenAPI when the external HTTP shape changes. Treat
   duplicate-operation or schema warnings as failures to resolve.
5. For native UI consumers, update the shared frontend Gateway client/types
   rather than creating ad-hoc direct-to-`:8000` browser calls.
6. Do not broaden `/tools/v1` merely because a full-Gateway operation exists;
   model-tool exposure needs its own safety and usefulness justification.
7. Preserve approval, action, secret, and loopback boundaries. A route is not
   permission to bypass its owning subsystem.

Useful focused checks for the stable registration/auth boundary include:

```bash
python3.12 -m pytest \
  tests/test_auth.py \
  tests/test_route_contracts.py \
  tests/test_route_registration.py -q
```

Route-specific changes should also run their owning tests. A passing generic
registration check is not evidence that the changed domain behavior works.
