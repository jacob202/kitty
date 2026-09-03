# Capability Manifest — Design Contract (Proposed Schema)

**Schema version:** 2 (proposed)
**Authority:** ADR 0029 ratifies the *principle* that Kitty will have one
capability manifest as the single source of runtime truth; ADR 0032 ratifies
evidence-backed claims; Constitution v1 Article III.5 (Honest State) ratifies
the five-state lattice. This document is a **proposed design contract and
schema**, not ratified live truth — ADR 0029 did not bless this specific
schema, and no ADR or Jacob sign-off ratifies it as built.
**Date:** 2026-08-05
**Status:** Designed — not yet built. The detailed v2 schema below is a design
proposal. For **actual current runtime behavior**, see the live implementation
in `gateway/runtime_manifest.py` and `gateway/builder_status.py`, which ADR
0029 designates as the path the manifest will supersede once built.

When implemented per ADR 0029, the Capability Manifest is intended to be
Kitty's single source of runtime truth — the one surface every UI, client,
shell, and prompt consumes, with no other endpoint, config file, or inferred
state able to contradict it. That is the design intent of this contract, not
a description of current runtime.

---

## 0. Design axioms

Every rule in this document derives from four axioms. When the specification is ambiguous, resolve toward the axiom.

| # | Axiom |
|---|---|
| A1 | **One owner per fact.** Each field has exactly one owning subsystem. The composer does not create facts — it collects them from their owners. |
| A2 | **No fabricated state.** A probe that fails produces `unknown`, not `unavailable`. A value that exceeds its TTL produces `stale`, not `available`. An empty result produces an explicit empty value, not `null`. |
| A3 | **Evidence traces to a source.** Every fact carries `source` (the owning subsystem) and `observed_at` (when it was last confirmed). Complex facts carry `evidence_ref` (the probe, record, or receipt proving the claim). |
| A4 | **TTLs are field-specific, not global.** A Git repository probe is valid for seconds. A provider pricing record is valid for an hour. A project name is valid until the next switch. Each field declares its own TTL. |

---

## 1. The state lattice

Every field in the manifest is classified into exactly one of five states. These are the only states. No field may carry an unlisted or compound state.

| State | Meaning | Behavior | Example |
|---|---|---|---|
| `available` | The owning subsystem confirmed the value is correct and usable. | The value is safe to display and consume. | LiteLLM returned a valid model list within the last 15 seconds. |
| `unavailable` | The owning subsystem confirmed the capability is absent or disabled by policy. | Display the reason. Do not offer the capability. | `KITTY_BUILDER_QUEUE_ENABLED=0`. |
| `degraded` | The capability is partially available but has a known loss of function. | Display the degraded value with the reason. Offer the capability with a warning. | Builder queue is readable but 3 packet records have incomplete attempt data. |
| `stale` | The last confirmed value has exceeded its TTL and no refresh has succeeded. | Display the last-known value with a staleness indicator and the age. Do not accept the value as current for decisions that depend on freshness. | The last model probe was 47 seconds ago; TTL is 15 seconds. |
| `unknown` | The owning subsystem could not establish the truth. The probe failed, or the source is unreachable. | Display the reason. Never treat as `unavailable`, never display as a default, and never offer the capability as if it works. | LiteLLM did not respond to the model probe within 1.5 seconds. |

### State transitions

A fact transitions from one state to another only when its owning subsystem's probe returns a different result. The composer does not auto-promote or demote facts. Transitions are:

```
                      ┌──→ available ──→ stale (TTL expired) ──┐
                      │                                          │
unknown (initial) ────┤                                          ├──→ unknown (TTL expired AND refresh failed)
                      │                                          │
                      ├──→ unavailable (confirmed absent)        │
                      └──→ degraded (confirmed partial)          │
```

A fact that enters `stale` because its TTL expired remains `stale` until its next probe succeeds (→ `available` or `degraded`) or the probe fails (→ `unknown`). A fact in `stale` state for longer than 5× its TTL may be treated as `unknown` by consumers that depend on freshness, but the manifest still reports `stale`.

---

## 2. The fact envelope

Every leaf fact in the manifest carries this envelope. Container objects (objects that group facts) carry `observed_at` and `valid_until` at the container level; their child facts inherit those timestamps unless a child declares its own.

```json
{
  "state": "available | unavailable | degraded | stale | unknown",
  "value": "<any>",
  "source": "litellm:/v1/models",
  "observed_at": "2026-08-05T14:32:11.000Z",
  "valid_until": "2026-08-05T14:32:26.000Z",
  "evidence_ref": "probe:litellm:models:5e3f1a2b",
  "reason": null
}
```

### Field rules

- `state` — required on every leaf fact. Container objects may omit it; consumers must check leaf facts.
- `value` — required. The confirmed value when the state is `available` or `degraded`. `null` when the state is `unknown`, `unavailable`, or `stale` with no prior confirmed value.
- `source` — required. The owning subsystem identifier. Uses the format `subsystem:path` (e.g., `litellm:/v1/models`, `builder_runtime`, `git`). Never `manual`, `config`, or `prompt`.
- `observed_at` — required. ISO 8601 UTC with millisecond precision. The moment the owning subsystem last confirmed this fact.
- `valid_until` — required. ISO 8601 UTC. The moment after which the fact is `stale`. Computed as `observed_at + ttl`. A consumer that reads a fact whose `valid_until` is in the past must treat it as stale.
- `evidence_ref` — optional. When present, a stable identifier for the probe, record, or receipt that proves this fact. Format: `probe:<subsystem>:<key>` or `receipt:<id>`. Absent for facts derived from static configuration (e.g., the application name).
- `reason` — required when state is not `available`. A human-readable explanation of why the fact is not available. Required for `unavailable`, `degraded`, `stale`, and `unknown`. Must not be empty. Must not leak secrets or internal paths.

---

## 3. The full schema

```json
{
  "schema_version": 2,
  "manifest_id": "runtime-a1b2c3d4e5f6g7h8",
  "revision": "a1b2c3d4e5f6g7h8",
  "generated_at": "2026-08-05T14:32:11.000Z",
  "valid_until": "2026-08-05T14:32:26.000Z",
  "application": { },
  "clock": { },
  "context": {
    "active_project": { },
    "repository": { }
  },
  "execution": {
    "builder": { },
    "builder_attention": { }
  },
  "inference": {
    "routing_mode": { },
    "available_models": { },
    "providers": { },
    "pricing": { }
  },
  "connections": {
    "gateway": { },
    "litellm": { }
  },
  "tools": { },
  "mcp_servers": { },
  "memory": {
    "memory_graph": { },
    "mem0": { },
    "chromadb": { }
  },
  "image": {
    "generation": { },
    "recipes": { },
    "characters": { },
    "comfyui": { },
    "runpod": { }
  },
  "shell": {
    "openwebui": { }
  },
  "approvals": { },
  "health": { }
}
```

### 3.1 `application`

Identifies the running Kitty instance. Derived from build metadata and environment. Never stale — these are static facts observed once at startup.

```json
{
  "application": {
    "name": {
      "state": "available",
      "value": "Kitty",
      "source": "build_metadata",
      "observed_at": "2026-08-05T12:00:00.000Z",
      "valid_until": "2026-08-06T12:00:00.000Z"
    },
    "version": {
      "state": "available",
      "value": "0.1.0",
      "source": "KITTY_VERSION",
      "observed_at": "2026-08-05T12:00:00.000Z",
      "valid_until": "2026-08-06T12:00:00.000Z"
    },
    "build_commit": {
      "state": "available",
      "value": "d3c8274847b149fc5c2d1e9b50ca056891b63cb8",
      "source": "git",
      "observed_at": "2026-08-05T12:00:00.000Z",
      "valid_until": "2026-08-06T12:00:00.000Z"
    },
    "environment": {
      "state": "available",
      "value": "local",
      "source": "KITTY_ENV",
      "observed_at": "2026-08-05T12:00:00.000Z",
      "valid_until": "2026-08-06T12:00:00.000Z"
    }
  }
}
```

**Owner:** build_metadata / environment variables
**TTL:** 24 hours (application metadata does not change at runtime)

### 3.2 `clock`

The host's current time and timezone. Computed fresh on every manifest generation. The value is the generation time itself — no external probe needed.

```json
{
  "clock": {
    "current_time": "2026-08-05T14:32:11.000Z",
    "timezone": "America/Denver",
    "state": "available",
    "source": "host_clock",
    "observed_at": "2026-08-05T14:32:11.000Z",
    "valid_until": "2026-08-05T14:32:12.000Z"
  }
}
```

**Owner:** host clock
**TTL:** 1 second (time advances)

### 3.3 `context`

Active project and repository state. These are the facts that ground every turn in the user's current work.

```json
{
  "context": {
    "active_project": {
      "state": "available",
      "value": {
        "project_id": 1,
        "name": "kitty",
        "kind": "code",
        "description": "Kitty personal AI companion"
      },
      "source": "project_store",
      "observed_at": "2026-08-05T14:32:11.000Z",
      "valid_until": "2026-08-05T14:32:41.000Z"
    },
    "repository": {
      "state": "available",
      "value": {
        "root": "/Users/jacobbrizinski/Projects/kitty",
        "branch": "main",
        "commit": "d3c8274847b149fc5c2d1e9b50ca056891b63cb8",
        "dirty": true,
        "changed_paths": 7
      },
      "source": "git",
      "observed_at": "2026-08-05T14:32:11.000Z",
      "valid_until": "2026-08-05T14:32:16.000Z"
    }
  }
}
```

**Owners:**
- `active_project` — `project_context` + `project_store`
- `repository` — `git` (subprocess probe)

**TTLs:**
- `active_project` — 30 seconds (project switching is an explicit user action)
- `repository` — 5 seconds (branch changes, commits, and dirtiness are frequent during active work)

#### Unknown / unavailable shapes

```json
{
  "context": {
    "active_project": {
      "state": "unknown",
      "value": null,
      "source": "project_context",
      "observed_at": "2026-08-05T14:32:11.000Z",
      "valid_until": "2026-08-05T14:32:41.000Z",
      "reason": "No active project has been set. Use /project to select one."
    },
    "repository": {
      "state": "unknown",
      "value": null,
      "source": "git",
      "observed_at": "2026-08-05T14:32:11.000Z",
      "valid_until": "2026-08-05T14:32:16.000Z",
      "reason": "git probe failed: not a git repository (or any git process is unavailable)"
    }
  }
}
```

### 3.4 `execution`

Builder queue, initiative, and worker state. These are read through bounded, non-mutating projections into Builder's SQLite database. The detailed initiative body (400KB+) is never inlined — only counts and attention states.

```json
{
  "execution": {
    "builder": {
      "state": "degraded",
      "value": {
        "schema_version": 2,
        "integrity": {
          "state": "partial",
          "partial_packets": 3,
          "total_packets": 107
        },
        "queue": {
          "total": 107,
          "queued": 2,
          "claimed": 0,
          "running": 0,
          "blocked": 10,
          "pr_opened": 0,
          "awaiting_review": 0,
          "done": 51,
          "failed": 1,
          "cancelled": 43
        },
        "worker_sessions": {
          "total": 0,
          "connected": 0
        },
        "initiative_count": 31
      },
      "source": "builder_runtime",
      "observed_at": "2026-08-05T14:32:11.000Z",
      "valid_until": "2026-08-05T14:32:21.000Z",
      "evidence_ref": "probe:builder:snapshot:7f3a1b2c"
    },
    "builder_attention": {
      "state": "available",
      "value": [
        {
          "initiative": "Trustworthy KittyBuilder: B2-B10",
          "state": "paused",
          "packet_count": 9
        },
        {
          "initiative": "KTF-001: Daylight Builder lifecycle proof (v4)",
          "state": "failed",
          "packet_count": 2
        }
      ],
      "source": "builder_runtime",
      "observed_at": "2026-08-05T14:32:11.000Z",
      "valid_until": "2026-08-05T14:32:21.000Z"
    }
  }
}
```

**Owner:** `builder_runtime` (via `build_runtime_snapshot` → `build_status_snapshot`)

**TTL:** 10 seconds (Builder can process packets rapidly during active campaigns)

**Rules:**
- Builder reads must never initialize or migrate the queue database. If the database does not exist, report `unavailable` with reason "Builder queue database does not exist."
- If the database exists but the projection schema is not fully available, report `degraded` with specific counts of partial records.
- If a read fails with an OS or database error, report `unknown`.
- `initiative_count` is always included; the full initiative list is never inlined in the manifest but is available through `/builder/initiatives`.
- `builder_attention` filters initiatives to `blocked`, `failed`, or `paused` states and is limited to the 10 most recent. It exists so the Home surface and prompt can surface "what needs attention" without loading all 31+ initiative records.

### 3.5 `inference`

Model routing, provider availability, and pricing staleness. This is the most dynamic section — model lists and provider health change with network conditions.

```json
{
  "inference": {
    "routing_mode": {
      "state": "available",
      "value": "gateway route_model + LiteLLM",
      "source": "gateway configuration",
      "observed_at": "2026-08-05T12:00:00.000Z",
      "valid_until": "2026-08-06T12:00:00.000Z"
    },
    "available_models": {
      "state": "available",
      "value": [
        "kitty-default",
        "kitty-small",
        "kitty-think",
        "kitty-code",
        "kitty-vision"
      ],
      "source": "litellm:/v1/models",
      "observed_at": "2026-08-05T14:32:11.000Z",
      "valid_until": "2026-08-05T14:32:26.000Z",
      "evidence_ref": "probe:litellm:models:a3b2c1d4"
    },
    "providers": {
      "state": "available",
      "value": [
        {
          "id": "openrouter",
          "route": "openrouter",
          "configuration": "configured",
          "default_model": null,
          "health": {
            "state": "available",
            "latency_ms": 245,
            "observed_at": "2026-08-05T14:32:11.000Z",
            "valid_until": "2026-08-05T14:32:26.000Z",
            "evidence_ref": "probe:litellm:health:openrouter"
          }
        },
        {
          "id": "deepseek",
          "route": "deepseek",
          "configuration": "unconfigured",
          "default_model": "deepseek-chat",
          "health": {
            "state": "unavailable",
            "observed_at": "2026-08-05T14:32:11.000Z",
            "valid_until": "2026-08-05T14:32:26.000Z",
            "reason": "No configured credential was found"
          }
        }
      ],
      "source": "provider_config + litellm probes",
      "observed_at": "2026-08-05T14:32:11.000Z",
      "valid_until": "2026-08-05T14:32:26.000Z"
    },
    "pricing": {
      "state": "stale",
      "value": {
        "last_updated": "2026-08-04T18:00:00.000Z",
        "model_count": 342
      },
      "source": "openrouter_pricing_cache",
      "observed_at": "2026-08-04T18:00:00.000Z",
      "valid_until": "2026-08-05T02:00:00.000Z",
      "reason": "Pricing data is 20.5 hours old. Cost estimates may be inaccurate."
    }
  }
}
```

**Owners:**
- `routing_mode` — gateway configuration (static)
- `available_models` — `litellm:/v1/models` (live probe)
- `providers` — `provider_config` (static configuration) + per-provider health probes
- `pricing` — `openrouter_pricing_cache`

**TTLs:**
- `routing_mode` — 24 hours
- `available_models` — 15 seconds
- `providers[*].health` — 15 seconds
- `pricing` — 8 hours (OpenRouter pricing does not change rapidly)

**Rules:**
- The available model list is the authoritative list of models the active provider policy can honor. If no models are returned or the probe fails, `available_models` is `unknown`.
- Provider health is per-provider. A configured provider whose health probe fails is `degraded` (the provider exists but is unreachable). An unconfigured provider is `unavailable`.
- When pricing is `stale`, cost estimates must display "estimated" or "not verified" rather than a confident dollar amount.

### 3.6 `connections`

Point-to-point connection health for Kitty's own services.

```json
{
  "connections": {
    "gateway": {
      "state": "available",
      "value": {
        "endpoint": "http://127.0.0.1:8000",
        "uptime_seconds": 84123
      },
      "source": "gateway health check",
      "observed_at": "2026-08-05T14:32:11.000Z",
      "valid_until": "2026-08-05T14:32:16.000Z"
    },
    "litellm": {
      "state": "available",
      "value": {
        "endpoint": "http://127.0.0.1:8001",
        "model_count": 5
      },
      "source": "litellm health probe",
      "observed_at": "2026-08-05T14:32:11.000Z",
      "valid_until": "2026-08-05T14:32:16.000Z",
      "evidence_ref": "probe:litellm:health:a3b2c1d4"
    }
  }
}
```

**Owner:** Composition of Gateway health + LiteLLM probe
**TTL:** 5 seconds (connection is binary: up or down)

### 3.7 `tools`

Kitty-owned tool surface. This is the catalog of Gateway-owned command surfaces, not a claim that every remote integration is healthy.

```json
{
  "tools": {
    "state": "available",
    "value": [
      {
        "id": "chat.completions",
        "display_name": "Chat",
        "route": "/v1/chat/completions",
        "approval_class": "read",
        "health": {
          "state": "available",
          "source": "gateway route registry",
          "observed_at": "2026-08-05T14:32:11.000Z",
          "valid_until": "2026-08-05T14:32:21.000Z"
        }
      },
      {
        "id": "memory.search",
        "display_name": "Memory search",
        "route": "/tools/v1/memory/search",
        "approval_class": "read",
        "health": {
          "state": "available",
          "source": "gateway route registry",
          "observed_at": "2026-08-05T14:32:11.000Z",
          "valid_until": "2026-08-05T14:32:21.000Z"
        }
      },
      {
        "id": "memory.remember",
        "display_name": "Remember",
        "route": "/tools/v1/memory/remember",
        "approval_class": "write-notify",
        "health": {
          "state": "available",
          "source": "gateway route registry",
          "observed_at": "2026-08-05T14:32:11.000Z",
          "valid_until": "2026-08-05T14:32:21.000Z"
        }
      },
      {
        "id": "notes.search",
        "display_name": "Notes search",
        "route": "/tools/v1/notes/search",
        "approval_class": "read",
        "health": {
          "state": "available",
          "source": "gateway route registry",
          "observed_at": "2026-08-05T14:32:11.000Z",
          "valid_until": "2026-08-05T14:32:21.000Z"
        }
      },
      {
        "id": "projects.list",
        "display_name": "Project list",
        "route": "/tools/v1/projects",
        "approval_class": "read",
        "health": {
          "state": "available",
          "source": "gateway route registry",
          "observed_at": "2026-08-05T14:32:11.000Z",
          "valid_until": "2026-08-05T14:32:21.000Z"
        }
      },
      {
        "id": "projects.next_step",
        "display_name": "Next step",
        "route": "/tools/v1/projects/next-step",
        "approval_class": "read",
        "health": {
          "state": "available",
          "source": "gateway route registry",
          "observed_at": "2026-08-05T14:32:11.000Z",
          "valid_until": "2026-08-05T14:32:21.000Z"
        }
      },
      {
        "id": "calendar.today",
        "display_name": "Calendar today",
        "route": "/tools/v1/calendar/today",
        "approval_class": "read",
        "health": {
          "state": "available",
          "source": "gateway route registry",
          "observed_at": "2026-08-05T14:32:11.000Z",
          "valid_until": "2026-08-05T14:32:21.000Z"
        }
      },
      {
        "id": "tutor.ask",
        "display_name": "Tutor",
        "route": "/tools/v1/tutor",
        "approval_class": "read",
        "health": {
          "state": "available",
          "source": "gateway route registry",
          "observed_at": "2026-08-05T14:32:11.000Z",
          "valid_until": "2026-08-05T14:32:21.000Z"
        }
      },
      {
        "id": "builder.status",
        "display_name": "Builder status",
        "route": "/tools/v1/builder/status",
        "approval_class": "read",
        "health": {
          "state": "available",
          "source": "gateway route registry",
          "observed_at": "2026-08-05T14:32:11.000Z",
          "valid_until": "2026-08-05T14:32:21.000Z"
        }
      },
      {
        "id": "capture.write",
        "display_name": "Quick Capture",
        "route": "/tools/v1/capture",
        "approval_class": "write-notify",
        "health": {
          "state": "available",
          "source": "gateway route registry",
          "observed_at": "2026-08-05T14:32:11.000Z",
          "valid_until": "2026-08-05T14:32:21.000Z"
        }
      }
    ],
    "source": "gateway route registry",
    "observed_at": "2026-08-05T14:32:11.000Z",
    "valid_until": "2026-08-05T14:32:21.000Z"
  }
}
```

**Owner:** Gateway route registry
**TTL:** 10 seconds

**Rules:**
- The tool catalog is derived from the Gateway's registered routes, not from a hand-maintained list. A tool exists in the manifest if and only if its route is registered.
- Per-tool health is reported separately from tool availability. A tool may be `available` (route registered) while its health is `unknown` (the tool's backend dependency, e.g., ChromaDB, is unverifiable). The composer does not conflate these.
- `approval_class` maps to the Constitution's approval classes: `read` (auto), `write-notify` (act and notify), `write-approve` (request approval).
- Remote integration tools (MCP servers) are reported under `mcp_servers`, not here. These are Gateway-owned command surfaces only.

### 3.8 `mcp_servers`

MCP (Model Context Protocol) server state. These are external tool servers that Open WebUI connects to. Each server reports its connection, protocol level, and tool catalog.

```json
{
  "mcp_servers": {
    "state": "degraded",
    "value": [
      {
        "id": "filesystem",
        "display_name": "Filesystem MCP",
        "transport": "stdio",
        "command": "npx @anthropic/mcp-filesystem ~/Projects",
        "connection": {
          "state": "available",
          "observed_at": "2026-08-05T14:32:11.000Z",
          "valid_until": "2026-08-05T14:32:21.000Z"
        },
        "tools": {
          "state": "available",
          "value": [
            {"name": "read_file", "description": "Read a file from the filesystem"},
            {"name": "write_file", "description": "Write content to a file"},
            {"name": "list_directory", "description": "List directory contents"},
            {"name": "search_files", "description": "Search for files matching a pattern"}
          ],
          "observed_at": "2026-08-05T14:32:11.000Z",
          "valid_until": "2026-08-05T14:32:21.000Z"
        }
      },
      {
        "id": "git",
        "display_name": "Git MCP (read-only)",
        "transport": "stdio",
        "command": "npx @anthropic/mcp-git --read-only ~/Projects",
        "connection": {
          "state": "available",
          "observed_at": "2026-08-05T14:32:11.000Z",
          "valid_until": "2026-08-05T14:32:21.000Z"
        },
        "tools": {
          "state": "available",
          "value": [
            {"name": "git_status", "description": "Show working tree status"},
            {"name": "git_diff", "description": "Show changes"},
            {"name": "git_log", "description": "Show commit history"},
            {"name": "git_branch", "description": "List branches"},
            {"name": "git_show", "description": "Show a commit"}
          ],
          "observed_at": "2026-08-05T14:32:11.000Z",
          "valid_until": "2026-08-05T14:32:21.000Z"
        }
      },
      {
        "id": "shell",
        "display_name": "Shell MCP (read-only)",
        "transport": "stdio",
        "command": "npx @anthropic/mcp-shell --read-only",
        "connection": {
          "state": "degraded",
          "observed_at": "2026-08-05T14:32:11.000Z",
          "valid_until": "2026-08-05T14:32:21.000Z",
          "reason": "Connected but timeout was exceeded on last tool call"
        },
        "tools": {
          "state": "degraded",
          "value": [
            {"name": "run_command", "description": "Run a shell command (read-only mode)"}
          ],
          "observed_at": "2026-08-05T14:32:11.000Z",
          "valid_until": "2026-08-05T14:32:21.000Z"
        }
      },
      {
        "id": "web-fetch",
        "display_name": "Web Fetch MCP",
        "transport": "stdio",
        "command": "npx @anthropic/mcp-web-fetch",
        "connection": {
          "state": "unknown",
          "observed_at": "2026-08-05T14:32:11.000Z",
          "valid_until": "2026-08-05T14:32:21.000Z",
          "reason": "MCP server process did not respond to initialize within 3 seconds"
        },
        "tools": {
          "state": "unknown",
          "value": null,
          "observed_at": "2026-08-05T14:32:11.000Z",
          "valid_until": "2026-08-05T14:32:21.000Z",
          "reason": "Cannot enumerate tools: server connection is unknown"
        }
      }
    ],
    "source": "mcp_registry",
    "observed_at": "2026-08-05T14:32:11.000Z",
    "valid_until": "2026-08-05T14:32:21.000Z"
  }
}
```

**Owner:** `mcp_registry` (the Gateway component that manages MCP server processes)

**TTL:** 10 seconds

**Rules:**
- Each MCP server has its own connection state and tool catalog. A degraded server does not make the entire MCP section degraded.
- The container-level `state` is `degraded` when at least one server is not `available`. It is `unavailable` when the MCP registry itself cannot report.
- Tools exposed by MCP servers are never conflated with Gateway-owned tools (`tools` section). They are separate concerns with separate owners.
- When a server's connection is `unknown`, its tool catalog is always also `unknown`.
- The actual list of registered MCP servers comes from the MCP server configuration, not from a hand-maintained manifest entry.

### 3.9 `memory`

Kitty's memory infrastructure health. The memory subsystem has three components: the memory graph (unified read path), mem0 (long-term memory backend), and ChromaDB (vector store).

```json
{
  "memory": {
    "memory_graph": {
      "state": "available",
      "value": {
        "adapter_count": 4,
        "active_adapters": ["journal", "inbox", "facts", "todos"],
        "last_search_latency_ms": 120
      },
      "source": "memory_graph",
      "observed_at": "2026-08-05T14:32:11.000Z",
      "valid_until": "2026-08-05T14:32:16.000Z",
      "evidence_ref": "probe:memory:graph:2d4e5f6a"
    },
    "mem0": {
      "state": "available",
      "value": {
        "memory_count": 847,
        "last_write_at": "2026-08-05T14:28:00.000Z"
      },
      "source": "mem0",
      "observed_at": "2026-08-05T14:32:11.000Z",
      "valid_until": "2026-08-05T14:32:16.000Z",
      "evidence_ref": "probe:memory:mem0:2d4e5f6a"
    },
    "chromadb": {
      "state": "degraded",
      "value": {
        "collection_count": 3,
        "total_embeddings": 12450,
        "version": "0.5.23"
      },
      "source": "chromadb",
      "observed_at": "2026-08-05T14:32:11.000Z",
      "valid_until": "2026-08-05T14:32:16.000Z",
      "reason": "1 of 3 collections reports 0 embeddings (expected > 0). Collection 'memory_v1' may need re-indexing.",
      "evidence_ref": "probe:memory:chromadb:2d4e5f6a"
    }
  }
}
```

**Owners:**
- `memory_graph` — `gateway/memory_graph.py`
- `mem0` — `gateway/memory.py`
- `chromadb` — ChromaDB client

**TTL:** 5 seconds (memory writes happen during active chat; staleness matters for continuity)

**Rules:**
- `memory_graph` reports the number of active adapters and the last search latency. If no search has been performed, `last_search_latency_ms` is `null`.
- `mem0` reports the total memory count and last write time. If mem0 is not installed or the backend is unreachable, state is `unavailable`.
- `chromadb` reports collection count, total embeddings, and version. A collection with zero embeddings when it was expected to have data is a `degraded` condition. If ChromaDB is not running, state is `unavailable`.
- The memory section never contains actual memory content — only infrastructure health. Content is retrieved via the tools surface (`/tools/v1/memory/search`).

### 3.10 `image`

Image generation infrastructure health. Covers local ComfyUI, remote RunPod, recipe availability, and character state.

```json
{
  "image": {
    "generation": {
      "state": "degraded",
      "value": {
        "queue_depth": 0,
        "active_jobs": 0,
        "completed_24h": 3,
        "failed_24h": 1
      },
      "source": "image_runner + image_jobs",
      "observed_at": "2026-08-05T14:32:11.000Z",
      "valid_until": "2026-08-05T14:32:21.000Z",
      "reason": "1 job failed in the last 24 hours. Last failure: ComfyUI returned HTTP 502."
    },
    "recipes": {
      "state": "available",
      "value": {
        "total": 12,
        "available": 8,
        "unavailable": 4
      },
      "source": "image_recipes",
      "observed_at": "2026-08-05T14:32:11.000Z",
      "valid_until": "2026-08-05T14:32:41.000Z",
      "evidence_ref": "probe:image:recipes:8b9c0d1e"
    },
    "characters": {
      "state": "available",
      "value": {
        "total": 5,
        "with_lora": 3,
        "with_reference": 2
      },
      "source": "image_characters",
      "observed_at": "2026-08-05T14:32:11.000Z",
      "valid_until": "2026-08-05T14:32:41.000Z"
    },
    "comfyui": {
      "state": "unavailable",
      "value": null,
      "source": "comfyui_probe",
      "observed_at": "2026-08-05T14:32:11.000Z",
      "valid_until": "2026-08-05T14:32:21.000Z",
      "reason": "ComfyUI is not running. Start it with: ./kitty image up"
    },
    "runpod": {
      "state": "unavailable",
      "value": null,
      "source": "runpod_probe",
      "observed_at": "2026-08-05T14:32:11.000Z",
      "valid_until": "2026-08-05T14:32:21.000Z",
      "reason": "RUNPOD_API_KEY is not configured"
    }
  }
}
```

**Owners:**
- `generation` — `image_runner` + `image_jobs`
- `recipes` — `image_recipes`
- `characters` — `image_characters`
- `comfyui` — ComfyUI API probe
- `runpod` — RunPod API probe

**TTLs:**
- `generation` — 10 seconds
- `recipes` — 30 seconds (recipe availability changes with operator action)
- `characters` — 30 seconds
- `comfyui` — 10 seconds
- `runpod` — 10 seconds

**Rules:**
- `generation.queue_depth` is the number of jobs waiting for a worker. `active_jobs` is running jobs.
- `generation` is `degraded` when any job in the last 24 hours failed. It is `unavailable` when no generation backend (ComfyUI or RunPod) is available.
- `comfyui` is `unavailable` when the ComfyUI API does not respond. It is never `unknown` — the probe is definitive.
- `runpod` is `unavailable` when the API key is not configured. It is `unknown` when the key is configured but the API does not respond.

### 3.11 `shell`

Open WebUI shell state. Reports the shell's version, database health, extension health, and connection to Kitty Gateway.

```json
{
  "shell": {
    "openwebui": {
      "state": "available",
      "value": {
        "version": "0.10.2",
        "pinned": true,
        "database": {
          "state": "available",
          "size_bytes": 2457600,
          "chat_count": 47,
          "last_backup_at": "2026-08-05T12:00:00.000Z"
        },
        "extensions": {
          "state": "degraded",
          "value": {
            "count": 8,
            "active": 7,
            "failed": 1,
            "failed_names": ["kitty_auto_router"]
          },
          "observed_at": "2026-08-05T14:32:11.000Z",
          "valid_until": "2026-08-05T14:32:21.000Z",
          "reason": "1 extension failed to load: kitty_auto_router (ImportError: No module named 'gateway')"
        },
        "gateway_connection": {
          "state": "available",
          "value": {
            "endpoint": "http://127.0.0.1:8000/v1",
            "latency_ms": 12
          },
          "observed_at": "2026-08-05T14:32:11.000Z",
          "valid_until": "2026-08-05T14:32:16.000Z",
          "evidence_ref": "probe:openwebui:gateway:1a2b3c4d"
        }
      },
      "source": "openwebui_shell_probe",
      "observed_at": "2026-08-05T14:32:11.000Z",
      "valid_until": "2026-08-05T14:32:16.000Z"
    }
  }
}
```

**Owner:** `openwebui_shell_probe` — a Gateway-side probe that queries Open WebUI's health endpoints

**TTL:** 5 seconds

**Rules:**
- This section reports on the Open WebUI **process**, not on its internal database content. Kitty never reads Open WebUI's internal database (ADR 0033).
- `version` and `pinned` come from `scripts/openwebui_local.py` configuration.
- `database.size_bytes` and `chat_count` come from Open WebUI's own health endpoint if available, or from filesystem inspection of `webui.db` as a fallback.
- `extensions` reports the Kitty-owned extensions (Event Functions, Filters, Pipes, Actions) loaded into Open WebUI. An extension that fails to load is a `degraded` condition on the extensions section.
- `gateway_connection` is Open WebUI's perspective on whether it can reach the Gateway. This is distinct from `connections.gateway` (the Gateway's own health check).
- If Open WebUI is not running, the entire `shell.openwebui` container is `unavailable` with reason "Open WebUI is not running."

### 3.12 `approvals`

Active approval policy and pending decisions.

```json
{
  "approvals": {
    "state": "available",
    "value": {
      "policy_version": "action_tiers.json",
      "tiers": {
        "T0": "auto — safe reads, local calculations, health probes",
        "T1": "auto — bounded reads, drafting, new files in worktrees, queuing approved-scope work",
        "T2": "request approval — push, merge, delete, external messages, secrets, auth, paid execution, heavy deps, broad scope"
      },
      "disabled": [],
      "auto_execute_tiers": ["T0", "T1"],
      "approval_required_tiers": ["T2"],
      "pending_decisions": 0
    },
    "source": "action_tiers.json",
    "observed_at": "2026-08-05T14:32:11.000Z",
    "valid_until": "2026-08-05T14:33:11.000Z"
  }
}
```

**Owner:** `action_tiers.json` (the policy file) + `decision_store` (for pending decisions)

**TTL:** 60 seconds (policy changes are rare; pending decisions may accumulate)

### 3.13 `health`

Aggregate health summary for quick scanning. Every component reports into this section.

```json
{
  "health": {
    "state": "degraded",
    "value": {
      "components": [
        {
          "component": "gateway",
          "state": "available"
        },
        {
          "component": "litellm",
          "state": "available"
        },
        {
          "component": "builder",
          "state": "degraded",
          "reason": "3 partial packet records"
        },
        {
          "component": "memory_graph",
          "state": "available"
        },
        {
          "component": "mem0",
          "state": "available"
        },
        {
          "component": "chromadb",
          "state": "degraded",
          "reason": "collection memory_v1 reports 0 embeddings"
        },
        {
          "component": "comfyui",
          "state": "unavailable",
          "reason": "not running"
        },
        {
          "component": "runpod",
          "state": "unavailable",
          "reason": "not configured"
        },
        {
          "component": "mcp_servers",
          "state": "degraded",
          "reason": "web-fetch MCP is unavailable; shell MCP is degraded"
        },
        {
          "component": "openwebui",
          "state": "degraded",
          "reason": "1 extension failed to load"
        },
        {
          "component": "pricing",
          "state": "stale",
          "reason": "20.5 hours old"
        }
      ],
      "summary": {
        "available": 3,
        "degraded": 4,
        "unavailable": 2,
        "stale": 1,
        "unknown": 0
      }
    },
    "source": "manifest composer",
    "observed_at": "2026-08-05T14:32:11.000Z",
    "valid_until": "2026-08-05T14:32:16.000Z"
  }
}
```

**Owner:** manifest composer (derived from all other sections)
**TTL:** 5 seconds

**Rules:**
- The health section is a computed summary, not an independently probed section. It derives from all other sections' states.
- The container `state` is the worst state among all components: `unknown` > `stale` > `unavailable` > `degraded` > `available`.
- The `summary` counts components in each state for quick diagnostics.

---

## 4. Ownership table

Every field has exactly one owner. This table is the definitive mapping. When a field's owner is unclear, it does not belong in the manifest.

| Manifest path | Owner subsystem | Probe type | TTL |
|---|---|---|---|
| `application.*` | build_metadata / env | static | 24h |
| `clock` | host_clock | computed | 1s |
| `context.active_project` | project_context + project_store | db read | 30s |
| `context.repository` | git subprocess | shell probe | 5s |
| `execution.builder` | builder_runtime | db read (ro) | 10s |
| `execution.builder_attention` | builder_runtime | db read (ro) | 10s |
| `inference.routing_mode` | gateway config | static | 24h |
| `inference.available_models` | litellm:/v1/models | http probe | 15s |
| `inference.providers` | provider_config + litellm | config + probe | 15s |
| `inference.pricing` | openrouter_pricing_cache | cache read | 8h |
| `connections.gateway` | gateway health | internal | 5s |
| `connections.litellm` | litellm probe | http probe | 5s |
| `tools` | gateway route registry | internal | 10s |
| `mcp_servers` | mcp_registry | process probe | 10s |
| `memory.memory_graph` | memory_graph | internal | 5s |
| `memory.mem0` | mem0 client | internal | 5s |
| `memory.chromadb` | chromadb client | internal | 5s |
| `image.generation` | image_runner + image_jobs | db read | 10s |
| `image.recipes` | image_recipes | db read | 30s |
| `image.characters` | image_characters | db read | 30s |
| `image.comfyui` | comfyui_probe | http probe | 10s |
| `image.runpod` | runpod_probe | http probe | 10s |
| `shell.openwebui` | openwebui_shell_probe | http + fs probe | 5s |
| `approvals` | action_tiers.json + decision_store | file + db read | 60s |
| `health` | manifest composer | computed | 5s |

### Owner contract

Each owner must provide a probe function with this signature:

```python
async def probe_<subsystem>() -> dict[str, Any]:
    """Return a fact envelope for this subsystem.

    Must return within the subsystem's deadline (default 3 seconds).
    Must never raise — catch all errors and return an unknown or unavailable fact.
    Must use _fact(), _unknown(), or an equivalent envelope constructor.
    """
```

If a subsystem cannot probe within its deadline, it must respond with `unknown` and a reason that names the timeout. The composer does not fabricate an `unavailable` state for a timed-out subsystem.

---

## 5. Composer: update rules

The manifest composer (`gateway/runtime_manifest.py:compose_manifest`) follows these rules in order.

### 5.1 Generation

1. **Create the timestamp anchor.** `now = datetime.now(timezone.utc)`. All `observed_at` values derive from this moment.
2. **Compute TTLs.** Every probe uses its field-specific TTL (from the ownership table) to set `valid_until = now + TTL`.
3. **Fan out probes.** Launch all probe functions concurrently. Each probe is bounded by a per-source timeout (default 3 seconds for most probes; git gets 3 seconds; LLM endpoints get 1.5 seconds). A probe that exceeds its timeout does not block other probes.
4. **Collect results.** Each probe returns a fact envelope. If a probe raises (despite the contract), the composer wraps it in `unknown` with the exception message.
5. **Assemble the body.** Populate every section of the schema with the probe results. Sections without an active probe are omitted from the manifest.
6. **Derive health.** Compute the `health` section from all other sections' states.
7. **Compute revision.** Serialize the body to canonical JSON, SHA-256 hash, take first 16 hex characters as the revision.
8. **Assign manifest_id.** `runtime-<revision>`.
9. **Return the complete manifest.**

### 5.2 Stale detection

A fact is stale when `valid_until < now`. The composer computes staleness at generation time, not at probe time. That means:

- A fact with `valid_until` in the past is **stale at the moment of generation**.
- The composer does **not** auto-promote stale facts to `unknown`. The owning subsystem's next probe is the only thing that can change the state.
- A consumer that receives a manifest must check every fact's `valid_until` against the consumer's own clock. If a fact is stale, the consumer must treat it as stale regardless of what the manifest says. (The manifest's `valid_until` at the top level is the composer's best guess; the consumer's clock is authoritative for staleness decisions.)

### 5.3 Caching and revisioned snapshots

- Every manifest generation produces an immutable revision. The revision changes only when the manifest content changes.
- `GET /runtime/manifest` returns the latest manifest. If the revision has not changed since the last request, the client may skip processing.
- `GET /runtime/manifest?project_id=1` scopes the manifest to a specific project.
- The manifest is **never cached at the HTTP layer**. It is a live snapshot. Cache headers forbid CDN or browser caching. Clients cache it in memory and invalidate on their own schedule.

### 5.4 SSE patches (future)

When implemented (Phase 2+), the Gateway will offer `GET /runtime/manifest/stream` (Server-Sent Events). Clients that maintain a live connection receive:

- A full snapshot on connect (current manifest).
- Revisioned patches when any section changes: `{"revision": "a1b2c3d4", "patch": {"context": {"repository": {...}}}}`.
- A heartbeat every 15 seconds: `{"revision": "a1b2c3d4", "heartbeat": true}`.

Clients apply patches to their local manifest and increment the revision. If a patch references a revision the client does not have, the client requests a fresh snapshot.

---

## 6. The compact prompt projection

The full manifest is too large for a model prompt (~3-5KB of JSON). The `compact_runtime_context` function produces a smaller projection containing only facts relevant to the current turn.

### Projection rules

1. **Drop the health section entirely.** The model does not need component-level health breakdowns.
2. **Summarize Builder.** Replace the full `builder.value` with initiative count, queue summary, and attention states only. Drop worker sessions and integrity details.
3. **Drop MCP server tool catalogs.** Keep server names and connection states; drop per-server tool lists.
4. **Drop image section entirely** unless the turn is an image generation request.
5. **Drop pricing details.** Keep only whether pricing is fresh or stale.
6. **Keep all context, inference, connections, tools, and approvals.**
7. **Wrap in a structured XML tag:** `<kitty_runtime_truth>...</kitty_runtime_truth>` so the model can distinguish manifest facts from user content.

### Projection example

```xml
<kitty_runtime_truth>
{
  "manifest_revision": "a1b2c3d4e5f6g7h8",
  "generated_at": "2026-08-05T14:32:11.000Z",
  "application": {"name": "Kitty", "environment": "local"},
  "clock": {"current_time": "2026-08-05T14:32:11.000Z", "timezone": "America/Denver"},
  "context": {
    "active_project": "kitty (code)",
    "repository": {"branch": "main", "commit": "d3c82748", "dirty": true}
  },
  "execution": {
    "builder": {"queue_depth": 2, "blocked": 10, "attention": ["Trustworthy KittyBuilder stalled"]}
  },
  "inference": {
    "routing_mode": "gateway + LiteLLM",
    "available_models": ["kitty-default", "kitty-small", "kitty-think"],
    "providers": {"openrouter": "available", "deepseek": "unavailable"},
    "pricing_fresh": false
  },
  "connections": {"gateway": "available", "litellm": "available"},
  "tools": {
    "memory": "available",
    "notes": "available",
    "projects": "available",
    "calendar": "available",
    "tutor": "available",
    "builder": "available",
    "capture": "available"
  },
  "mcp_servers": ["filesystem (ok)", "git (ok)", "shell (degraded)", "web-fetch (down)"],
  "memory_health": "available",
  "shell": "Open WebUI 0.10.2 (ok, 1 extension degraded)",
  "approvals": {"auto_tiers": ["T0", "T1"], "pending_decisions": 0}
}
</kitty_runtime_truth>
```

### Projection binding

Every chat turn records the `manifest_revision` it was bound to. If the manifest changes during a conversation, subsequent turns bind to the new revision. This makes it auditable: "What did Kitty know when it answered that question?"

---

## 7. Consumer contract

Every consumer of the manifest — Open WebUI's Event Functions, the Kitty Console, the compact prompt projection, SSE clients, Home, Brief — must obey these rules.

### Must do

1. **Check `valid_until` on every consumed fact.** If a fact is past its TTL, treat it as stale.
2. **Always display the reason.** When a fact is not `available`, show the reason to the user. Never hide it behind a generic error.
3. **Never infer a better state.** A fact that is `unknown` must not be rendered as `unavailable` or `false`.
4. **Never fabricate a value.** When the value is `null`, display "not available" or the reason — never `$0`, never `0`, never `false`, never an empty list that looks like "nothing to show".
5. **Use the compact projection for prompts.** Never inline the full manifest. The projection is designed for model consumption.
6. **Bind every turn to a manifest revision.** Record which revision was active when the turn was dispatched.
7. **Re-fetch on project switch.** When the active project changes, the manifest must be refreshed.

### Must not do

1. **Do not define model identities independently.** If the manifest says a model is `unavailable`, the UI must not offer it in a dropdown.
2. **Do not hardcode capability assumptions.** "Kitty can search memory" is true only when the manifest's `tools` section shows `memory.search` as `available`.
3. **Do not cache indefinitely.** The manifest expires. A cached manifest older than its shortest TTL is stale.
4. **Do not compose a separate truth.** There is one manifest. All surfaces consume it. A surface that builds its own truth path is a defect.
5. **Do not read the manifest and then ignore it.** A consumer that loads the manifest and then displays hardcoded text ("All systems operational") when the manifest says `degraded` is lying.

---

## 8. Open WebUI integration

Open WebUI receives the manifest through two paths.

### 8.1 Event Function injection

The `kitty_context_injector` Event Function (from the product plan) queries `GET /runtime/manifest` at `on_chat_start` and injects the compact prompt projection into the system prompt. This is the primary path for model context.

### 8.2 Shell health display

A second Event Function, `kitty_shell_status`, queries the manifest at `on_chat_start` and displays a Rich UI card above the first message:

```
Kitty · Auto (gpt-5.4) · Cloud  |  Builder 2 queued  |  Memory ok  |  1 MCP down
```

This card uses only the `health.summary` and `inference` sections. It is the terse "is everything ok?" glance.

### 8.3 Tool availability gating

Before the model calls a tool, the `kitty_tool_auth` Event Function checks the manifest's `tools` section. If the target tool is `unavailable` or `unknown`, the function call is blocked before execution. The model receives the reason in the tool response. This prevents the model from calling a tool that the Gateway cannot service.

### 8.4 Shell boundary

Open WebUI never composes its own runtime truth. Its internal state (persisted chats, user settings, version) is private to the shell. When the shell needs a fact about Kitty — "what models are available?", "is Builder running?", "can I search memory?" — it reads the manifest through the Gateway. The Gateway is the authority; the manifest is the contract.

---

## 9. Schema evolution

### Versioning

- The manifest carries `schema_version` at the top level. The current version is `2`.
- Every schema change increments the version. A consumer that does not understand the new version must fail with an explicit message, never silently parse a subset.
- Schema changes are additive only. No field is ever removed without a deprecation window. A deprecated field carries `"deprecated": true` for one schema version before removal.

### Migration

- When `schema_version` increments, the composer must support both the old and new schema for one version cycle.
- The old schema is served at `GET /runtime/manifest?v=1`. The new schema is the default.
- After one version cycle, the old endpoint is removed and consumers that have not migrated will receive a 400 with "schema version 1 is no longer supported; upgrade to v2."

### Stability guarantees

- The top-level sections (`application`, `clock`, `context`, `execution`, `inference`, `connections`, `tools`, `mcp_servers`, `memory`, `image`, `shell`, `approvals`, `health`) are stable from v2 onward. They will not be renamed.
- New top-level sections may be added in minor schema versions.
- Fields within sections may be added freely; they will not break existing consumers.
- The fact envelope (`state`, `value`, `source`, `observed_at`, `valid_until`, `evidence_ref`, `reason`) is stable and will not change.
- The state lattice (`available`, `unavailable`, `degraded`, `stale`, `unknown`) is stable and will not gain or lose states without a major schema version.

---

## 10. Implementation mapping

This specification maps to the existing codebase as follows.

| Specification section | Existing implementation | Gaps (from v1 in `gateway/runtime_manifest.py`) |
|---|---|---|
| Fact envelope | `_fact()`, `_unknown()` in `runtime_manifest.py` | Missing `evidence_ref` field. Add to all facts. |
| `application` | Present, partial | Add `build_commit`, `environment` as facts. |
| `clock` | Present | Use fact envelope shape. |
| `context.active_project` | `_project_fact()` | Already correct. |
| `context.repository` | `_git_snapshot()` + `_fact()` | Already correct. |
| `execution.builder` | `_builder_fact()` with `build_runtime_snapshot()` | Add `builder_attention` filter. Add worker session summary. |
| `inference.available_models` | `_litellm_models()` | Already correct. |
| `inference.providers` | `_provider_facts()` | Add per-provider health probes (not just config check). |
| `inference.pricing` | **Missing** | Add OpenRouter pricing cache probe. |
| `connections` | Present | Already correct. |
| `tools` | `_tool_fact()` | Replace hardcoded list with route registry scan. Add per-tool health. Add `write-notify` tools (remember, capture). |
| `mcp_servers` | **Missing** | Add MCP registry probe. |
| `memory.*` | **Missing** | Add memory_graph, mem0, chromadb probes. |
| `image.*` | **Missing** | Add image_jobs, recipes, characters, comfyui, runpod probes. |
| `shell.openwebui` | **Missing** | Add Open WebUI shell probe. |
| `approvals` | `_approval_fact()` | Add pending decision count. |
| `health` | **Missing** | Add computed health summary. |
| Compact projection | `compact_runtime_context()` | Update for v2 schema sections. |
| SSE patches | **Missing** | Future Phase 2+. |
| Stale detection | `MANIFEST_TTL_SECONDS` (global 15s) | Replace with per-field TTLs per ownership table. |

### Implementation priority

Phase 1 (one packet):
1. Add `evidence_ref` to the fact envelope.
2. Add per-field TTLs (replace global `MANIFEST_TTL_SECONDS`).
3. Add the missing probes: pricing, MCP servers, memory, image, shell, health.
4. Update consumable surfaces (Open WebUI Event Functions, compact projection) to use the v2 schema.

Phase 2 (one packet):
1. SSE streaming endpoint with revisioned patches.
2. `GET /runtime/manifest?v=1` backward compatibility.

Phase 3 (ongoing):
1. Deprecate v1 when all consumers have migrated.
2. Add new sections as subsystems mature.

---

## 11. Honesty guarantees

This specification makes six guarantees about the manifest's relationship to reality.

| # | Guarantee |
|---|---|
| G1 | **Every fact names its source.** You can trace from "available_models is unavailable" to "litellm:/v1/models returned HTTP 502" to the raw probe response. |
| G2 | **No fact is composed from vibes.** The composer collects facts from owners. It does not synthesize, average, soften, or guess. |
| G3 | **TTLs are enforced, not suggested.** A fact that is 16 seconds old with a 15-second TTL is stale. The composer reports it as stale. The consumer treats it as stale. There is no grace period. |
| G4 | **Unknown is not unavailable.** A probe that fails is `unknown`. A capability that is explicitly disabled is `unavailable`. These are different. They always have different reasons. They are never conflated. |
| G5 | **Every state transition is recorded.** The manifest's revision changes when any fact changes state. The revision history is the audit trail of Kitty's runtime truth. |
| G6 | **The manifest is consumed, not questioned.** A surface that reads the manifest and then decides to show something different is a bug. The manifest is the single source of runtime truth. There is no override, no fallback truth, no "but actually..." path. |

---

## 12. Relation to other specifications

- **Constitution v1 §III.5 (Honest State):** The proposed manifest implements the five-state lattice. Every fact obeys the honesty rules. No fact is ever fabricated.
- **ADR 0029 (Capability Manifest Single Truth):** Ratifies the *principle* of a single capability-manifest source of runtime truth. This contract is a proposed implementation of that principle; ADR 0029 does not ratify this specific schema. The KPA-01 schema outline it references is design history, not a superseded authority.
- **ADR 0032 (Evidence-Backed Claims):** The proposed `evidence_ref` field implements the evidence requirement. Every claim about capability traces to a probed source.
- **docs/OPENWEBUI_PRODUCT_PLAN.md:** The product plan's Event Functions (`kitty_context_injector`, `kitty_shell_status`, `kitty_tool_auth`) are intended to consume this manifest. The manifest is the proposed data contract between Gateway and shell.
- **gateway/runtime_manifest.py / gateway/builder_status.py:** The **current** runtime-truth implementation (v1). This contract proposes v2; the existing code is both the starting point for implementation and the authority for actual current behavior until a ratified manifest replaces it.

`KITTY_PRODUCT_ARCHITECTURE.md §4` first sketched a CapabilityManifest schema; this contract develops that sketch in greater detail (MCP, memory, image, shell sections the original deferred). `KITTY_PRODUCT_ARCHITECTURE.md` is design history, not a ratified authority for this schema — only ADR 0029, ADR 0032, and the Constitution are.
