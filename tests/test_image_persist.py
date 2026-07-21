"""IMG-03 atomic image persistence contracts."""

from pathlib import Path

from mcp.imagen import io


def test_save_image_writes_atomically_and_leaves_no_temp_file(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(io.settings, "output_dir", tmp_path)

    path = io.save_image(b"png-bytes", prefix="atomic")

    assert path.read_bytes() == b"png-bytes"
    assert list(tmp_path.glob("*.tmp")) == []


def test_save_image_failure_does_not_leave_partial_artifact(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(io.settings, "output_dir", tmp_path)

    class BrokenBytes:
        def __bytes__(self):
            raise RuntimeError("write failed")

    try:
        io.save_image(BrokenBytes(), prefix="broken")  # type: ignore[arg-type]
    except RuntimeError as exc:
        assert "write failed" in str(exc)
    else:
        raise AssertionError("save_image unexpectedly succeeded")
    assert list(tmp_path.iterdir()) == []
