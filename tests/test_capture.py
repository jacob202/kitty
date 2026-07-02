"""Tests for POST /capture/file — file upload and local path capture."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    from gateway import paths
    from gateway.app import app
    from gateway.routes import capture

    monkeypatch.setattr(paths, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(paths, "INBOX_FILE", tmp_path / "data" / "inbox.jsonl")
    monkeypatch.setattr(capture, "INBOX_FILE", tmp_path / "data" / "inbox.jsonl")
    monkeypatch.setattr(capture, "CAPTURES_DIR", tmp_path / "data" / "captures")
    monkeypatch.setattr(capture, "_index_capture", lambda _cid, _path: None)

    return TestClient(app)


class TestCaptureFile:
    def test_capture_upload_pdf_queues_and_writes_inbox(self, client, tmp_path):
        pdf = tmp_path / "note.pdf"
        pdf.write_text("%PDF-1.4 fake pdf content")

        with pdf.open("rb") as f:
            response = client.post(
                "/capture/file",
                files={"file": ("note.pdf", f, "application/pdf")},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "queued"
        assert "capture_id" in body

        from gateway.routes import capture

        inbox_lines = [
            json.loads(line)
            for line in capture.INBOX_FILE.read_text().splitlines()
            if line.strip()
        ]
        assert len(inbox_lines) == 1
        assert inbox_lines[0]["type"] == "file_upload"
        assert inbox_lines[0]["status"] == "queued"
        assert inbox_lines[0]["capture_id"] == body["capture_id"]

    def test_capture_local_path_queues_and_writes_inbox(self, client, tmp_path):
        txt = tmp_path / "note.txt"
        txt.write_text("hello world")

        response = client.post("/capture/file", data={"path": str(txt)})

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "queued"

        from gateway.routes import capture

        inbox_lines = [
            json.loads(line)
            for line in capture.INBOX_FILE.read_text().splitlines()
            if line.strip()
        ]
        assert len(inbox_lines) == 1
        assert inbox_lines[0]["type"] == "local_path"
        assert inbox_lines[0]["source_path"] == str(txt)

    def test_capture_rejects_missing_file_and_path(self, client):
        response = client.post("/capture/file")
        assert response.status_code == 400

    def test_capture_rejects_both_file_and_path(self, client, tmp_path):
        pdf = tmp_path / "note.pdf"
        pdf.write_text("%PDF-1.4 fake pdf content")

        with pdf.open("rb") as f:
            response = client.post(
                "/capture/file",
                files={"file": ("note.pdf", f, "application/pdf")},
                data={"path": str(pdf)},
            )
        assert response.status_code == 400

    def test_capture_rejects_unsupported_type(self, client, tmp_path):
        bad = tmp_path / "virus.exe"
        bad.write_bytes(b"evil")

        with bad.open("rb") as f:
            response = client.post(
                "/capture/file",
                files={"file": ("virus.exe", f, "application/x-msdownload")},
            )
        assert response.status_code == 415

    def test_capture_rejects_oversized_file(self, client, tmp_path, monkeypatch):
        from gateway.routes import capture

        monkeypatch.setattr(capture, "MAX_CAPTURE_BYTES", 100)
        txt = tmp_path / "big.txt"
        txt.write_text("x" * 200)

        with txt.open("rb") as f:
            response = client.post(
                "/capture/file",
                files={"file": ("big.txt", f, "text/plain")},
            )
        assert response.status_code == 413

    def test_capture_rejects_nonexistent_path(self, client, tmp_path):
        response = client.post("/capture/file", data={"path": str(tmp_path / "missing.pdf")})
        assert response.status_code == 404
