"""Content-lane execution policy for image generation (ADR 0040 decision #8).

Every executable image declaration carries a content lane and, for private
work, a consent basis. The lane is an authorization boundary, never a prompt
guess: keyword matching in ``image_gen`` is workflow conditioning only and has
zero routing authority.

Lane contract (v1):
- ``safe`` is the default. Work in this lane may run on hosted or private
  executors; ``consent_basis`` may be null.
- ``private_adult`` must be explicitly selected, never inferred from prompt
  text. It requires a non-null ``consent_basis`` in {synthetic, self}, an
  explicit ``adult_confirmed`` of true, and an execution target that is a
  Kitty-controlled private executor. Any hosted, absent, or unknown target is
  a fail-closed refusal — private work must never reach a hosted provider
  through routing, fallback, retry, or substitution.

Fail-closed: every mismatch raises a typed error; nothing silently coerces a
request into a weaker lane. ``validate_image_execution_policy`` is the single
canonical seam. The dispatch route, the runner (``image_runner.run`` /
``run_edit``), and plan persistence all call it (or its persistence contract)
so a direct runner invocation cannot bypass the guard.
"""

from __future__ import annotations

from enum import Enum
from typing import Any


class ContentLane(str, Enum):
    """Authorized content lane of an image declaration."""

    SAFE = "safe"
    PRIVATE_ADULT = "private_adult"


class ConsentBasis(str, Enum):
    """Why private-adult work is permitted at all.

    v1 admits no third-party likenesses: the subject is synthetic or the user
    themselves. Anything else is not a valid basis.
    """

    SYNTHETIC = "synthetic"
    SELF = "self"


class ExecutorKind(str, Enum):
    PRIVATE = "private"
    HOSTED = "hosted"
    UNKNOWN = "unknown"


#: Executors Kitty controls end-to-end. In v1 this is the worker edit lane;
#: txt2img on the worker is not yet wired, so private text-to-image is refused
#: until a private executor can perform it.
PRIVATE_EXECUTORS = frozenset({"kitty_worker"})

#: External hosted providers that private-adult work must never reach. Kept
#: additive and explicit so a new hosted integration is a deliberate review
#: point, not an implicit backdoor.
HOSTED_EXECUTORS = frozenset(
    {"flux", "flux2", "openrouter", "bfl", "runware", "google", "fal"}
)

_VALID_LANES = frozenset(lane.value for lane in ContentLane)
_VALID_CONSENT = frozenset(basis.value for basis in ConsentBasis)


class ImagePolicyError(RuntimeError):
    """Base for every fail-closed content-lane refusal."""


class ConsentRequiredError(ImagePolicyError):
    """private_adult work was declared without a valid consent basis."""


class AdultConfirmationRequiredError(ImagePolicyError):
    """private_adult work was declared without adult confirmation."""


class PrivateExecutionRequiredError(ImagePolicyError):
    """private_adult work was routed to a target that is not a private executor."""


def executor_kind(execution_target: str | None) -> ExecutorKind:
    """Classify an execution target for policy purposes.

    Only the explicit private executor set counts as private. Everything else —
    including local engines like comfyui/drawthings and unknown names — is not
    private and therefore fails closed for private_adult work.
    """
    normalized = (execution_target or "").strip().lower()
    if normalized in PRIVATE_EXECUTORS:
        return ExecutorKind.PRIVATE
    if normalized in HOSTED_EXECUTORS:
        return ExecutorKind.HOSTED
    return ExecutorKind.UNKNOWN


def normalize_lane(content_lane: Any) -> ContentLane | None:
    """Strict lane normalization, or None when the lane is unrecognized."""
    if isinstance(content_lane, ContentLane):
        return content_lane
    if content_lane is None or str(content_lane).strip() == "":
        return None
    text = str(content_lane).strip().lower()
    try:
        return ContentLane(text)
    except ValueError:
        return None


def _adult_confirmed_true(adult_confirmed: Any) -> bool:
    """Strict truthiness for the adult gate.

    Accpet only real booleans (or SQLite's integer 0/1). A bare truthy string
    is rejected rather than coerced: the caller must pass an explicit boolean.
    """
    if isinstance(adult_confirmed, bool):
        return adult_confirmed is True
    if isinstance(adult_confirmed, int) and adult_confirmed in (0, 1):
        return adult_confirmed == 1
    return False


def validate_image_execution_policy(
    content_lane: Any,
    consent_basis: Any,
    adult_confirmed: Any,
    execution_target: str | None,
) -> None:
    """The single canonical content-lane gate. Raises a typed error or returns.

    *content_lane* missing/unknown is itself an error for private work but a
    missing lane defaults to ``safe`` when explicitly absent (``None``/empty) —
    pre-IL-02 callers and plans are safe until something says otherwise. An
    unrecognized non-empty lane is a hard policy error.
    """
    lane = normalize_lane(content_lane)
    if lane is None:
        if content_lane is not None and str(content_lane).strip() != "":
            raise ImagePolicyError(
                f"invalid content lane {content_lane!r}; expected one of "
                f"{sorted(_VALID_LANES)}"
            )
        lane = ContentLane.SAFE

    if lane is ContentLane.SAFE:
        return

    if not _adult_confirmed_true(adult_confirmed):
        raise AdultConfirmationRequiredError(
            "content lane 'private_adult' requires adult_confirmed=true; "
            "adult confirmation cannot be inferred from prompt text"
        )

    if consent_basis is None or str(consent_basis).strip() == "":
        raise ConsentRequiredError(
            "content lane 'private_adult' requires a consent_basis in "
            f"{sorted(_VALID_CONSENT)}; consent cannot be inferred from prompt text"
        )
    if isinstance(consent_basis, ConsentBasis):
        basis = consent_basis.value
    else:
        basis = str(consent_basis).strip().lower()
    if basis not in _VALID_CONSENT:
        raise ConsentRequiredError(
            f"invalid consent_basis {consent_basis!r}; expected one of "
            f"{sorted(_VALID_CONSENT)}"
        )

    kind = executor_kind(execution_target)
    if kind is not ExecutorKind.PRIVATE:
        raise PrivateExecutionRequiredError(
            "content lane 'private_adult' requires a Kitty-controlled private "
            f"executor; target {execution_target!r} is {kind.value} — refusing "
            "rather than routing private work to a hosted provider"
        )
