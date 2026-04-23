"""
ImprovementTrigger — monitors live signals from the Supervisor and queues
kitty_coder jobs when thresholds are breached. Called once per run() call,
never blocks the hot path.

Trigger types and thresholds:
  ERROR_RATE      — >25% tool failures in last 20 calls
  USER_CORRECTION — 2+ correction signals in last 10 turns
  SPECIALIST_MISS — 3+ consecutive keyword-routing misses
  RESPONSE_LATENCY — 3+ consecutive responses >10s

Cooldown: 30 minutes per trigger type, persisted in data/vector_store/trigger_state.json
"""

import json
import time
from collections import deque
from pathlib import Path

TRIGGER_STATE_PATH = Path("./data/vector_store/trigger_state.json")
COOLDOWN_SECONDS = 1800  # 30 minutes

ERROR_RATE_WINDOW = 20
ERROR_RATE_THRESHOLD = 0.25
CORRECTION_WINDOW = 10
CORRECTION_THRESHOLD = 2
MISS_STREAK_THRESHOLD = 3
LATENCY_STREAK_THRESHOLD = 3
LATENCY_SECONDS = 10.0


class ImprovementTrigger:
    """
    Singleton. Maintains in-memory sliding windows (no DB queries in hot path).
    Queues kitty_coder jobs via TaskDelegator when thresholds are breached.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._state: dict[str, float] = self._load_state()
        self._tool_results: deque = deque(maxlen=ERROR_RATE_WINDOW)
        self._correction_turns: deque = deque(maxlen=CORRECTION_WINDOW)
        self._miss_streak: int = 0
        self._latency_streak: int = 0

    # ── State persistence ──────────────────────────────────────────────────────

    def _load_state(self) -> dict[str, float]:
        if TRIGGER_STATE_PATH.exists():
            try:
                return json.loads(TRIGGER_STATE_PATH.read_text())
            except Exception:
                pass
        return {}

    def _save_state(self):
        try:
            TRIGGER_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
            TRIGGER_STATE_PATH.write_text(json.dumps(self._state, indent=2))
        except Exception:
            pass

    # ── Signal ingestion ───────────────────────────────────────────────────────

    def record_tool_result(self, success: bool):
        self._tool_results.append(success)

    def record_correction(self, was_correction: bool):
        self._correction_turns.append(was_correction)

    def record_specialist_miss(self, was_miss: bool):
        if was_miss:
            self._miss_streak += 1
        else:
            self._miss_streak = 0

    def record_response_latency(self, elapsed_seconds: float):
        if elapsed_seconds > LATENCY_SECONDS:
            self._latency_streak += 1
        else:
            self._latency_streak = 0

    # ── Threshold evaluation ───────────────────────────────────────────────────

    def _in_cooldown(self, trigger_type: str) -> bool:
        last = self._state.get(trigger_type, 0.0)
        return (time.time() - last) < COOLDOWN_SECONDS

    def _set_cooldown(self, trigger_type: str):
        self._state[trigger_type] = time.time()
        self._save_state()

    def check_and_trigger(self, task_delegator) -> str | None:
        """
        Evaluate thresholds. If one fires and is not in cooldown, queue a
        kitty_coder background job and return the trigger type. Returns None
        if nothing fired or task_delegator is unavailable.
        """
        if task_delegator is None:
            return None

        fired = self._evaluate()
        if fired is None:
            return None

        trigger_type, prompt = fired
        if self._in_cooldown(trigger_type):
            return None

        try:
            task_delegator.delegate_heavy_task(prompt, task_type="kitty_coder")
            self._set_cooldown(trigger_type)
            return trigger_type
        except Exception:
            return None

    def _evaluate(self) -> tuple[str, str] | None:
        """Return (trigger_type, improvement_prompt) for the first breached threshold."""

        # ERROR_RATE: >25% failures in last 20 tool calls
        if len(self._tool_results) >= ERROR_RATE_WINDOW:
            failures = sum(1 for r in self._tool_results if not r)
            rate = failures / len(self._tool_results)
            if rate > ERROR_RATE_THRESHOLD:
                return (
                    "ERROR_RATE",
                    (
                        f"AUTONOMOUS IMPROVEMENT TASK (triggered: ERROR_RATE {rate:.0%} failure rate):\n"
                        "Investigate why tools are failing at a high rate. "
                        "Use code_ls to enumerate tool files under tools/, "
                        "code_read to inspect the top failing ones, identify root causes "
                        "(bad parameters, missing deps, broken APIs), and apply fixes with code_write. "
                        "Run shell_exec with a quick import or pytest check to verify. "
                        "Report what you fixed and why it was failing."
                    ),
                )

        # USER_CORRECTION: 2+ correction signals in last 10 turns
        if len(self._correction_turns) >= CORRECTION_WINDOW:
            corrections = sum(1 for c in self._correction_turns if c)
            if corrections >= CORRECTION_THRESHOLD:
                return (
                    "USER_CORRECTION",
                    (
                        f"AUTONOMOUS IMPROVEMENT TASK (triggered: USER_CORRECTION "
                        f"{corrections} signals in last {CORRECTION_WINDOW} turns):\n"
                        "The user has signaled incorrect responses multiple times recently. "
                        "Use code_read on scripts/supervisor.py to review the routing and "
                        "response-generation logic. Check _gatekeeper_mlx, _keyword_specialist, "
                        "and the Council path for logic errors. "
                        "Be conservative — only change what you can verify is wrong."
                    ),
                )

        # SPECIALIST_MISS: 3+ consecutive routing misses
        if self._miss_streak >= MISS_STREAK_THRESHOLD:
            return (
                "SPECIALIST_MISS",
                (
                    f"AUTONOMOUS IMPROVEMENT TASK (triggered: SPECIALIST_MISS "
                    f"streak={self._miss_streak}):\n"
                    "The keyword router has missed {self._miss_streak} consecutive queries. "
                    "Use code_ls on data/agents/ to list all specialists. "
                    "Use code_read to inspect their keywords arrays. "
                    "Review data/vector_store/session.json to see what queries were missed. "
                    "Add missing keywords using agent_patch on the relevant agent JSON files."
                ).format(self=self),
            )

        # RESPONSE_LATENCY: 3+ consecutive slow responses
        if self._latency_streak >= LATENCY_STREAK_THRESHOLD:
            return (
                "RESPONSE_LATENCY",
                (
                    f"AUTONOMOUS IMPROVEMENT TASK (triggered: RESPONSE_LATENCY "
                    f"streak={self._latency_streak} responses >10s):\n"
                    "Responses have been consistently slow. "
                    "Use shell_exec to check Ollama health: curl -s http://localhost:11434/api/tags. "
                    "Use code_read on scripts/supervisor.py to find blocking calls in _finish and run(). "
                    "Check _execute_tool for missing timeout guards. "
                    "Apply targeted fixes and report findings."
                ).format(self=self),
            )

        return None
