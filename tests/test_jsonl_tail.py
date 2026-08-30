

import pytest

from gateway.jsonl_tail import read_tail_lines


def test_read_tail_lines_propagates_real_read_failure() -> None:
    class BrokenPath:
        def exists(self) -> bool:
            return True

        def open(self, *_args, **_kwargs):
            raise PermissionError("denied")

    with pytest.raises(PermissionError, match="denied"):
        read_tail_lines(BrokenPath(), limit=5)  # type: ignore[arg-type]


def test_read_tail_lines_handles_missing_file_without_exists_preflight() -> None:
    class MissingPath:
        def exists(self) -> bool:
            raise AssertionError("exists() must not collapse filesystem errors")

        def open(self, *_args, **_kwargs):
            raise FileNotFoundError("gone")

    assert read_tail_lines(MissingPath(), limit=5) == []  # type: ignore[arg-type]
