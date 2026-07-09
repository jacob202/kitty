from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gateway import expert_proactive


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path, monkeypatch):
    db = tmp_path / "test.db"
    monkeypatch.setattr("gateway.db.KITTY_DB_FILE", db)
    monkeypatch.setattr("gateway.paths.KITTY_DB_FILE", db)
    monkeypatch.setattr("gateway.expert_state.KITTY_DB_FILE", db)
    monkeypatch.setattr("gateway.expert_proactive.paths.EXPERT_CURSORS_FILE", tmp_path / "expert_cursors.json")
    monkeypatch.setattr("gateway.expert_proactive.paths.EXPERT_STATE_FILE", tmp_path / "expert_state.json")
    monkeypatch.setattr("gateway.expert_proactive.paths.DEAD_LETTER_DIR", tmp_path / "dead_letter")
    monkeypatch.setattr("gateway.expert_proactive.paths.KITTY_DATA_DIR", tmp_path / "kitty_data")
    monkeypatch.setattr("gateway.expert_proactive.paths.LOGS_DIR", tmp_path / "logs")
    import gateway.db as kitty_db
    kitty_db.migrate(db)


@pytest.fixture
def mock_experts():
    return {
        "automotive": {
            "prompt_path": "fake/auto.md",
            "proactive_policy": {
                "watch_inbox": True,
                "watch_directories": ["/fake/obd"],
                "learning_enabled": True,
            },
        },
        "health": {
            "prompt_path": "fake/health.md",
            "proactive_policy": {
                "watch_inbox": True,
                "watch_directories": [],
                "learning_enabled": False,
            },
        },
    }


@pytest.fixture
def mock_inbox():
    return [
        {"id": "entry-1", "text": "Fuel trims are at +15% on bank 1"},
        {"id": "entry-2", "text": "Got a headache today"},
    ]


@pytest.mark.asyncio
@patch.dict("gateway.expert_proactive.knowledge.EXPERT_PROFILES", {}, clear=True)
@patch("gateway.expert_proactive.desktop_store.read_inbox")
@patch("gateway.expert_proactive.Path")
@patch("gateway.expert_proactive._already_evaluated")
@patch("gateway.expert_proactive._mark_evaluating")
@patch("gateway.expert_proactive.llm_client.call_llm")
@patch("gateway.expert_proactive.DeepResearcher")
@patch("gateway.expert_proactive.signal_store.emit")
@patch("gateway.expert_proactive.shutil.move")
async def test_proactive_polling(
    mock_shutil_move,
    mock_emit,
    mock_researcher_cls,
    mock_call_llm,
    mock_mark,
    mock_already_evaluated,
    mock_path,
    mock_read_inbox,
    mock_experts,
    mock_inbox,
):
    from gateway.expert_proactive import knowledge
    knowledge.EXPERT_PROFILES.update(mock_experts)
    mock_read_inbox.return_value = mock_inbox
    mock_already_evaluated.return_value = False
    mock_mark.return_value = True

    # Setup Path mock to return some fake files
    mock_dir = MagicMock()
    mock_dir.exists.return_value = True
    mock_dir.is_dir.return_value = True

    fake_csv = MagicMock()
    fake_csv.is_file.return_value = True
    fake_csv.suffix = ".csv"
    fake_csv.name = "log1.csv"
    st = MagicMock()
    st.st_size = 500
    st.st_mtime = 0 # old file
    fake_csv.stat.return_value = st
    fake_csv.read_text.return_value = "RPM,FuelTrim\n1000,+15\n"

    mock_dir.iterdir.return_value = [fake_csv]

    def side_effect_path(val):
        if str(val) == "/fake/obd":
            return mock_dir
        pm = MagicMock()
        pm.exists.return_value = True
        pm.read_text.return_value = "Expert Prompt"
        return pm

    mock_path.side_effect = side_effect_path

    # Setup LLM behavior
    mock_researcher = AsyncMock()
    mock_researcher.technical_deep_dive.return_value = "Web context: check vacuum leaks"
    mock_researcher_cls.return_value = mock_researcher

    # For automotive entry-1: "SEARCH: fuel trim", then headline
    # For automotive entry-2: "NO"
    # For automotive csv: "NO"
    # For health entry-1: "NO"
    # For health entry-2: "Headline"

    call_count = 0
    def llm_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        prompt = args[0][0]["content"] if isinstance(args[0], list) else args[0]
        if "automotive" in prompt and "Fuel trims" in prompt and "Research Context" not in prompt:
            return "SEARCH: fuel trims +15%"
        if "Research Context" in prompt:
            return "[Headline] Vacuum Leak Detected\n[T0 Action] Check hoses\nLikely an intake leak."
        if "health" in prompt and "headache" in prompt:
            return "[Headline] Hydration Check\n[T1 Action] Drink water\nCould be dehydration."
        return "NO"

    mock_call_llm.side_effect = llm_side_effect

    await expert_proactive.async_poll_experts()

    # Did we emit the right signals?
    emits = mock_emit.call_args_list
    # The evaluation markers are emitted via _mark_evaluating, which is mocked, so emit is only called for headlines

    assert len(emits) == 2

    # Auto emit
    assert emits[0].kwargs["source"] == "expert.automotive"
    assert emits[0].kwargs["payload"]["headline"] == "Vacuum Leak Detected"
    assert emits[0].kwargs["payload"]["action"] == "Check hoses"

    # Health emit
    assert emits[1].kwargs["source"] == "expert.health"
    assert emits[1].kwargs["payload"]["headline"] == "Hydration Check"
    assert emits[1].kwargs["payload"]["action"] == "Drink water"
