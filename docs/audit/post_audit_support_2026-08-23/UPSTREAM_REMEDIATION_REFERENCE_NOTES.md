# Kitty Upstream Remediation Reference Notes

Status: reference material only. These are authoritative implementation patterns to consult AFTER the audit proves a Kitty finding. They are not prescriptions for changing Kitty.

## 1. Official MCP Python SDK

Current official MCP Python SDK docs identify v2 as the stable release line. The client has one explicit lifecycle: construct it, enter `async with`, use typed async protocol methods, then disconnect on exit.

Useful implications if the audit confirms Kitty's hand-rolled MCP client bridge should migrate:
- prefer official `Client`/transport semantics over custom JSON-RPC;
- inspect server capabilities and negotiated protocol version rather than hard-coding assumptions;
- use typed `list_tools()` / `call_tool()` results;
- handle `is_error` as protocol-level tool failure;
- use in-memory client connections for integration tests where possible;
- use Streamable HTTP for normal HTTP production transport;
- keep lifecycle and transport ownership explicit.

Official references:
- https://py.sdk.modelcontextprotocol.io/
- https://py.sdk.modelcontextprotocol.io/client/
- https://github.com/modelcontextprotocol/python-sdk

Important migration caution: v2 is a breaking major version. If current Kitty dependency is v1, migration must inspect current pin/API first rather than copying v2 code blindly.

## 2. SQLite live backup and integrity

SQLite's Online Backup API is designed to create a consistent snapshot of a live database while limiting source locking. The Python sqlite3 connection exposes corresponding backup support.

For backup/restore remediation, useful proof concepts are:
- snapshot every supported record/store rather than arbitrary list limits;
- validate snapshot shape before mutating destination state;
- verify restored SQLite databases with `PRAGMA integrity_check`;
- separately use `PRAGMA foreign_key_check` because integrity_check does not detect foreign-key violations;
- test malformed restore and mid-restore failure against isolated state;
- prove round-trip fidelity, not merely successful function return.

Official references:
- https://sqlite.org/backup.html
- https://sqlite.org/c3ref/backup_finish.html
- https://sqlite.org/pragma.html
## 3. Blocking I/O inside async Gateway paths

Python's official asyncio docs state that calling blocking I/O directly inside a coroutine blocks the event loop. `asyncio.to_thread()` is intended for I/O-bound functions that would otherwise block that loop.

If the audit verifies slow synchronous integrations inside async routes, the remediation should first measure concurrent-request impact, then choose one of:
- native async client/API;
- `asyncio.to_thread()` for bounded I/O-bound legacy functions;
- subprocess APIs that are already asynchronous;
- architectural isolation only when measurement justifies it.

Do not offload trivial synchronous work merely for stylistic consistency.

Official reference:
- https://docs.python.org/3/library/asyncio-task.html#asyncio.to_thread

## 4. HTTP client lifetime / connection reuse

HTTPX official guidance recommends a `Client` for non-trivial repeated HTTP use because top-level calls establish new connections rather than reusing pooled connections. Client instances provide connection pooling and reduced repeated handshake overhead.

If the audit confirms client-lifecycle fragmentation, evaluate each subsystem for:
- repeated same-host traffic;
- explicit timeout ownership;
- clean shutdown/lifecycle;
- event-loop ownership for AsyncClient;
- provider-specific retry semantics;
- observability requirements.

Do not force every integration through one global client if loop ownership or isolation makes that unsafe.

Official reference:
- https://www.python-httpx.org/advanced/clients/

## 5. npm vulnerability gates

Current npm docs state `npm audit` exits non-zero when vulnerabilities meet the configured threshold, and `--audit-level` selects the minimum severity that causes failure.

Therefore, if the audit decides HIGH production vulnerabilities must gate Kitty CI, the clean mechanism is to make the audit step non-advisory and choose an explicit threshold rather than parsing human output.

Use `npm audit` for reporting/gating; do not run `npm audit fix` automatically in CI because it mutates dependency resolution/install state.

Official reference:
- https://docs.npmjs.com/cli/v11/commands/npm-audit/
