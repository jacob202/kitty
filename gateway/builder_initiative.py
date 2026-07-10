"""KittyBuilder KB-S1A — initiative manifests: validation, persistence, apply.

An *initiative* is a versioned JSON manifest describing an ordered set of work
*packets* (objective, acceptance criteria, allowed paths, dependencies). This
module validates manifests, persists them durably, and materializes exactly
one queue task per packet — atomically and idempotently.

Scope boundaries (KB-S1A):

- No worker, worktree, branch, PR, or GitHub mutation happens here. Apply
  only writes rows to the Builder queue DB.
- The queue task state machine in gateway/builder_queue.py is used unchanged.
  Orchestration state (dependency eligibility, initiative status) is modeled
  in separate tables, added by later packets — never by widening task states.
- Idempotency is belt-and-braces: the ``initiative_packets`` mapping table is
  authoritative, and each materialized task also carries
  ``bridge_external_id = "<initiative_id>/<packet_id>"`` so the existing
  unique bridge index in the tasks table independently rejects duplicates.

Storage lives in the same SQLite DB as the queue (BUILDER_QUEUE_DB) so that
initiative + packet mappings + queue tasks commit in one transaction.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from graphlib import CycleError, TopologicalSorter
from pathlib import Path
from typing import Any

from gateway import builder_queue as bq

MANIFEST_VERSION = 1

# Initiative states. KB-S1A only creates 'active'. KB-S1B adds the read-only
# rollup states below, derived from per-packet task state — never by writing
# task rows. Completion/pause *transitions* remain owned by later packets.
INITIATIVE_ACTIVE = "active"
INITIATIVE_COMPLETED = "completed"
INITIATIVE_FAILED = "failed"
INITIATIVE_PAUSED = "paused"

# Task states that make a dependency permanently unsatisfiable.
_BLOCKING_STATES = frozenset({bq.FAILED, bq.CANCELLED})

# \Z, not $: $ would accept a trailing newline in an ID.
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")

_TOP_LEVEL_KEYS = frozenset(
    {"manifest_version", "initiative_id", "title", "description", "packets"}
)
_PACKET_KEYS = frozenset(
    {
        "id",
        "title",
        "objective",
        "depends_on",
        "acceptance_criteria",
        "allowed_paths",
        "policy",
        "validation_commands",
    }
)
_MAX_VALIDATION_COMMANDS = 20
_POLICY_KEYS = frozenset({"max_attempts", "priority"})

# bridge_source for tasks materialized from initiative packets.
BRIDGE_SOURCE = "initiative"


class ManifestError(ValueError):
    """Raised when a manifest fails semantic validation.

    ``errors`` carries the full list so the CLI can print every problem in
    one pass instead of one-error-per-run whack-a-mole.
    """

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


class InitiativeConflictError(ValueError):
    """Raised when an initiative ID exists with different manifest contents."""


class InitiativeNotFoundError(ValueError):
    """Raised when an initiative ID does not exist."""


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS initiatives (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    manifest_version INTEGER NOT NULL,
    manifest_json TEXT NOT NULL,
    manifest_sha256 TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'active',
    pause_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS initiative_packets (
    initiative_id TEXT NOT NULL,
    packet_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    title TEXT NOT NULL,
    objective TEXT NOT NULL,
    depends_on_json TEXT NOT NULL,
    acceptance_criteria_json TEXT NOT NULL,
    allowed_paths_json TEXT NOT NULL,
    policy_json TEXT,
    validation_commands_json TEXT,
    task_id TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (initiative_id, packet_id),
    FOREIGN KEY (initiative_id) REFERENCES initiatives(id),
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);
"""


def _ensure_packet_columns(conn: sqlite3.Connection) -> None:
    """Add KB-S3a columns to initiative_packets tables created before them."""
    existing = {
        str(row["name"])
        for row in conn.execute("PRAGMA table_info(initiative_packets)").fetchall()
    }
    if existing and "validation_commands_json" not in existing:
        conn.execute(
            "ALTER TABLE initiative_packets ADD COLUMN validation_commands_json TEXT"
        )


def _ensure_initiative_columns(conn: sqlite3.Connection) -> None:
    """Add durable operator-pause metadata to pre-KB-S5 databases."""
    existing = {
        str(row["name"])
        for row in conn.execute("PRAGMA table_info(initiatives)").fetchall()
    }
    if existing and "pause_reason" not in existing:
        conn.execute("ALTER TABLE initiatives ADD COLUMN pause_reason TEXT")


def init_db(db_path: Path | None = None) -> None:
    """Ensure the queue schema plus initiative tables exist. Idempotent."""
    bq.init_db(db_path)
    conn = bq.connect(db_path)
    try:
        _ensure_packet_columns(conn)
        conn.executescript(_SCHEMA_SQL)
        _ensure_initiative_columns(conn)
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Canonicalization / hashing
# ---------------------------------------------------------------------------


def canonicalize_manifest(manifest: dict[str, Any]) -> str:
    """Return the canonical JSON form: sorted keys, no whitespace, UTF-8."""
    return json.dumps(
        manifest,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def manifest_sha256(manifest: dict[str, Any]) -> str:
    """SHA-256 hex digest of the canonical manifest JSON."""
    return hashlib.sha256(
        canonicalize_manifest(manifest).encode("utf-8")
    ).hexdigest()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def load_manifest(path: Path) -> dict[str, Any]:
    """Read and JSON-parse a manifest file. Raises ManifestError on bad JSON."""
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise ManifestError([f"cannot read manifest: {exc}"]) from exc
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ManifestError([f"manifest is not valid JSON: {exc}"]) from exc
    if not isinstance(parsed, dict):
        raise ManifestError(["manifest root must be a JSON object"])
    return parsed


def _is_int(value: Any) -> bool:
    # bool is an int subclass; a manifest saying "priority": true is a bug.
    return isinstance(value, int) and not isinstance(value, bool)


def _check_str_list(
    value: Any, label: str, errors: list[str], *, required: bool
) -> list[str]:
    """Validate a non-empty list of non-empty strings. Returns the list or []."""
    if value is None:
        if required:
            errors.append(f"{label} is required and must be a non-empty array")
        return []
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        errors.append(f"{label} must be an array of non-empty strings")
        return []
    if required and not value:
        errors.append(f"{label} is required and must be a non-empty array")
    return value


def _validate_allowed_path(path: str, label: str, errors: list[str]) -> None:
    if path.startswith("/") or path.startswith("~"):
        errors.append(f"{label}: allowed path must be repo-relative: {path!r}")
    if ".." in Path(path).parts:
        errors.append(f"{label}: allowed path must not contain '..': {path!r}")


def _validate_policy(policy: Any, label: str, errors: list[str]) -> None:
    if not isinstance(policy, dict):
        errors.append(f"{label}: policy must be a JSON object")
        return
    unknown = set(policy) - _POLICY_KEYS
    if unknown:
        errors.append(f"{label}: unknown policy keys: {sorted(unknown)}")
    if "max_attempts" in policy and (
        not _is_int(policy["max_attempts"]) or policy["max_attempts"] < 1
    ):
        errors.append(f"{label}: policy.max_attempts must be an integer >= 1")
    if "priority" in policy and not _is_int(policy["priority"]):
        errors.append(f"{label}: policy.priority must be an integer")


def validate_manifest(manifest: Any) -> list[str]:
    """Semantic validation. Returns the full list of problems (empty = valid)."""
    errors: list[str] = []
    if not isinstance(manifest, dict):
        return ["manifest root must be a JSON object"]

    unknown = set(manifest) - _TOP_LEVEL_KEYS
    if unknown:
        errors.append(f"unknown top-level keys: {sorted(unknown)}")

    version = manifest.get("manifest_version")
    if version != MANIFEST_VERSION:
        errors.append(
            f"manifest_version must be {MANIFEST_VERSION}, got {version!r}"
        )

    initiative_id = manifest.get("initiative_id")
    if not isinstance(initiative_id, str) or not _ID_RE.match(initiative_id):
        errors.append(
            "initiative_id must match "
            f"{_ID_RE.pattern!r}, got {initiative_id!r}"
        )

    title = manifest.get("title")
    if not isinstance(title, str) or not title.strip():
        errors.append("title is required and must be a non-empty string")

    description = manifest.get("description")
    if description is not None and not isinstance(description, str):
        errors.append("description must be a string when present")

    packets = manifest.get("packets")
    if not isinstance(packets, list) or not packets:
        errors.append("packets must be a non-empty array")
        return errors

    seen_ids: set[str] = set()
    deps_by_id: dict[str, list[str]] = {}
    for i, packet in enumerate(packets):
        label = f"packets[{i}]"
        if not isinstance(packet, dict):
            errors.append(f"{label} must be a JSON object")
            continue

        unknown = set(packet) - _PACKET_KEYS
        if unknown:
            errors.append(f"{label}: unknown keys: {sorted(unknown)}")

        packet_id = packet.get("id")
        if not isinstance(packet_id, str) or not _ID_RE.match(packet_id):
            errors.append(
                f"{label}: id must match {_ID_RE.pattern!r}, got {packet_id!r}"
            )
            packet_id = None
        elif packet_id in seen_ids:
            errors.append(f"{label}: duplicate packet id {packet_id!r}")
            packet_id = None
        else:
            seen_ids.add(packet_id)
            label = f"packet {packet_id!r}"

        for field in ("title", "objective"):
            value = packet.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(
                    f"{label}: {field} is required and must be a non-empty string"
                )

        _check_str_list(
            packet.get("acceptance_criteria"),
            f"{label}: acceptance_criteria",
            errors,
            required=True,
        )
        allowed = _check_str_list(
            packet.get("allowed_paths"),
            f"{label}: allowed_paths",
            errors,
            required=True,
        )
        for path in allowed:
            _validate_allowed_path(path, label, errors)

        commands = _check_str_list(
            packet.get("validation_commands"),
            f"{label}: validation_commands",
            errors,
            required=False,
        )
        if len(commands) > _MAX_VALIDATION_COMMANDS:
            errors.append(
                f"{label}: validation_commands must have at most "
                f"{_MAX_VALIDATION_COMMANDS} entries"
            )

        deps = _check_str_list(
            packet.get("depends_on"), f"{label}: depends_on", errors,
            required=False,
        )
        if packet_id is not None:
            deps_by_id[packet_id] = deps

    # Dependency checks only make sense over the packets that parsed cleanly.
    for packet_id, deps in deps_by_id.items():
        for dep in deps:
            if dep == packet_id:
                errors.append(f"packet {packet_id!r}: depends on itself")
            elif dep not in seen_ids:
                errors.append(
                    f"packet {packet_id!r}: unknown dependency {dep!r}"
                )

    try:
        TopologicalSorter(
            {pid: [d for d in deps if d in seen_ids] for pid, deps in deps_by_id.items()}
        ).prepare()
    except CycleError as exc:
        cycle = exc.args[1] if len(exc.args) > 1 else []
        errors.append(f"dependency cycle: {' -> '.join(cycle)}")

    for i, packet in enumerate(packets):
        if isinstance(packet, dict) and "policy" in packet:
            pid = packet.get("id")
            label = f"packet {pid!r}" if isinstance(pid, str) else f"packets[{i}]"
            _validate_policy(packet["policy"], label, errors)

    return errors


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------


def apply_manifest(
    manifest: dict[str, Any],
    *,
    dry_run: bool = False,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Validate and apply a manifest. Atomic and idempotent.

    - First apply: creates the initiative row, one queue task per packet, and
      the packet→task mapping rows, all in one transaction.
    - Identical re-apply (same initiative_id, same canonical SHA-256):
      returns ``status="unchanged"`` and mutates nothing.
    - Changed contents under an existing initiative_id: raises
      InitiativeConflictError without any mutation.
    - ``dry_run=True`` performs every check and reports what would happen,
      guaranteed mutation-free.

    Returns ``{"status", "initiative_id", "manifest_sha256", "packets"}``
    where packets is ``[{"packet_id", "task_id"}, ...]`` (task_id is None in
    a would-create dry run).
    """
    errors = validate_manifest(manifest)
    if errors:
        raise ManifestError(errors)

    initiative_id = manifest["initiative_id"]
    digest = manifest_sha256(manifest)
    canonical = canonicalize_manifest(manifest)
    packets = manifest["packets"]

    init_db(db_path)
    conn = bq.connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT manifest_sha256 FROM initiatives WHERE id = ?",
            (initiative_id,),
        ).fetchone()
        if row is not None:
            if row["manifest_sha256"] != digest:
                raise InitiativeConflictError(
                    f"initiative {initiative_id!r} already exists with "
                    f"different contents (stored sha256 "
                    f"{row['manifest_sha256'][:12]}…, manifest {digest[:12]}…). "
                    "Initiative manifests are immutable; use a new "
                    "initiative_id for changed work."
                )
            mappings = [
                {"packet_id": r["packet_id"], "task_id": r["task_id"]}
                for r in conn.execute(
                    """
                    SELECT packet_id, task_id FROM initiative_packets
                    WHERE initiative_id = ? ORDER BY seq
                    """,
                    (initiative_id,),
                ).fetchall()
            ]
            conn.rollback()
            return {
                "status": "unchanged",
                "initiative_id": initiative_id,
                "manifest_sha256": digest,
                "packets": mappings,
            }

        if dry_run:
            conn.rollback()
            return {
                "status": "would_create",
                "initiative_id": initiative_id,
                "manifest_sha256": digest,
                "packets": [
                    {"packet_id": p["id"], "task_id": None} for p in packets
                ],
            }

        conn.execute(
            """
            INSERT INTO initiatives
                (id, title, manifest_version, manifest_json, manifest_sha256, state)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                initiative_id,
                manifest["title"],
                manifest["manifest_version"],
                canonical,
                digest,
                INITIATIVE_ACTIVE,
            ),
        )

        mappings = []
        for seq, packet in enumerate(packets):
            policy = packet.get("policy") or {}
            task = bq.create_task(
                f"[{packet['id']}] {packet['title']}",
                description=packet["objective"],
                acceptance_criteria=packet["acceptance_criteria"],
                priority=policy.get("priority", 0),
                allowed_paths=packet["allowed_paths"],
                bridge_source=BRIDGE_SOURCE,
                bridge_external_id=f"{initiative_id}/{packet['id']}",
                db_path=db_path,
                conn=conn,
            )
            validation_commands = packet.get("validation_commands") or []
            conn.execute(
                """
                INSERT INTO initiative_packets (
                    initiative_id, packet_id, seq, title, objective,
                    depends_on_json, acceptance_criteria_json,
                    allowed_paths_json, policy_json,
                    validation_commands_json, task_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    initiative_id,
                    packet["id"],
                    seq,
                    packet["title"],
                    packet["objective"],
                    json.dumps(packet.get("depends_on") or []),
                    json.dumps(packet["acceptance_criteria"]),
                    json.dumps(packet["allowed_paths"]),
                    json.dumps(policy) if policy else None,
                    json.dumps(validation_commands) if validation_commands else None,
                    task["id"],
                ),
            )
            mappings.append({"packet_id": packet["id"], "task_id": task["id"]})
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {
        "status": "created",
        "initiative_id": initiative_id,
        "manifest_sha256": digest,
        "packets": mappings,
    }


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------


def _row_to_packet(row: sqlite3.Row) -> dict[str, Any]:
    packet = dict(row)
    for column, key in (
        ("depends_on_json", "depends_on"),
        ("acceptance_criteria_json", "acceptance_criteria"),
        ("allowed_paths_json", "allowed_paths"),
        ("policy_json", "policy"),
        ("validation_commands_json", "validation_commands"),
    ):
        raw = packet.get(column)
        try:
            packet[key] = json.loads(raw) if raw is not None else None
        except (json.JSONDecodeError, TypeError) as exc:
            raise bq.DataCorruptionError(
                f"corrupted {column} for packet "
                f"{packet.get('initiative_id')}/{packet.get('packet_id')}: {exc}"
            ) from exc
    return packet


def list_initiatives(db_path: Path | None = None) -> list[dict[str, Any]]:
    """List initiatives with packet counts, newest last."""
    init_db(db_path)
    conn = bq.connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT i.id, i.title, i.manifest_version, i.manifest_sha256,
                   i.state, i.created_at, i.updated_at,
                   COUNT(p.packet_id) AS packet_count
            FROM initiatives i
            LEFT JOIN initiative_packets p ON p.initiative_id = i.id
            GROUP BY i.id
            ORDER BY i.created_at ASC, i.id ASC
            """
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_initiative(
    initiative_id: str, db_path: Path | None = None
) -> dict[str, Any] | None:
    """Return the initiative dict with its packets (ordered), or None."""
    init_db(db_path)
    conn = bq.connect(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM initiatives WHERE id = ?", (initiative_id,)
        ).fetchone()
        if row is None:
            return None
        initiative = dict(row)
        initiative["manifest"] = json.loads(initiative.pop("manifest_json"))
        packet_rows = conn.execute(
            """
            SELECT * FROM initiative_packets
            WHERE initiative_id = ? ORDER BY seq
            """,
            (initiative_id,),
        ).fetchall()
        initiative["packets"] = [_row_to_packet(r) for r in packet_rows]
        return initiative
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# KB-S1B — packet eligibility and initiative status (read-only)
# ---------------------------------------------------------------------------


def _read_packets_with_states(
    initiative_id: str, db_path: Path | None = None
) -> list[dict[str, Any]]:
    """Return each packet with its current task state, ordered by ``seq``.

    Raises InitiativeNotFoundError if the initiative row is absent. A packet
    whose task row is missing (should not happen post-apply) reports
    ``state=None`` rather than fabricating one.
    """
    init_db(db_path)
    conn = bq.connect(db_path)
    try:
        exists = conn.execute(
            "SELECT 1 FROM initiatives WHERE id = ?", (initiative_id,)
        ).fetchone()
        if exists is None:
            raise InitiativeNotFoundError(initiative_id)

        rows = conn.execute(
            """
            SELECT packet_id, seq, title, task_id, depends_on_json
            FROM initiative_packets
            WHERE initiative_id = ? ORDER BY seq
            """,
            (initiative_id,),
        ).fetchall()

        packets: list[dict[str, Any]] = []
        for r in rows:
            task = (
                bq._get_task_on_conn(conn, r["task_id"])
                if r["task_id"]
                else None
            )
            packets.append(
                {
                    "packet_id": r["packet_id"],
                    "seq": r["seq"],
                    "title": r["title"],
                    "task_id": r["task_id"],
                    "depends_on": json.loads(r["depends_on_json"])
                    if r["depends_on_json"]
                    else [],
                    "state": task["state"] if task else None,
                }
            )
        return packets
    finally:
        conn.close()


def _compute_unreachable(
    packets: list[dict[str, Any]]
) -> set[str]:
    """Packets that can never become eligible (transitive blocking closure).

    A packet is directly unreachable when a dependency's task is in a blocking
    state (``failed``/``cancelled``). That unreachability propagates to any
    packet depending on an already-unreachable packet, so a single failed
    dependency surfaces every downstream packet that will never run instead of
    silently leaving them perpetually non-eligible.
    """
    by_id = {p["packet_id"]: p for p in packets}
    unreachable: set[str] = set()

    for p in packets:
        for dep in p["depends_on"]:
            dep_p = by_id.get(dep)
            if dep_p is not None and dep_p["state"] in _BLOCKING_STATES:
                unreachable.add(p["packet_id"])
                break

    while True:
        added = False
        for p in packets:
            if p["packet_id"] in unreachable:
                continue
            if any(dep in unreachable for dep in p["depends_on"]):
                unreachable.add(p["packet_id"])
                added = True
        if not added:
            break
    return unreachable


def eligible_packets(
    initiative_id: str, db_path: Path | None = None
) -> list[dict[str, Any]]:
    """Packets ready to run now: own task ``queued`` and every dependency done.

    Unreachable packets (a blocking dependency) are excluded, as are packets
    still waiting on in-flight dependencies. Returned in ``seq`` order so
    selection is deterministic.
    """
    init_db(db_path)
    packets = _read_packets_with_states(initiative_id, db_path)

    by_id = {p["packet_id"]: p for p in packets}
    unreachable = _compute_unreachable(packets)

    eligible = []
    for p in packets:
        if p["packet_id"] in unreachable:
            continue
        if p["state"] != bq.QUEUED:
            continue
        if all(
            by_id[d]["state"] == bq.DONE
            for d in p["depends_on"]
            if d in by_id
        ):
            eligible.append(p)
    return eligible


def blocked_packets(
    initiative_id: str, db_path: Path | None = None
) -> list[dict[str, Any]]:
    """Packets unreachable because of a blocking dependency task.

    Each entry carries the direct blocking dependencies (the failed/cancelled
    tasks responsible) so operators see exactly which dependency must be
    resolved. Transitively blocked packets are included but list only their
    nearest blocking causes.
    """
    init_db(db_path)
    packets = _read_packets_with_states(initiative_id, db_path)

    by_id = {p["packet_id"]: p for p in packets}
    unreachable = _compute_unreachable(packets)

    blocked = []
    for p in packets:
        if p["packet_id"] not in unreachable:
            continue
        blockers = [
            {
                "packet_id": dep,
                "task_id": by_id[dep]["task_id"],
                "state": by_id[dep]["state"],
            }
            for dep in p["depends_on"]
            if dep in by_id and by_id[dep]["state"] in _BLOCKING_STATES
        ]
        blocked.append(
            {
                "packet_id": p["packet_id"],
                "task_id": p["task_id"],
                "blocked_by": blockers,
            }
        )
    return blocked


def next_packet(
    initiative_id: str, db_path: Path | None = None
) -> dict[str, Any] | None:
    """Deterministic next packet to run: lowest ``seq`` among eligible.

    Priority is advisory metadata only and does not influence ordering — the
    manifest's ``seq`` is the single source of truth for scheduling order.
    """
    eligible = eligible_packets(initiative_id, db_path)
    return eligible[0] if eligible else None


def initiative_status(
    initiative_id: str, db_path: Path | None = None
) -> dict[str, Any]:
    """Read-only rollup of an initiative's progress from task state.

    Returns the derived ``state`` (``active | completed | failed | paused``)
    plus per-bucket packet ids and the current ``next_packet``.

    State derivation (deterministic, over current task states):

    - ``completed``: every packet task is ``done``.
    - ``failed``: any packet task is ``failed``/``cancelled``, or any packet is
      unreachable due to a blocking dependency.
    - ``paused``: not completed and not failed, but no packet is eligible now
      (everything remaining waits on in-flight dependencies).
    - ``active``: at least one packet is eligible and ready to run.
    """
    initiative = get_initiative(initiative_id, db_path)
    if initiative is None:
        raise InitiativeNotFoundError(initiative_id)

    packets = _read_packets_with_states(initiative_id, db_path)
    unreachable = _compute_unreachable(packets)
    eligible = eligible_packets(initiative_id, db_path)
    blocked = blocked_packets(initiative_id, db_path)

    done = [p["packet_id"] for p in packets if p["state"] == bq.DONE]
    failed = [
        p["packet_id"]
        for p in packets
        if p["state"] in _BLOCKING_STATES
    ]
    in_progress = [
        p["packet_id"]
        for p in packets
        if p["state"] not in (bq.DONE, bq.QUEUED, *list(_BLOCKING_STATES))
    ]
    pending = [
        p["packet_id"]
        for p in packets
        if p["packet_id"] not in unreachable
        and p["state"] == bq.QUEUED
        and p["packet_id"] not in {e["packet_id"] for e in eligible}
    ]

    stored_state = str(initiative.get("state", INITIATIVE_ACTIVE))
    if stored_state == INITIATIVE_PAUSED:
        state = INITIATIVE_PAUSED
    elif len(done) == len(packets):
        state = INITIATIVE_COMPLETED
    elif blocked or failed:
        state = INITIATIVE_FAILED
    elif not eligible:
        state = INITIATIVE_PAUSED
    else:
        state = INITIATIVE_ACTIVE

    next_p = eligible[0] if eligible else None
    return {
        "initiative_id": initiative_id,
        "state": state,
        "pause_reason": initiative.get("pause_reason"),
        "total_packets": len(packets),
        "eligible": [p["packet_id"] for p in eligible],
        "blocked": [p["packet_id"] for p in blocked],
        "done": done,
        "failed": failed,
        "in_progress": in_progress,
        "pending": pending,
        "next_packet": next_p["packet_id"] if next_p else None,
        "next_packet_task_id": next_p["task_id"] if next_p else None,
    }


# ---------------------------------------------------------------------------
# KB-S5 — durable initiative state (pause/resume) and the run loop driver.
# ---------------------------------------------------------------------------


_VALID_STATES = frozenset(
    {INITIATIVE_ACTIVE, INITIATIVE_COMPLETED, INITIATIVE_FAILED, INITIATIVE_PAUSED}
)


def get_initiative_state(
    initiative_id: str, db_path: Path | None = None
) -> str:
    """Return the stored initiative ``state`` (the operator-set value).

    Distinct from ``initiative_status``'s *derived* state: this is the value an
    operator writes via pause/resume and that the run loop consults as a gate.
    """
    init_db(db_path)
    conn = bq.connect(db_path)
    try:
        row = conn.execute(
            "SELECT state FROM initiatives WHERE id = ?", (initiative_id,)
        ).fetchone()
        if row is None:
            raise InitiativeNotFoundError(initiative_id)
        return str(row["state"])
    finally:
        conn.close()


def set_initiative_state(
    initiative_id: str, state: str, db_path: Path | None = None
) -> None:
    """Persist an operator-set initiative ``state``. Validates the value."""
    if state not in _VALID_STATES:
        raise ValueError(
            f"invalid initiative state {state!r}; expected one of "
            f"{sorted(_VALID_STATES)}"
        )
    init_db(db_path)
    conn = bq.connect(db_path)
    try:
        row = conn.execute(
            "SELECT 1 FROM initiatives WHERE id = ?", (initiative_id,)
        ).fetchone()
        if row is None:
            raise InitiativeNotFoundError(initiative_id)
        conn.execute(
            "UPDATE initiatives SET state = ?, pause_reason = ?, "
            "updated_at = CURRENT_TIMESTAMP "
            "WHERE id = ?",
            (state, None if state != INITIATIVE_PAUSED else "operator state", initiative_id),
        )
        conn.commit()
    finally:
        conn.close()


def pause_initiative(
    initiative_id: str, reason: str | None = None, db_path: Path | None = None
) -> None:
    """Halt the run loop for an initiative. Idempotent and fail-loud.

    Sets the stored state to ``paused``; the next ``run_initiative`` call sees
    this and returns without driving any packet. The reason is durable.
    """
    if not reason or not reason.strip():
        reason = "operator pause"
    init_db(db_path)
    conn = bq.connect(db_path)
    try:
        row = conn.execute(
            "SELECT 1 FROM initiatives WHERE id = ?", (initiative_id,)
        ).fetchone()
        if row is None:
            raise InitiativeNotFoundError(initiative_id)
        conn.execute(
            "UPDATE initiatives SET state = ?, pause_reason = ?, "
            "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (INITIATIVE_PAUSED, reason, initiative_id),
        )
        conn.commit()
    finally:
        conn.close()


def resume_initiative(
    initiative_id: str, db_path: Path | None = None
) -> None:
    """Clear a pause so the run loop may proceed. Fail-loud if unknown."""
    get_initiative_state(initiative_id, db_path=db_path)  # raises if missing
    set_initiative_state(initiative_id, INITIATIVE_ACTIVE, db_path=db_path)
