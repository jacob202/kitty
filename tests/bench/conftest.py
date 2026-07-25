from pathlib import Path

import pytest

from gateway.builder import queue as bq


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    p = tmp_path / "kittybuilder" / "builder_queue.db"
    bq.init_db(p)
    return p
