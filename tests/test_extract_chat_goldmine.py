"""Packet 024 phase 1 — offline extractor tests.

Covers: loader (ChatGPT JSON + flat text), JSON parsing (with fences),
validation (drops bad types + non-unreviewed items), sensitivity
auto-bump on recovery hints, and CLI dry-run.
"""
import json
from pathlib import Path

from scripts.curation.extract_chat_goldmine import (
    Chunk,
    ExtractionParseError,
    _parse_items,
    _tag,
    _valid,
    extract_from_chunk,
    load_source,
    main,
)


def _write(tmp: Path, name: str, content: str) -> Path:
    p = tmp / name
    p.write_text(content)
    return p


def test_load_flat_markdown(tmp_path):
    p = _write(tmp_path, "thread-about-kitty.md", "user: hi\nassistant: hi.\n")
    [c] = load_source(p)
    assert c.source == "thread-about-kitty.md"
    assert c.title == "thread about kitty"
    assert "assistant: hi" in c.text


def test_load_chatgpt_export_orders_by_create_time(tmp_path):
    p = _write(tmp_path, "conversations.json", json.dumps([
        {
            "title": "kitty ideas",
            "create_time": 1_710_000_000,
            "mapping": {
                "b": {"message": {"author": {"role": "assistant"}, "create_time": 2, "content": {"parts": ["second"]}}},
                "a": {"message": {"author": {"role": "user"}, "create_time": 1, "content": {"parts": ["first"]}}},
                "empty": {"message": None},
            },
        },
        {"title": "empty conv", "mapping": {}},
    ]))
    chunks = load_source(p)
    assert [c.source for c in chunks] == ["conversations.json#0"]
    assert chunks[0].title == "kitty ideas"
    assert chunks[0].started_at.startswith("2024-")
    assert chunks[0].text.index("first") < chunks[0].text.index("second")


def test_load_source_rejects_unknown_suffix(tmp_path):
    p = _write(tmp_path, "notes.pdf", "irrelevant")
    try:
        load_source(p)
    except SystemExit as e:
        assert "unsupported source" in str(e)
    else:
        raise AssertionError("expected SystemExit")


def test_parse_items_accepts_json_fence():
    raw = '```json\n{"items": [{"object_type": "idea_seed", "title": "x"}]}\n```'
    assert _parse_items(raw) == [{"object_type": "idea_seed", "title": "x"}]


def test_parse_items_raises_on_bad_json():
    try:
        _parse_items("not json at all")
    except ExtractionParseError:
        pass
    else:
        raise AssertionError("expected ExtractionParseError")


def test_valid_drops_bad_object_type_and_non_unreviewed():
    assert _valid({"object_type": "idea_seed", "user_review": "unreviewed"})
    assert not _valid({"object_type": "life_advice", "user_review": "unreviewed"})
    assert not _valid({"object_type": "idea_seed", "user_review": "approved"})


def test_tag_stamps_source_and_bumps_sensitivity_on_recovery_hints():
    chunk = Chunk(source="t.md", title="t", started_at="2026-06-01", text="")
    tagged = _tag({
        "object_type": "project_thread",
        "title": "kitty as recovery support surface",
        "evidence_quote": "we talked about relapse triggers and grief",
    }, chunk)
    assert tagged["evidence_source"] == "t.md"
    assert tagged["sensitivity"] == "sensitive"  # auto-bumped
    assert tagged["user_review"] == "unreviewed"
    assert tagged["date_or_period"] == "2026-06-01"


def test_tag_respects_normal_content():
    chunk = Chunk(source="t.md", title="t", started_at=None, text="")
    tagged = _tag({
        "object_type": "idea_seed",
        "title": "kitty desk lamp mode",
        "evidence_quote": "a small warm status light for the mac",
    }, chunk)
    assert tagged["sensitivity"] == "normal"
    assert "date_or_period" not in tagged


def test_extract_from_chunk_end_to_end_with_stub_llm():
    calls: list[list[dict]] = []

    def stub(messages: list[dict], model: str) -> str:
        calls.append(messages)
        return json.dumps({
            "items": [
                {
                    "object_type": "project_thread",
                    "title": "kitty",
                    "one_line": "the assistant",
                    "user_review": "unreviewed",
                    "sensitivity": "normal",
                    "evidence_quote": "kitty holds the thread",
                },
                # Dropped: bad type.
                {"object_type": "random_thought", "user_review": "unreviewed"},
                # Dropped: not unreviewed.
                {"object_type": "idea_seed", "user_review": "approved"},
            ]
        })

    chunk = Chunk(source="conv#0", title="ideas", started_at=None, text="kitty holds the thread")
    items = extract_from_chunk(chunk, llm=stub)
    assert len(items) == 1
    assert items[0]["evidence_source"] == "conv#0"
    assert calls, "llm was called"


def test_cli_dry_run(tmp_path, capsys):
    src = _write(tmp_path, "conv.md", "one two three")
    rc = main(["--source", str(src), "--dry-run"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "conv.md" in out
    assert "13 chars" in out


def test_cli_missing_source_is_error(tmp_path, capsys):
    rc = main(["--source", str(tmp_path / "nope.md")])
    assert rc == 2
