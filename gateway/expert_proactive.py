"""Proactive expert evaluation and learning loop.

Evaluates unread captures and configured directories to emit expert headlines.
"""
from __future__ import annotations

import asyncio
import csv
import json
import logging
import os
import shutil
import time
import uuid
from pathlib import Path

import filelock

from gateway import desktop_store, knowledge, llm_client, paths, signal_store, expert_state
from gateway.researcher import DeepResearcher

logger = logging.getLogger("kitty.expert_proactive")


def poll_experts() -> None:
    """Synchronous entry point for cron."""
    asyncio.run(async_poll_experts())


def _load_cursors() -> dict:
    if paths.EXPERT_CURSORS_FILE.exists():
        try:
            with open(paths.EXPERT_CURSORS_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}


def _save_cursor(expert_id: str, file_key: str, size: int, mtime: float) -> None:
    lock = filelock.FileLock(str(paths.EXPERT_CURSORS_FILE) + ".lock", timeout=10)
    with lock:
        cursors = _load_cursors()
        if expert_id not in cursors:
            cursors[expert_id] = {}
        cursors[expert_id][file_key] = {"size": size, "mtime": mtime}
        paths.EXPERT_CURSORS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(paths.EXPERT_CURSORS_FILE, "w") as f:
            json.dump(cursors, f)


async def async_poll_experts() -> None:
    """Evaluate new signals and files for each proactive expert."""
    cycle_id = str(uuid.uuid4())[:8]
    if expert_state.is_global_pause():
        logger.info("[cycle=%s] Proactive experts are globally paused.", cycle_id)
        return

    expert_state.recover_stuck_inbox_entries(10)

    experts = knowledge.EXPERT_PROFILES

    # Get recent untriaged inbox entries
    inbox_entries = desktop_store.read_inbox(limit=25)

    for expert_id, config in experts.items():

        policy = config.get("proactive_policy")
        if not policy:
            continue

        snooze_until = expert_state.get_snooze_until(expert_id)
        if time.time() < snooze_until:
            logger.info("[cycle=%s] Expert %s is snoozed until %s", cycle_id, expert_id, snooze_until)
            continue

        poll_interval = policy.get("poll_interval_hours", 0) * 3600
        cursors = _load_cursors()
        last_run_data = cursors.get(expert_id, {}).get("_last_run", 0)
        last_run = last_run_data.get("mtime", 0) if isinstance(last_run_data, dict) else last_run_data
        if time.time() - last_run < poll_interval:
            continue

        lock_file = paths.KITTY_DATA_DIR / f"expert_{expert_id}.lock"

        paths.KITTY_DATA_DIR.mkdir(parents=True, exist_ok=True)
        lock = filelock.FileLock(str(lock_file), timeout=5)
        try:
            with lock:
                await _poll_single_expert(expert_id, config, inbox_entries, cycle_id)

        except filelock.Timeout:
            logger.warning("[cycle=%s] Expert %s lock contention: already polling.", cycle_id, expert_id)
            continue


async def _poll_single_expert(expert_id: str, config: dict, inbox_entries: list[dict], cycle_id: str) -> None:
    policy = config.get("proactive_policy", {})
    prompt_path = Path(config["prompt_path"])
    expert_prompt = prompt_path.read_text() if prompt_path.exists() else ""
    learning_enabled = policy.get("learning_enabled", False)

    # 1. Process Inbox Entries
    if policy.get("watch_inbox"):
        for entry in inbox_entries:
            inbox_id = entry.get("id")
            if not inbox_id:
                continue

            if not expert_state.claim_inbox_entry(expert_id, inbox_id):
                continue

            dedupe_key = f"expert_evaluation:{expert_id}:inbox:{inbox_id}"
            try:
                await _evaluate_and_emit(
                    expert_id=expert_id,
                    expert_prompt=expert_prompt,
                    data_source=f"Inbox Capture: {entry.get('text', '')}",
                    learning_enabled=learning_enabled,
                    dedupe_key=dedupe_key,
                    config=config,
                    cycle_id=cycle_id
                )
                expert_state.set_inbox_entry_status(expert_id, inbox_id, "triaged")
                desktop_store.mark_inbox_processed(inbox_id)
            except Exception as e:
                logger.error(f"[cycle={cycle_id}] Error evaluating inbox entry {inbox_id}: {e}")
                expert_state.set_inbox_entry_status(expert_id, inbox_id, "new")

    # 2. Process Watch Directories
    cursors = _load_cursors().get(expert_id, {})
    for watch_dir in policy.get("watch_directories", []):
        dir_path = Path(os.path.expanduser(watch_dir))
        if not dir_path.exists() or not dir_path.is_dir():
            continue

        for file_path in dir_path.iterdir():
            if not file_path.is_file() or file_path.suffix.lower() != ".csv":
                continue

            try:
                st = file_path.stat()
                current_size = st.st_size
                current_mtime = st.st_mtime

                # Stable file check: must not have been modified in the last 10 seconds
                if time.time() - current_mtime < 10:
                    continue

                cursor = cursors.get(file_path.name)
                # Only process if size has grown
                if cursor and current_size <= cursor.get("size", 0):
                    continue

                content = _read_csv_tail(file_path, tail_lines=20)
                if content.strip():
                    dedupe_key = f"expert_evaluation:{expert_id}:file:{file_path.name}:{current_size}"
                    await _evaluate_and_emit(
                        expert_id=expert_id,
                        expert_prompt=expert_prompt,
                        data_source=f"CSV Data ({file_path.name}):\n{content}",
                        learning_enabled=learning_enabled,
                        dedupe_key=dedupe_key,
                        config=config,
                        cycle_id=cycle_id
                    )

                # Update cursor regardless of LLM output (NO or emitted)
                _save_cursor(expert_id, file_path.name, current_size, current_mtime)

            except Exception as e:
                logger.warning(f"[cycle={cycle_id}] Failed to read file {file_path}: {e}")
                # Move to dead letter queue
                dead_letter = paths.DEAD_LETTER_DIR / file_path.name
                paths.DEAD_LETTER_DIR.mkdir(parents=True, exist_ok=True)
                shutil.move(str(file_path), str(dead_letter))
                signal_store.emit(
                    source=f"expert.{expert_id}",
                    kind="expert.error",
                    payload={"error": str(e), "file": file_path.name}
                )

    _save_cursor(expert_id, "_last_run", 0, time.time())


def _already_evaluated(dedupe_key: str) -> bool:
    return False


def _mark_evaluating(expert_id: str, dedupe_key: str) -> bool:
    res = signal_store.emit(
        source=f"expert.{expert_id}",
        kind="expert.evaluation",
        dedupe_key=dedupe_key,
        payload={"status": "evaluating"}
    )
    return res is not None


def _read_csv_tail(path: Path, tail_lines: int = 20) -> str:
    for enc in ["utf-8", "latin-1", "utf-16"]:
        try:
            lines = path.read_text(encoding=enc).strip().splitlines()
            break
        except UnicodeDecodeError:
            continue
    else:
        # If all fail, raise to trigger dead-letter
        raise UnicodeError("Failed to decode CSV with common encodings.")

    if not lines:
        return ""
    if len(lines) <= tail_lines + 1:
        return "\n".join(lines)
    header = lines[0]
    tail = lines[-tail_lines:]
    return header + "\n" + "\n".join(tail)


def _is_duplicate_signal(expert_id: str, new_headline: str, new_analysis: str) -> bool:
    """Hybrid dedup: fast jaccard pre-filter, fallback to LLM."""
    recent_signals = signal_store.list_recent(limit=10, source=f"expert.{expert_id}")
    recent_texts = []
    for s in recent_signals:
        if s["kind"] == "expert.suggestion" and "payload" in s:
            text = s["payload"].get("headline", "") + " " + s["payload"].get("analysis", "")
            recent_texts.append(text)

    if not recent_texts:
        return False

    def get_words(text: str) -> set[str]:
        return set(text.lower().split())

    new_words = get_words(new_headline + " " + new_analysis)
    if not new_words:
        return False

    for old_text in recent_texts:
        old_words = get_words(old_text)
        if not old_words:
            continue

        intersection = new_words.intersection(old_words)
        union = new_words.union(old_words)
        jaccard = len(intersection) / len(union) if union else 0

        if jaccard > 0.8:
            return True  # Fast path: virtually identical

        if jaccard > 0.4:
            # Slow path: LLM Fallback
            prompt = f"""You are checking for duplicate insights.
Recent insight: {old_text}
New insight: {new_headline}
{new_analysis}

Are these two insights describing the exact same underlying issue/event, just phrased differently?
Reply only YES or NO."""
            try:
                res = llm_client.call_llm([{"role": "user", "content": prompt}], privacy_tier="cloud_ok", content_class=None).strip()
                if res == "YES":
                    return True
            except Exception:
                pass

    return False


async def _evaluate_and_emit(
    expert_id: str,
    expert_prompt: str,
    data_source: str,
    learning_enabled: bool,
    dedupe_key: str,
    config: dict | None = None,
    cycle_id: str = ""
) -> None:
    if config is None:
        config = {}

    topic_hash = expert_state.compute_topic_hash(data_source)
    cooldown_hours = config.get("proactive_policy", {}).get("cooldown_hours", 12.0)

    if expert_state.check_cooldown(expert_id, topic_hash, cooldown_hours):
        logger.info(f"[cycle={cycle_id}] Expert {expert_id} skipping evaluation due to cooldown for topic: {topic_hash}")
        return

    suppress_threshold = config.get("proactive_policy", {}).get("suppress_after_dismissals", 3)
    dismissed_count = expert_state.get_dismissed_count(expert_id, topic_hash)
    if dismissed_count >= suppress_threshold:
        logger.info(f"[cycle={cycle_id}] Expert {expert_id} skipping topic due to dismissal threshold: {topic_hash}")
        return

    if not _mark_evaluating(expert_id, dedupe_key):
        return

    logger.info("[cycle=%s] Expert %s evaluating new data: %s", cycle_id, expert_id, dedupe_key)

    router_prompt = f"""You are the {expert_id} expert.
Profile Context: {expert_prompt}

New Data:
{data_source}

Does this data require a proactive insight from you? (e.g. diagnosing a problem, optimizing a metric, providing a warning)
If NO, reply strictly 'NO'.
If YES, you may either:
1. Reply 'SEARCH: <query>' to request more information from the web to learn about the issue before responding.
2. Reply with the final insight formatted exactly as:
[Headline] <Short punchy headline>
[T0 Action] <Suggested immediate action>
(or [T1 Action])
<Detailed Analysis>

If this insight is semantically identical to any recent signal, reply with 'ABORT'.
"""

    try:
        response = llm_client.call_llm([{"role": "user", "content": router_prompt}], privacy_tier="cloud_ok", content_class=None).strip()
    except Exception as e:
        logger.error(f"[cycle={cycle_id}] Expert {expert_id} failed to evaluate: {e}")
        return

    if response in ("NO", "ABORT"):
        return

    research_note = ""
    if response.startswith("SEARCH:") and learning_enabled:
        query = response.split("SEARCH:", 1)[1].strip()
        logger.info("[cycle=%s] Expert %s researching: %s", cycle_id, expert_id, query)
        researcher = DeepResearcher()

        # Exponential backoff search retry
        for attempt in range(2):
            try:
                research_context = await asyncio.wait_for(
                    researcher.technical_deep_dive(query, ingest=False),
                    timeout=45.0
                )
                break
            except asyncio.TimeoutError:
                if attempt == 0:
                    logger.warning(f"[cycle={cycle_id}] Search timed out for query: {query}. Retrying...")
                    await asyncio.sleep(2)
                    continue
                logger.warning(f"[cycle={cycle_id}] Search timed out again for query: {query}")
                research_context = ""
                research_note = "(Search timed out)"
            except Exception as e:
                if attempt == 0:
                    logger.warning(f"[cycle={cycle_id}] Search failed for query: {query}: {e}. Retrying...")
                    await asyncio.sleep(2)
                    continue
                logger.warning(f"[cycle={cycle_id}] Search failed again for query: {query}: {e}")
                research_context = ""
                research_note = "(Search failed)"


        feedback_note = ""
        if dismissed_count > 0:
            feedback_note = f"\\n\\nIMPORTANT: The user previously dismissed similar insights {dismissed_count} times. Only generate a signal if the situation has notably worsened."

        synthesis_prompt = f"""You are the {expert_id} expert.
Profile Context: {expert_prompt}

New Data:
{data_source}

Research Context gathered:
{research_context}
{research_note}{feedback_note}

Provide your final insight formatted exactly as:
[Headline] <Short punchy headline>
[T0 Action] <Suggested immediate action>
(or [T1 Action])
<Detailed Analysis>

If this insight is semantically identical to any recent signal, reply with 'ABORT'.
"""
        try:
            response = llm_client.call_llm([{"role": "user", "content": synthesis_prompt}], privacy_tier="cloud_ok", content_class=None).strip()
        except Exception as e:
            logger.error(f"[cycle={cycle_id}] Expert {expert_id} failed synthesis: {e}")
            return

    if response == "ABORT":
        return

    if "[Headline]" in response:
        lines = response.splitlines()
        headline = ""
        action = ""
        analysis_lines = []
        for line in lines:
            if line.startswith("[Headline]"):
                headline = line.replace("[Headline]", "").strip()
            elif line.startswith("[T0 Action]"):
                action = line.replace("[T0 Action]", "").strip()
            elif line.startswith("[T1 Action]"):
                action = line.replace("[T1 Action]", "").strip()
            else:
                analysis_lines.append(line)

        analysis = "\n".join(analysis_lines).strip()
        if research_note:
            analysis += f"\n\n*Note: {research_note}*"

        # Final hybrid semantic dedup check
        if _is_duplicate_signal(expert_id, headline, analysis):
            logger.info(f"[cycle={cycle_id}] Expert {expert_id} skipping semantically duplicate signal.")
            return

    expert_state.set_cooldown(expert_id, topic_hash)

    logger.info(f"[cycle={cycle_id}] Expert {expert_id} emitting new signal for topic {topic_hash}")

    signal_store.emit(
        source=f"expert.{expert_id}",
        kind="expert.suggestion",
        payload={
            "headline": headline,
            "action": action,
            "analysis": analysis,
            "topic_hash": topic_hash
        }
    )
