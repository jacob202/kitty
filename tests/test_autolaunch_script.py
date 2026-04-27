from pathlib import Path


def test_autolaunch_does_not_create_root_kitty_package():
    script = Path("autolaunch.sh").read_text()

    assert 'mkdir -p "$PROJECT_ROOT/kitty/"' not in script
    assert 'mkdir -p "$PROJECT_ROOT/kitty' not in script
    assert "No root-level kitty/ package will be created." in script


def test_autolaunch_does_not_overwrite_live_env_or_frontend_package():
    script = Path("autolaunch.sh").read_text()

    assert 'cat > "$PROJECT_ROOT/.env"' not in script
    assert 'cat << \'EOF\' > "$PROJECT_ROOT/garage-ui/package.json"' not in script
    assert 'cat > "$PROJECT_ROOT/garage-ui/package.json"' not in script
    assert "Kept existing .env" in script
