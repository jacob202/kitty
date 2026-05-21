"""Tests for the Kitty Filesystem OWUI tool."""

from __future__ import annotations

from pathlib import Path

from gateway.openwebui_library_tools.kitty_filesystem import Tools, _resolve_path


def test_resolve_path_allows_data_dir():
    p = _resolve_path("~/Projects/kitty/data")
    assert p is not None
    assert "kitty/data" in str(p)


def test_resolve_path_rejects_outside():
    p = _resolve_path("/etc/passwd")
    assert p is None


def test_resolve_path_rejects_system_root():
    p = _resolve_path("/")
    assert p is None


def test_list_directory(tmp_path, monkeypatch):
    import gateway.openwebui_library_tools.kitty_filesystem as fsmod
    monkeypatch.setattr(fsmod, "ALLOWED_ROOTS", [tmp_path])

    (tmp_path / "hello.txt").write_text("hello")
    (tmp_path / "sub").mkdir()
    tool = Tools()
    result = tool.list_directory(str(tmp_path))
    assert "hello.txt" in result
    assert "sub/" in result


def test_list_directory_not_found():
    tool = Tools()
    result = tool.list_directory("/nonexistent")
    assert "Error" in result or "outside allowed" in result


def test_read_file(tmp_path, monkeypatch):
    import gateway.openwebui_library_tools.kitty_filesystem as fsmod
    monkeypatch.setattr(fsmod, "ALLOWED_ROOTS", [tmp_path])

    f = tmp_path / "test.txt"
    f.write_text("Hello, world!")
    tool = Tools()
    result = tool.read_file(str(f))
    assert result == "Hello, world!"


def test_read_file_binary_does_not_crash(tmp_path, monkeypatch):
    import gateway.openwebui_library_tools.kitty_filesystem as fsmod
    monkeypatch.setattr(fsmod, "ALLOWED_ROOTS", [tmp_path])

    f = tmp_path / "test.bin"
    f.write_bytes(b"\x00\x01\x02\xff")
    tool = Tools()
    result = tool.read_file(str(f))
    assert isinstance(result, str)


def test_read_file_nonexistent():
    tool = Tools()
    result = tool.read_file("/nonexistent/file.txt")
    assert "Error" in result or "outside allowed" in result


def test_file_metadata(tmp_path, monkeypatch):
    import gateway.openwebui_library_tools.kitty_filesystem as fsmod
    monkeypatch.setattr(fsmod, "ALLOWED_ROOTS", [tmp_path])

    f = tmp_path / "test.txt"
    f.write_text("Hello")
    tool = Tools()
    result = tool.file_metadata(str(f))
    assert "test.txt" in result
    assert "size" in result


def test_batch_rename_dry_run(tmp_path, monkeypatch):
    import gateway.openwebui_library_tools.kitty_filesystem as fsmod
    monkeypatch.setattr(fsmod, "ALLOWED_ROOTS", [tmp_path])

    (tmp_path / "img_001.png").write_text("")
    (tmp_path / "img_002.png").write_text("")
    (tmp_path / "other.txt").write_text("")
    tool = Tools()
    result = tool.batch_rename(str(tmp_path), r"img_(\d+)", r"photo_\1", dry_run=True)
    assert "Would rename" in result
    assert "img_001" in result
    assert "img_002" in result
    assert (tmp_path / "img_001.png").exists()


def test_batch_rename_actual(tmp_path, monkeypatch):
    import gateway.openwebui_library_tools.kitty_filesystem as fsmod
    monkeypatch.setattr(fsmod, "ALLOWED_ROOTS", [tmp_path])

    (tmp_path / "img_001.png").write_text("")
    tool = Tools()
    result = tool.batch_rename(str(tmp_path), r"img_(\d+)", r"photo_\1", dry_run=False)
    assert "Renamed" in result
    assert not (tmp_path / "img_001.png").exists()
    assert (tmp_path / "photo_001.png").exists()


def test_batch_rename_no_match(tmp_path, monkeypatch):
    import gateway.openwebui_library_tools.kitty_filesystem as fsmod
    monkeypatch.setattr(fsmod, "ALLOWED_ROOTS", [tmp_path])

    tool = Tools()
    result = tool.batch_rename(str(tmp_path), r"NO_MATCH", r"x")
    assert "No files matched" in result
