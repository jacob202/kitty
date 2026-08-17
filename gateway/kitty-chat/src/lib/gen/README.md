# gen/ — generated API types

`gateway-schema.d.ts` mirrors the FastAPI `/openapi.json` schema and is
regenerated whenever the backend routes change. Don't edit it by hand.

## Regenerate

No running Gateway is required. The schema is dumped from the current FastAPI app, then converted to TypeScript.

```bash
cd gateway/kitty-chat
npm run gen:api-types
```

The command writes `src/lib/gen/openapi.json` first, so backend contract changes are reviewable even when no local server is running.

Then import the generated types like:

```ts
import type { paths, components } from '@/lib/gen/gateway-schema'

type BriefResponse = components['schemas']['BriefItem']
type ChatRequest   = paths['/chat']['post']['requestBody']['content']['application/json']
```

## Why bother

The hand-typed interfaces in `src/lib/gateway.ts` (e.g. `GatewayBrief`,
`GatewayTask`) drift from the backend silently — when a field is added
or renamed in `contracts/brief_item.py`, the front end keeps using the
old shape until something explodes at runtime. Pulling from OpenAPI
keeps them in sync without manual edits.

You can migrate at your own pace: pick one interface (e.g. `GatewayBrief`)
and replace its hand-written shape with a re-export from the generated
schema, leaving the rest as-is.
