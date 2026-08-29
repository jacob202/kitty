

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
