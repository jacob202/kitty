from pathlib import Path


def test_gateway_work_projection_module_exists():
    assert Path("gateway/work_projection.py").is_file()
