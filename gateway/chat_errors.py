"""User-facing chat turn failures.

The streaming chat path talks to a model provider through LiteLLM. When that
provider rejects or drops a request, the failure must reach the phone screen as
plain language and one recovery action — never as raw stream internals (e.g.
"Stream closed without [DONE]") or an unreadable stack trace.

``ChatTurnError`` is the typed carrier. The gateway emits it as one SSE error
event before the stream tears down; the client maps it (plus its own network /
timeout failures) into the same user-language copy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ChatErrorKind(str, Enum):
    """Machine-readable causes used by the frontend to choose recovery copy."""

    # Selected provider/model could not serve the request (auth, credit, bad
    # model id, provider down). Recovery: retry, or change model/provider.
    ROUTING = "routing"
    # The model provider or gateway failed while producing the reply.
    UPSTREAM = "upstream"
    # The client could not reach the gateway at all.
    NETWORK = "network"
    # The stream ended without a completion boundary.
    CUT_OFF = "cut-off"


# User-facing copy, keyed by kind. Written for a phone screen: what happened,
# that the message is saved, and the one next action. No Dynamo to parse.
FRIENDLY_MESSAGES: dict[ChatErrorKind, str] = {
    ChatErrorKind.ROUTING: (
        "Kitty couldn't complete this request — the selected model provider "
        "didn't accept it (it may be out of credit or unavailable). "
        "Your message is saved. Tap retry, or check Settings to pick a different model."
    ),
    ChatErrorKind.UPSTREAM: (
        "Kitty's model provider couldn't finish this request. "
        "Your message is saved — tap retry to try again."
    ),
    ChatErrorKind.NETWORK: (
        "Kitty couldn't reach its gateway. Check that Kitty is running, then tap "
        "retry — your message is saved."
    ),
    ChatErrorKind.CUT_OFF: (
        "Kitty's reply was cut off before it finished. Tap retry to continue."
    ),
}


@dataclass
class ChatTurnError(Exception):
    """Typed failure that carries user-facing copy plus machine detail."""

    kind: ChatErrorKind = ChatErrorKind.UPSTREAM
    user_message: str | None = None
    detail: str = ""
    _carry: list[str] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        super().__init__(self.user_message or FRIENDLY_MESSAGES[self.kind])

    @property
    def message(self) -> str:
        """User-facing copy: explicit override, else the kind default."""
        return self.user_message or FRIENDLY_MESSAGES[self.kind]

    @classmethod
    def from_exception(
        cls,
        exc: BaseException,
        *,
        kind: ChatErrorKind,
        detail: str = "",
    ) -> "ChatTurnError":
        """Wrap a raw failure without leaking internals to the user."""
        return cls(kind=kind, detail=detail or str(exc) or type(exc).__name__)


def sse_error_event(kind: ChatErrorKind | str, message: str) -> bytes:
    """The terminal SSE sequence for a failed turn, readable by both clients.

    Frame order is load-bearing:

    1. Kitty's own ``{"error": {...}}`` frame. ``chat-client.ts`` throws the
       moment it parses this and never reads further, so it must come first and
       it sees exactly what it saw before.
    2. An OpenAI-shaped chunk carrying the same copy as ``delta.content``.
       Open WebUI (and any other OpenAI-compatible client) cannot read frame 1,
       so without this the user got a silent empty reply on every failure. The
       standard ``finish_reason`` remains schema-valid; Kitty's richer error kind
       lives in the extension field.
    3. ``[DONE]``. The stream used to be torn down by the re-raise with no
       completion boundary, which those clients report as a cut connection
       rather than the real cause.
    """
    import json

    kind_value = kind.value if isinstance(kind, ChatErrorKind) else kind
    error_frame = json.dumps(
        {"error": {"kind": kind_value, "message": message}},
        ensure_ascii=False,
    )
    content_frame = json.dumps(
        {
            "object": "chat.completion.chunk",
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": message},
                    "finish_reason": "stop",
                }
            ],
            "kitty_error_kind": kind_value,
        },
        ensure_ascii=False,
    )
    return (
        f"data: {error_frame}\n\n"
        f"data: {content_frame}\n\n"
        "data: [DONE]\n\n"
    ).encode("utf-8")