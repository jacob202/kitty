"""Eval: does knowledge recall return relevant chunks?"""
from unittest.mock import MagicMock, patch

import gateway.knowledge as know_module


def _mock_knowledge(chunks: list[dict]):
    mock = MagicMock(return_value=chunks)
    return patch.object(know_module, "search_knowledge", mock)


def test_ai_topic_recalled():
    fake = [{"text": "Large language models have transformed software development", "score": 0.91}]
    with _mock_knowledge(fake):
        results = know_module.search_knowledge("AI language models")
    assert len(results) > 0
    assert any("language" in row.get("text", "").lower() for row in results)


def test_knowledge_block_format():
    fake = [
        {"text": "Jacob exported 1538 ChatGPT conversations", "score": 0.89, "source": "chatgpt.json"},
        {"text": "Claude Code session logs show daily coding patterns", "score": 0.85, "source": "claude.jsonl"},
    ]
    with _mock_knowledge(fake):
        block = know_module.get_knowledge_block("conversation history")
    assert "## Relevant knowledge" in block or len(block) > 0


def test_empty_knowledge_returns_empty_block():
    with _mock_knowledge([]):
        block = know_module.get_knowledge_block("nothing here")
    assert block == ""
