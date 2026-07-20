"""Tests for gateway.document_validator.

Run without any external services. Spoofed extensions and oversized files
must be rejected loudly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gateway.document_validator import (
    DocumentValidationError,
    sanitize_filename,
    validate_document,
)


def test_validate_accepts_real_pdf(tmp_path: Path):
    f = tmp_path / "doc.pdf"
    f.write_bytes(b"%PDF-1.4 fake pdf content")
    assert validate_document(f).name == "doc.pdf"


def test_validate_rejects_spoofed_extension(tmp_path: Path):
    f = tmp_path / "evil.pdf"
    f.write_bytes(b"PK\x03\x04 fake docx payload")  # zip/docx magic, not PDF
    with pytest.raises(DocumentValidationError):
        validate_document(f)


def test_validate_rejects_disallowed_extension(tmp_path: Path):
    f = tmp_path / "script.exe"
    f.write_bytes(b"MZ\x90\x00 fake exe")
    with pytest.raises(DocumentValidationError):
        validate_document(f)


def test_validate_rejects_oversize(tmp_path: Path):
    f = tmp_path / "big.txt"
    f.write_bytes(b"x" * (201 * 1024 * 1024))
    with pytest.raises(DocumentValidationError):
        validate_document(f)


def test_sanitize_strips_path_components():
    assert sanitize_filename("../../secret.txt") == "secret.txt"
    assert "/" not in sanitize_filename("a/b/c.md")
    assert "\\" not in sanitize_filename("a\\b.md")
