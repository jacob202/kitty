"""Project one Builder initiative into a product Work item."""

from gateway._work_projection_details import _project_blocker, _project_packet, _project_run
from gateway._work_projection_select import _has_live_run, _latest_attempt, _select_current_packet
from gateway._work_projection_support import _bounded_reason, _latest_updated_at


def _project_work_item(initiative):
    packets = initiative.get("packets") or []
    current_packet = _select_current_packet(initiative, packets)
    blocker = _project_blocker(initiative, current_packet, packets)
    state = _project_state(initiative, current_packet, packets, blocker)
    current_run = _project_run(current_packet)
    current_attempt = _latest_attempt(current_packet)
    publication = (current_packet or {}).get("publication")
    preflight = _project_preflight(initiative, current_packet)
    return {
        "id": initiative["initiative_id"],
        "title": initiative.get("title"),
        "state": state,
        "source": {
            "kind": "builder",
            "initiative_id": initiative["initiative_id"],
            "packet_id": (current_packet or {}).get("packet_id"),
        },
        "current_packet": _project_packet(current_packet),
        "current_run": current_run,
        "blocker": blocker,
        "next_action": _bounded_reason((current_packet or {}).get("projection", {}).get("next_action")),
        "preflight": preflight,
        "evidence": {
            "validation": (current_attempt or {}).get("validation"),
            "review": (current_attempt or {}).get("review"),
            "publication": publication,
            "approval": {
                "state": "unavailable",
                "reason": "No durable Gateway approval binding exists for Builder initiatives yet.",
            },
        },
        "data_quality": dict((current_packet or {}).get("data_quality") or {"state": "complete", "issues": []}),
        "updated_at": _latest_updated_at(initiative, packets),
    }


def _project_preflight(initiative, current_packet):
    """Compute a lightweight preflight result for the current packet.

    Read-only and side-effect-free: creates no attempt, changes no state.
    All cost figures are local estimates, not provider invoices.
    """
    if current_packet is None:
        return None

    from gateway import builder_queue as bq
    from gateway import compute_governor as cg

    initiative_state = initiative.get("state")
    task_state = current_packet.get("task_state")
    base_sha = current_packet.get("base_sha")
    blockers: list[str] = []
    warnings: list[str] = []

    if initiative_state != "active":
        blockers.append(f"initiative state is {initiative_state!r}, not 'active'")
    if initiative.get("superseded_by"):
        blockers.append(f"initiative is superseded by {initiative['superseded_by']}")
    if task_state is None:
        blockers.append("packet has no task record")
    elif task_state != bq.QUEUED:
        blockers.append(f"packet task state is {task_state!r}, not 'queued'")

    depends_on = current_packet.get("depends_on") or []
    packet_states = {
        p.get("packet_id"): p.get("task_state")
        for p in initiative.get("packets", [])
        if p.get("packet_id")
    }
    for dep in depends_on:
        dep_state = packet_states.get(dep)
        if dep_state is None:
            blockers.append(f"dependency {dep!r} not found")
        elif dep_state not in {bq.DONE, None}:
            blockers.append(f"dependency {dep!r} is in state {dep_state!r}, not 'done'")

    if not base_sha:
        warnings.append("packet has no base_sha recorded; manifest may be stale")

    governor_route = None
    estimated_cost_cad = 0.0
    try:
        config = cg.load_reserve_config(cg.ROOT_CONFIG_PATH)
        ledger_path = cg.default_db_path()
        cg.init_db(ledger_path)
        reserve = cg.reserve_from_ledger(ledger_path, config)
        dispatch = cg.Dispatch(
            task_type="implement",
            work_kind="implementation",
            subject_ref=f"{initiative.get('initiative_id', '')}/{current_packet.get('packet_id', '')}",
            head_sha=base_sha or "0" * 40,
            artifact=", ".join(current_packet.get("allowed_paths") or []),
            acceptance_tests=tuple(current_packet.get("acceptance_criteria") or []),
            allowed_scope=tuple(current_packet.get("allowed_paths") or []),
            exclusions=(),
            risk_class="routine",
            stopping_condition="acceptance tests pass",
            requested_route="free",
        )
        decision = cg.decide(ledger_path, dispatch, reserve=reserve)
        governor_route = decision.route
        estimated_cost_cad = cg.estimate_pass_cost_cad(decision.route) if decision.route else 0.0
        if decision.action in {cg.ACTION_DEFER, cg.ACTION_REJECT}:
            blockers.extend(decision.reasons)
    except Exception as exc:
        warnings.append(f"governor evaluation failed: {exc}")

    return {
        "can_proceed": len(blockers) == 0,
        "blockers": blockers,
        "warnings": warnings,
        "route": governor_route,
        "estimated_cost_cad": estimated_cost_cad,
        "basis": "local estimate — NOT a provider meter",
    }


def _project_state(initiative, current_packet, packets, blocker):
    if any(_has_live_run(packet) for packet in packets):
        return "active"
    if initiative.get("state") == "paused" and initiative.get("pause_reason"):
        return "paused"
    if blocker is not None and blocker.get("state") == "blocked":
        return "blocked"
    if initiative.get("state") == "completed":
        return "completed"
    if _has_failure(initiative, current_packet, packets):
        return "failed"
    if any((packet.get("eligibility") or {}).get("state") == "eligible" for packet in packets):
        return "ready"
    return "waiting"


def _has_failure(initiative, current_packet, packets):
    if initiative.get("state") == "failed":
        return True
    if current_packet is not None and _packet_failed(current_packet):
        return True
    return any(_packet_failed(packet) for packet in packets)


def _packet_failed(packet):
    if packet.get("task_state") == "failed":
        return True
    failure_kind = packet.get("failure_kind")
    return failure_kind not in {None, "blocked", "cancelled"}
