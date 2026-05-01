import pytest
from pathlib import Path
from scripts.automate_builder import parse_intake, generate_spec

def test_parse_intake(tmp_path):
    intake_file = tmp_path / "intake.md"
    intake_file.write_text("""# Intake: Test Feature
## Goal
Do something cool.
## Allowed Files
- cool.py
## Forbidden Files
- bad.py
## Validation Commands
- pytest cool.py
""")
    
    data = parse_intake(intake_file)
    assert data["name"] == "Test Feature"
    assert data["goal"] == "Do something cool."
    assert "- cool.py" in data["allowed_files"]
    assert "- bad.py" in data["forbidden_files"]
    assert "- pytest cool.py" in data["validation_commands"]

def test_security_leak(tmp_path):
    intake_file = tmp_path / "leak.md"
    intake_file.write_text("""# Intake: Leak
## Allowed Files
- secret.py
## Forbidden Files
- secret.py
""")
    
    with pytest.raises(SystemExit):
        generate_spec(intake_file, tmp_path)

def test_generate_spec(tmp_path):
    intake_file = tmp_path / "valid.md"
    intake_file.write_text("""# Intake: Valid
## Goal
Goal text.
## Allowed Files
- ok.py
## Forbidden Files
- no.py
""")
    
    generate_spec(intake_file, tmp_path)
    # Check if a .spec.md file was created
    specs = list(tmp_path.glob("*.spec.md"))
    assert len(specs) == 1
    content = specs[0].read_text()
    assert "# Spec: Valid" in content
    assert "## Goal\nGoal text." in content
