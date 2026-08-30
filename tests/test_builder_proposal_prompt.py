"""Wiring test for gateway/conversation_handoff.py's chat-side trigger.

Kitty only mentions the ```kitty-builder-proposal fence when the request
lands in the "code" domain (gateway/domain_router.py) — the instruction to
offer one (gateway/prompts.py's BUILDER_PROPOSAL_PROMPT) is appended to the
system prompt only for that domain (gateway/context_assembler.py's
_domain_prompt). These tests cover that gate, not model behavior: whether
the LLM actually emits a fence for a given message is not something a unit
test can assert. What is testable is that the *offer* never even reaches
the prompt for domains unrelated to build/fix requests, and that a handful
of representative conversational turns land where a human would expect.
"""

import pytest

from gateway.context_assembler import _AssemblerDeps, assemble_context
from gateway.domain_router import classify_domain
from gateway.memory_graph import Item, StoreAdapter

_MARKER = "kitty-builder-proposal"


class _EmptyAdapter(StoreAdapter):
    @property
    def name(self) -> str:
        return "empty"

    async def fetch(self, query: str) -> list[Item]:
        return []


def _deps() -> _AssemblerDeps:
    return _AssemblerDeps(adapters=[_EmptyAdapter()], enrichments=())


# ---------------------------------------------------------------------------
# The instruction is present for the code domain, absent everywhere else
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_code_domain_includes_builder_proposal_instruction():
    bundle = await assemble_context("debug this python function", deps=_deps(), domain="code")
    assert _MARKER in bundle.system


@pytest.mark.asyncio
async def test_soul_domain_excludes_builder_proposal_instruction():
    bundle = await assemble_context("hey what's up", deps=_deps(), domain="soul")
    assert _MARKER not in bundle.system


@pytest.mark.asyncio
async def test_health_domain_excludes_builder_proposal_instruction():
    bundle = await assemble_context("I have a headache and fever", deps=_deps(), domain="health")
    assert _MARKER not in bundle.system


@pytest.mark.asyncio
async def test_repair_domain_excludes_builder_proposal_instruction():
    bundle = await assemble_context("my amp is making a buzzing noise", deps=_deps(), domain="repair")
    assert _MARKER not in bundle.system


# ---------------------------------------------------------------------------
# Test conversations — messages a real chat would see, checked against the
# domain gate that decides whether the proposal instruction is even loaded.
# Conservative behavior means most of these must NOT be in the code domain.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "message",
    [
        "hey, how's it going",
        "I got my blood test results back",
        "my amp is making a buzzing noise, any idea why",
        "what do you think about this argument I'm having with my brother",
        "can you explain what a race condition is",
    ],
)
@pytest.mark.asyncio
async def test_casual_and_explanatory_messages_stay_out_of_code_domain(message):
    """Chatting about code, or code-adjacent topics, without asking for a
    build/fix should not even reach the code domain — so the proposal
    instruction never enters the prompt for these turns."""
    domain = classify_domain(message)
    bundle = await assemble_context(message, deps=_deps(), domain=domain)
    assert _MARKER not in bundle.system, f"{message!r} unexpectedly classified into a domain offering a proposal"


@pytest.mark.parametrize(
    "message",
    [
        "can you build me an endpoint that returns the weather",
        "let's implement a retry helper for the gateway client",
        "fix this code, it's throwing a KeyError",
    ],
)
@pytest.mark.asyncio
async def test_clear_build_requests_reach_code_domain(message):
    """Messages that clearly describe a build/fix land in the code domain,
    where the model at least has the option to offer a proposal — whether
    it actually does is a model-behavior question the prompt text answers,
    not this gate."""
    domain = classify_domain(message)
    assert domain == "code"
    bundle = await assemble_context(message, deps=_deps(), domain=domain)
    assert _MARKER in bundle.system
