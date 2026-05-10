import pytest
import asyncio
from unittest.mock import patch, AsyncMock
from gateway.context_builder import build_user_context, build_worker_context

@pytest.fixture
def mock_load_prompt():
    with patch("gateway.context_builder.load_prompt", return_value="SOUL_PROMPT") as m:
        yield m

@pytest.fixture
def mock_fetch_memory():
    with patch("gateway.context_builder._fetch_memory", new_callable=AsyncMock) as m:
        yield m

@pytest.fixture
def mock_fetch_knowledge():
    with patch("gateway.context_builder._fetch_knowledge", new_callable=AsyncMock) as m:
        yield m

@pytest.mark.asyncio
async def test_build_user_context_parallel_fetch(mock_load_prompt, mock_fetch_memory, mock_fetch_knowledge):
    mock_fetch_memory.return_value = [{"memory": "M1", "score": 0.9}]
    mock_fetch_knowledge.return_value = [{"text": "K1", "score": 0.9}]
    
    prefix, suffix = await build_user_context("query", "soul")
    
    mock_fetch_memory.assert_called_once()
    mock_fetch_knowledge.assert_called_once()
    assert "M1" in suffix
    assert "K1" in suffix

@pytest.mark.asyncio
async def test_relevance_threshold_filters_low_scores(mock_load_prompt, mock_fetch_memory, mock_fetch_knowledge):
    mock_fetch_memory.return_value = [{"memory": "M1", "score": 0.9}, {"memory": "M2", "score": 0.5}]
    mock_fetch_knowledge.return_value = [{"text": "K1", "score": 0.5}]
    
    prefix, suffix = await build_user_context("query", "soul")
    assert "M1" in suffix
    assert "M2" not in suffix
    assert "K1" not in suffix

@pytest.mark.asyncio
async def test_token_budget_truncates_memory(mock_load_prompt, mock_fetch_memory, mock_fetch_knowledge):
    long_mem = "word " * 500  # Will exceed MEMORY_BUDGET_TOKENS
    mock_fetch_memory.return_value = [{"memory": long_mem, "score": 0.9}, {"memory": "M2", "score": 0.9}]
    mock_fetch_knowledge.return_value = []
    
    prefix, suffix = await build_user_context("query", "soul")
    assert long_mem not in suffix
    assert "M2" in suffix

@pytest.mark.asyncio
async def test_token_budget_truncates_knowledge(mock_load_prompt, mock_fetch_memory, mock_fetch_knowledge):
    long_know = "word " * 600  # Exceeds KNOWLEDGE_BUDGET_TOKENS
    mock_fetch_memory.return_value = []
    mock_fetch_knowledge.return_value = [{"text": long_know, "score": 0.9}, {"text": "K2", "score": 0.9}]
    
    prefix, suffix = await build_user_context("query", "soul")
    assert long_know not in suffix
    assert "K2" in suffix

@pytest.mark.asyncio
async def test_filter_before_truncate(mock_load_prompt, mock_fetch_memory, mock_fetch_knowledge):
    # High score old chunk, low score new chunk
    long_old_mem = "word " * 300
    mock_fetch_memory.return_value = [
        {"memory": long_old_mem, "score": 0.9, "created_at": "1"}, 
        {"memory": "new low", "score": 0.5, "created_at": "2"}
    ]
    mock_fetch_knowledge.return_value = []
    
    prefix, suffix = await build_user_context("query", "soul")
    assert long_old_mem in suffix
    assert "new low" not in suffix

@pytest.mark.asyncio
async def test_empty_sections_omitted(mock_load_prompt, mock_fetch_memory, mock_fetch_knowledge):
    mock_fetch_memory.return_value = []
    mock_fetch_knowledge.return_value = []
    
    prefix, suffix = await build_user_context("query", "soul")
    assert "### About Jacob" not in suffix
    assert "### Relevant context" not in suffix
    assert suffix == ""

@pytest.mark.asyncio
async def test_one_fetch_fails_other_succeeds(mock_load_prompt, mock_fetch_memory, mock_fetch_knowledge):
    mock_fetch_memory.side_effect = Exception("Memory down")
    mock_fetch_knowledge.return_value = [{"text": "K1", "score": 0.9}]
    
    prefix, suffix = await build_user_context("query", "soul")
    assert "K1" in suffix
    assert "Memory down" not in suffix
    assert "### About Jacob" not in suffix

@pytest.mark.asyncio
async def test_both_fetches_fail_returns_soul_only(mock_load_prompt, mock_fetch_memory, mock_fetch_knowledge):
    mock_fetch_memory.side_effect = Exception("Memory down")
    mock_fetch_knowledge.side_effect = Exception("Knowledge down")
    
    prefix, suffix = await build_user_context("query", "soul")
    assert suffix == ""
    assert prefix == "SOUL_PROMPT"

@pytest.mark.asyncio
async def test_build_user_context_returns_tuple(mock_load_prompt, mock_fetch_memory, mock_fetch_knowledge):
    mock_fetch_memory.return_value = []
    mock_fetch_knowledge.return_value = []
    
    result = await build_user_context("query", "soul")
    assert isinstance(result, tuple)
    assert len(result) == 2

@pytest.mark.asyncio
async def test_cache_prefix_contains_soul(mock_load_prompt, mock_fetch_memory, mock_fetch_knowledge):
    mock_fetch_memory.return_value = []
    mock_fetch_knowledge.return_value = []
    
    prefix, suffix = await build_user_context("query", "soul")
    assert prefix == "SOUL_PROMPT"

def test_build_worker_context_no_soul():
    text = build_worker_context("learning", task_desc="Learn python")
    assert "SOUL_PROMPT" not in text
    assert "Learn python" in text

def test_build_worker_context_under_budget():
    text = build_worker_context("brief", top_task="T", memory="M", tz="UTC")
    # Budget is 300 tokens
    assert len(text.split()) < 300
    assert "T" in text

def test_build_worker_context_memory_none():
    text = build_worker_context("brief", top_task="T", memory=None, tz="UTC")
    assert "T" in text
    # No crash
