from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import os
import re
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

DEFAULT_REVIEWER_MODEL = "Qwen3.5-9B-Q3_K_M"
DEFAULT_OLLAMA_URLS = ("http://127.0.0.1:11434", "http://127.0.0.1:11435")
METAL_RUNTIME_PROFILE = "metal_calibrated_v1"
CPU_SHADOW_RUNTIME_PROFILE = "cpu_shadow_v1"
DEFAULT_RUNTIME_PROFILE = METAL_RUNTIME_PROFILE
_RUNTIME_PROFILE_GPU_LAYERS = {
    METAL_RUNTIME_PROFILE: 999,
    CPU_SHADOW_RUNTIME_PROFILE: 0,
}
_RUNTIME_PROFILE_REQUEST_TIMEOUT_S = {
    METAL_RUNTIME_PROFILE: 45.0,
    CPU_SHADOW_RUNTIME_PROFILE: 120.0,
}
VALID_ANSWERS = {"YES", "NO", "UNSURE"}
MAX_PROMPT_TOKENS = 1900
DEFAULT_FOCUS_LOCK = Path(tempfile.gettempdir()) / "kitty-local-review-focus.lock"

RISK_PATTERNS: dict[str, re.Pattern[str]] = {
    "spend": re.compile(r"\b(payment|charge|billing|spend|budget|paid provider|provider call|reservation)\b", re.I),
    "auth_security": re.compile(r"\b(auth(?:entication|orization)?|credential|secret|api key|access token|security)\b", re.I),
    "destructive": re.compile(r"\b(delete|drop|destroy|erase|purge|force[- ]?push|rewrite history)\b", re.I),
    "irreversible_external_effect": re.compile(r"\b(send (?:email|message)|publish|merge|push to main|external side effect|irreversible)\b", re.I),
}


def detect_risk_tags(requirements: Sequence[str]) -> set[str]:
    text = "\n".join(requirements)
    return {tag for tag, pattern in RISK_PATTERNS.items() if pattern.search(text)}


def model_family(model: str | None) -> str | None:
    if not model:
        return None
    value = model.lower()
    families = (
        ("qwen", "qwen"),
        ("deepseek", "deepseek"),
        ("minimax", "minimax"),
        ("claude", "anthropic"),
        ("anthropic", "anthropic"),
        ("codex", "openai"),
        ("gpt", "openai"),
        ("openai", "openai"),
        ("gemini", "google"),
        ("llama", "meta"),
        ("nemotron", "nvidia"),
    )
    for needle, family in families:
        if needle in value:
            return family
    return None


def build_requirement_prompt(requirement: str, candidate: str) -> str:
    return (
        "Determine whether the supplied candidate satisfies the single stated requirement.\n"
        "Answer exactly one token: YES, NO, or UNSURE.\n"
        "YES means the supplied evidence guarantees the requirement.\n"
        "NO means the supplied evidence demonstrates the requirement is not satisfied.\n"
        "UNSURE means the supplied evidence is insufficient to decide.\n"
        "Assess only this requirement.\n\n"
        f"Requirement:\n{requirement.strip()}\n\n"
        f"Candidate:\n{candidate.strip()}"
    )


def parse_requirement_answer(text: str) -> str | None:
    answer = text.strip().upper()
    return answer if answer in VALID_ANSWERS else None


def _review_precheck(
    requirements: Sequence[str],
    explicit_risk_tags: Iterable[str],
    implementation_model: str | None,
    reviewer_model: str,
) -> tuple[list[str], str | None]:
    risk_tags = sorted(detect_risk_tags(requirements) | {str(tag) for tag in explicit_risk_tags})
    if risk_tags:
        return risk_tags, "high_risk_requires_strong_review"
    if not implementation_model:
        return risk_tags, "implementation_model_unknown"
    implementation_family = model_family(implementation_model)
    reviewer_family = model_family(reviewer_model)
    if implementation_family is None:
        return risk_tags, "implementation_model_family_unknown"
    if reviewer_family is None:
        return risk_tags, "reviewer_model_family_unknown"
    if implementation_family == reviewer_family:
        return risk_tags, "reviewer_not_model_family_independent"
    return risk_tags, None


def review_decision(
    *,
    requirements: Sequence[str],
    candidate: str,
    ask: Callable[[str, str], str],
    explicit_risk_tags: Iterable[str] = (),
    implementation_model: str | None = None,
    reviewer_model: str = DEFAULT_REVIEWER_MODEL,
    review_kind: str = "code",
) -> dict[str, Any]:
    if not requirements:
        raise ValueError("at least one review requirement is required")
    if not candidate.strip():
        raise ValueError("candidate evidence is required")

    risk_tags, precheck_reason = _review_precheck(
        requirements, explicit_risk_tags, implementation_model, reviewer_model
    )
    result: dict[str, Any] = {
        "contract_version": 1,
        "authoritative": False,
        "review_kind": review_kind,
        "reviewer_model": reviewer_model,
        "risk_tags": risk_tags,
        "requirements": [],
    }
    if precheck_reason:
        return result | {"decision": "escalate", "reason": precheck_reason}

    for requirement in requirements:
        raw = ask(requirement, candidate)
        answer = parse_requirement_answer(raw)
        result["requirements"].append({"requirement": requirement, "answer": answer})
        if answer != "YES":
            return result | {
                "decision": "escalate",
                "reason": "local_reviewer_not_clear",
            }

    return result | {
        "decision": "advisory_clear",
        "reason": "all_requirements_locally_clear_shadow_only",
    }


def _runtime_inference_flags(runtime_profile: str) -> list[str]:
    gpu_layers = _RUNTIME_PROFILE_GPU_LAYERS.get(runtime_profile)
    if gpu_layers is None:
        raise ValueError(f"unknown local review runtime profile: {runtime_profile}")
    return [
        "--no-mmproj",
        "-np", "1",
        "-c", "2048",
        "-b", "128",
        "-ub", "64",
        "-fa", "on",
        "-ctk", "q4_0",
        "-ctv", "q4_0",
        "--reasoning", "off",
        "--reasoning-budget", "0",
        "-ngl", str(gpu_layers),
    ]


def _runtime_request_timeout(runtime_profile: str) -> float:
    timeout = _RUNTIME_PROFILE_REQUEST_TIMEOUT_S.get(runtime_profile)
    if timeout is None:
        raise ValueError(f"unknown local review runtime profile: {runtime_profile}")
    return timeout


def build_llama_server_command(
    model_path: Path,
    *,
    port: int,
    runtime_profile: str = DEFAULT_RUNTIME_PROFILE,
) -> list[str]:
    if not model_path.exists():
        raise FileNotFoundError(model_path)
    executable = shutil.which("llama-server") or "llama-server"
    return [
        executable,
        "-m", str(model_path),
        "--host", "127.0.0.1",
        "--port", str(port),
        *_runtime_inference_flags(runtime_profile),
    ]


def _request_json(
    method: str,
    url: str,
    payload: object = None,
    *,
    timeout: float = 5.0,
) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
    except urllib.error.URLError as exc:
        raise RuntimeError(f"local review request failed: {method} {url}: {exc}") from exc
    if not body:
        return {}
    value = json.loads(body.decode("utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"local review request returned non-object JSON: {url}")
    return value


def _ollama_request_json(method: str, url: str, payload: object = None) -> dict[str, Any]:
    return _request_json(method, url, payload, timeout=45.0)


@dataclass(frozen=True)
class OllamaResidency:
    base_url: str
    model: str
    keep_alive: int | str


def _embedding_model(name: str) -> bool:
    lowered = name.lower()
    return "embed" in lowered or "minilm" in lowered


def _restore_keep_alive(expires_at: str | None) -> int | str:
    if not expires_at:
        return -1
    try:
        expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except ValueError:
        return -1
    now = datetime.now(timezone.utc)
    seconds = (expiry.astimezone(timezone.utc) - now).total_seconds()
    if seconds > 365 * 24 * 3600:
        return -1
    return f"{max(1, math.ceil(seconds))}s"


class ReviewExecutionLock:
    """Exclusive ownership of the local reviewer runtime, independent of focus mode."""

    def __init__(self, lock_path: Path = DEFAULT_FOCUS_LOCK) -> None:
        self.lock_path = lock_path
        self._handle: Any = None

    def __enter__(self) -> "ReviewExecutionLock":
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.lock_path.open("a+")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            handle.close()
            raise RuntimeError("local review runtime is already active") from exc
        self._handle = handle
        return self

    def __exit__(self, exc_type: object, exc: BaseException | None, tb: object) -> bool:
        if self._handle is not None:
            try:
                fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
            finally:
                self._handle.close()
                self._handle = None
        return False


class ReviewFocus:
    def __init__(
        self,
        ollama_urls: Sequence[str] = DEFAULT_OLLAMA_URLS,
        *,
        request_json: Callable[[str, str, object], dict[str, Any]] = _ollama_request_json,
        managed_models: Iterable[str] = (),
        lock_path: Path = DEFAULT_FOCUS_LOCK,
        acquire_lock: bool = True,
    ) -> None:
        self.ollama_urls = tuple(url.rstrip("/") for url in ollama_urls)
        self.request_json = request_json
        self.managed_models = frozenset(str(item) for item in managed_models)
        self.lock_path = lock_path
        self.acquire_lock = acquire_lock
        self.unloaded: list[OllamaResidency] = []
        self._pending_restore: list[OllamaResidency] = []
        self.unavailable: list[dict[str, str]] = []
        self._lock_handle: Any = None

    @property
    def unloaded_history(self) -> list[OllamaResidency]:
        return list(self.unloaded)

    @property
    def pending_restore(self) -> list[OllamaResidency]:
        return list(self._pending_restore)

    def _acquire_lock(self) -> None:
        if not self.acquire_lock:
            return
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.lock_path.open("a+")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            handle.close()
            raise RuntimeError("local review focus is already active") from exc
        self._lock_handle = handle

    def _release_lock(self) -> None:
        if self._lock_handle is None:
            return
        try:
            fcntl.flock(self._lock_handle.fileno(), fcntl.LOCK_UN)
        finally:
            self._lock_handle.close()
            self._lock_handle = None

    def _restore_unloaded(self) -> list[str]:
        errors: list[str] = []
        for residency in reversed(tuple(self._pending_restore)):
            try:
                self.request_json(
                    "POST",
                    f"{residency.base_url}/api/generate",
                    {"model": residency.model, "prompt": "", "keep_alive": residency.keep_alive},
                )
            except Exception as exc:
                errors.append(f"{residency.model}@{residency.base_url}: {exc}")
                continue
            self._pending_restore.remove(residency)
        return errors

    def __enter__(self) -> "ReviewFocus":
        self._acquire_lock()
        try:
            for base_url in self.ollama_urls:
                try:
                    state = self.request_json("GET", f"{base_url}/api/ps", None)
                except Exception as exc:
                    self.unavailable.append({"url": base_url, "error": str(exc)})
                    continue
                for model in state.get("models", []):
                    name = str(model.get("name") or model.get("model") or "")
                    if not name or name not in self.managed_models:
                        continue
                    residency = OllamaResidency(
                        base_url=base_url,
                        model=name,
                        keep_alive=_restore_keep_alive(model.get("expires_at")),
                    )
                    self._pending_restore.append(residency)
                    self.request_json(
                        "POST",
                        f"{base_url}/api/generate",
                        {"model": name, "prompt": "", "keep_alive": 0},
                    )
                    self.unloaded.append(residency)
            return self
        except Exception as exc:
            restore_errors = self._restore_unloaded()
            self._release_lock()
            if restore_errors:
                raise RuntimeError(
                    f"review focus entry failed: {exc}; restore also failed: {'; '.join(restore_errors)}"
                ) from exc
            raise

    def __exit__(self, exc_type: object, exc: BaseException | None, tb: object) -> bool:
        restore_errors = self._restore_unloaded()
        self._release_lock()
        if restore_errors:
            detail = "; ".join(restore_errors)
            if exc is not None:
                raise RuntimeError(f"review failed and model residency restore failed: {detail}") from exc
            raise RuntimeError(f"model residency restore failed: {detail}")
        return False

def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def find_default_model_path() -> Path:
    override = os.environ.get("KITTY_LOCAL_REVIEW_MODEL_PATH")
    if override:
        path = Path(override).expanduser()
        if path.exists():
            return path
        raise FileNotFoundError(path)
    persistent = (
        Path.home()
        / "Library/Application Support/Kitty/models/local-reviewer/Qwen3.5-9B-Q3_K_M.gguf"
    )
    if persistent.exists():
        return persistent
    cache_root = (
        Path.home()
        / ".cache/huggingface/hub/models--unsloth--Qwen3.5-9B-GGUF/snapshots"
    )
    matches = sorted(
        cache_root.glob("*/Qwen3.5-9B-Q3_K_M.gguf"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    if matches:
        return matches[0]
    raise FileNotFoundError(
        "Qwen3.5-9B Q3_K_M is not cached; set KITTY_LOCAL_REVIEW_MODEL_PATH"
    )


def _model_sha256(path: Path) -> str:
    resolved = path.expanduser().resolve()
    digest = hashlib.sha256()
    with resolved.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def reviewer_fingerprint(
    model_path: Path,
    model_id: str,
    *,
    runtime_profile: str = DEFAULT_RUNTIME_PROFILE,
    request_timeout: float | None = None,
) -> dict[str, str]:
    resolved = model_path.expanduser().resolve()
    inference_flags = _runtime_inference_flags(runtime_profile)
    effective_timeout = (
        _runtime_request_timeout(runtime_profile)
        if request_timeout is None
        else float(request_timeout)
    )
    return {
        "model_id": model_id,
        "model_family": model_family(model_id) or model_family(resolved.name) or "unknown",
        "model_path": str(resolved),
        "model_sha256": _model_sha256(resolved),
        "runtime": "llama.cpp",
        "runtime_profile": runtime_profile,
        "inference_flags": " ".join(inference_flags),
        "request_timeout_s": f"{effective_timeout:g}",
    }


class LocalLlamaServer:
    def __init__(
        self,
        model_path: Path,
        *,
        port: int | None = None,
        startup_timeout: float = 75.0,
        request_timeout: float | None = None,
        runtime_profile: str = DEFAULT_RUNTIME_PROFILE,
        deadline_monotonic: float | None = None,
    ) -> None:
        _runtime_inference_flags(runtime_profile)
        profile_timeout = _runtime_request_timeout(runtime_profile)
        self.model_path = model_path
        self.port = port or _free_port()
        self.startup_timeout = startup_timeout
        self.request_timeout = profile_timeout if request_timeout is None else float(request_timeout)
        self.runtime_profile = runtime_profile
        self.deadline_monotonic = deadline_monotonic
        self.process: subprocess.Popen[bytes] | None = None
        self.log_path: Path | None = None
        self.model_id = DEFAULT_REVIEWER_MODEL

    def _bounded_timeout(self, cap: float) -> float:
        if self.deadline_monotonic is None:
            return cap
        remaining = self.deadline_monotonic - time.monotonic()
        if remaining <= 0:
            raise RuntimeError("local review aggregate wall budget exhausted")
        return max(0.01, min(cap, remaining))

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def __enter__(self) -> "LocalLlamaServer":
        if shutil.which("llama-server") is None:
            raise FileNotFoundError("llama-server is not installed")
        log = tempfile.NamedTemporaryFile(prefix="kitty-local-review-", suffix=".log", delete=False)
        self.log_path = Path(log.name)
        self.process = subprocess.Popen(
            build_llama_server_command(
                self.model_path, port=self.port, runtime_profile=self.runtime_profile
            ),
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        log.close()
        deadline = time.monotonic() + self.startup_timeout
        if self.deadline_monotonic is not None:
            deadline = min(deadline, self.deadline_monotonic)
        last_error = "server did not answer"
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                break
            try:
                health = _request_json("GET", f"{self.base_url}/health", timeout=1.0)
                if health.get("status") in {"ok", "no slot available"}:
                    models = _request_json("GET", f"{self.base_url}/v1/models", timeout=2.0)
                    data = models.get("data") or []
                    if data and data[0].get("id"):
                        self.model_id = str(data[0]["id"])
                    return self
            except Exception as exc:
                last_error = str(exc)
            time.sleep(0.2)
        detail = self._log_tail()
        self._stop()
        raise RuntimeError(f"local reviewer failed to start: {last_error}; log={detail}")

    def ask(self, requirement: str, candidate: str) -> str:
        prompt = build_requirement_prompt(requirement, candidate)
        tokenized = _request_json(
            "POST",
            f"{self.base_url}/tokenize",
            {"content": prompt, "add_special": True},
            timeout=self._bounded_timeout(min(self.request_timeout, 10.0)),
        )
        tokens = tokenized.get("tokens")
        if not isinstance(tokens, list):
            raise RuntimeError(f"local reviewer tokenizer returned malformed response: {tokenized}")
        if len(tokens) > MAX_PROMPT_TOKENS:
            raise RuntimeError(
                f"local reviewer input too large: {len(tokens)} tokens exceeds {MAX_PROMPT_TOKENS}"
            )
        response = _request_json(
            "POST",
            f"{self.base_url}/v1/chat/completions",
            {
                "model": self.model_id,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
                "max_tokens": 4,
                "stream": False,
            },
            timeout=self._bounded_timeout(self.request_timeout),
        )
        try:
            choice = response["choices"][0]
            content = str(choice["message"]["content"])
            finish_reason = choice.get("finish_reason")
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"local reviewer returned malformed completion: {response}") from exc
        if finish_reason != "stop":
            raise RuntimeError(
                f"local reviewer returned incomplete completion: finish_reason={finish_reason!r}"
            )
        return content

    def fingerprint(self) -> dict[str, str]:
        return reviewer_fingerprint(
            self.model_path,
            self.model_id,
            runtime_profile=self.runtime_profile,
            request_timeout=self.request_timeout,
        )

    def _log_tail(self) -> str:
        if self.log_path is None or not self.log_path.exists():
            return "<no log>"
        lines = self.log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        return " | ".join(lines[-8:])

    def _stop(self) -> None:
        if self.process is None or self.process.poll() is not None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)

    def __exit__(self, exc_type: object, exc: BaseException | None, tb: object) -> bool:
        self._stop()
        return False


def run_local_review(
    request: dict[str, Any],
    *,
    model_path: Path | None = None,
    use_focus: bool = True,
    ollama_urls: Sequence[str] = DEFAULT_OLLAMA_URLS,
    managed_ollama_models: Iterable[str] = (),
    focus_lock_path: Path = DEFAULT_FOCUS_LOCK,
    runtime_profile: str = DEFAULT_RUNTIME_PROFILE,
    max_wall_seconds: float | None = None,
) -> dict[str, Any]:
    requirements = [str(item) for item in request.get("requirements") or []]
    candidate = str(request.get("candidate") or "")
    implementation_model = request.get("implementation_model")
    explicit_tags = [str(item) for item in request.get("risk_tags") or []]
    review_kind = str(request.get("review_kind") or "code")

    if not requirements:
        raise ValueError("at least one review requirement is required")
    if not candidate.strip():
        raise ValueError("candidate evidence is required")
    if max_wall_seconds is not None and max_wall_seconds <= 0:
        raise ValueError("max_wall_seconds must be positive")
    wall_deadline = (
        time.monotonic() + float(max_wall_seconds)
        if max_wall_seconds is not None
        else None
    )

    risk_tags = sorted(detect_risk_tags(requirements) | set(explicit_tags))
    base_result: dict[str, Any] = {
        "contract_version": 1,
        "authoritative": False,
        "review_kind": review_kind,
        "reviewer_model": None,
        "risk_tags": risk_tags,
        "requirements": [],
        "implementation_provenance": "untrusted_request_metadata",
    }
    if risk_tags:
        return base_result | {"decision": "escalate", "reason": "high_risk_requires_strong_review"}
    if not implementation_model:
        return base_result | {"decision": "escalate", "reason": "implementation_model_unknown"}
    if model_family(str(implementation_model)) is None:
        return base_result | {"decision": "escalate", "reason": "implementation_model_family_unknown"}

    try:
        selected_model_path = model_path or find_default_model_path()
    except OSError as exc:
        return base_result | {
            "decision": "escalate",
            "reason": "local_reviewer_runtime_error",
            "error": str(exc),
        }
    focus = (
        ReviewFocus(
            ollama_urls,
            managed_models=managed_ollama_models,
            lock_path=focus_lock_path,
            acquire_lock=False,
        )
        if use_focus
        else None
    )

    def execute() -> dict[str, Any]:
        with LocalLlamaServer(
            selected_model_path,
            runtime_profile=runtime_profile,
            deadline_monotonic=wall_deadline,
        ) as server:
            result = review_decision(
                requirements=requirements,
                candidate=candidate,
                ask=server.ask,
                explicit_risk_tags=explicit_tags,
                implementation_model=str(implementation_model),
                reviewer_model=server.model_id,
                review_kind=review_kind,
            )
            fingerprint = (
                server.fingerprint()
                if hasattr(server, "fingerprint")
                else reviewer_fingerprint(
                    selected_model_path, server.model_id, runtime_profile=runtime_profile
                )
            )
            result["reviewer_fingerprint"] = fingerprint
            result["implementation_provenance"] = "untrusted_request_metadata"
            return result

    try:
        with ReviewExecutionLock(focus_lock_path):
            if focus is None:
                return execute()
            with focus:
                result = execute()
            result["focus"] = {
                "unloaded": [item.model for item in focus.unloaded_history],
                "unavailable": focus.unavailable,
            }
            return result
    except (RuntimeError, OSError) as exc:
        return base_result | {
            "decision": "escalate",
            "reason": "local_reviewer_runtime_error",
            "error": str(exc),
        }

def _load_request(path: str) -> dict[str, Any]:
    if path == "-":
        value = json.load(__import__("sys").stdin)
    else:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("local review input must be one JSON object")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m gateway.local_review")
    parser.add_argument("--input", default="-", help="JSON request file, or - for stdin")
    parser.add_argument("--model-path")
    parser.add_argument(
        "--focus", action="store_true",
        help="temporarily unload only explicitly named managed Ollama models",
    )
    parser.add_argument(
        "--managed-ollama-model", action="append", default=[],
        help="restartable Kitty-owned Ollama model eligible for focus-mode unload",
    )
    args = parser.parse_args(argv)
    model_path = Path(args.model_path).expanduser() if args.model_path else None
    result = run_local_review(
        _load_request(args.input),
        model_path=model_path,
        use_focus=args.focus,
        managed_ollama_models=args.managed_ollama_model,
    )
    print(json.dumps(result, sort_keys=True))
    return 0 if result["decision"] == "approve" else 2


if __name__ == "__main__":
    raise SystemExit(main())
