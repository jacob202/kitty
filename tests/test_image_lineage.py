"""IMG-04 provider-neutral image lineage contracts."""

from pathlib import Path

import pytest

from gateway import image_jobs as jobs


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path: Path):
    import gateway.paths as paths

    original = paths.KITTY_DB_FILE
    paths.KITTY_DB_FILE = tmp_path / "kitty.db"
    yield
    paths.KITTY_DB_FILE = original


def test_list_children_returns_variations_in_creation_order():
    source = jobs.create_job(provider="comfyui", operation="txt2img", prompt="source")
    first = jobs.create_job(
        provider="comfyui", operation="variation", prompt="first", parent_id=source.job_id
    )
    second = jobs.create_job(
        provider="drawthings", operation="variation", prompt="second", parent_id=source.job_id
    )

    children = jobs.list_children(source.job_id)

    assert [child.job_id for child in children] == [first.job_id, second.job_id]
    assert all(child.parent_id == source.job_id for child in children)
