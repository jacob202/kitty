from pathlib import Path

from kitty_gateway.doctor import parse_env


def test_parse_env_unescapes_json_values(tmp_path):
    env_file = tmp_path / "openwebui.env"
    env_file.write_text(
        'OPEN_TERMINAL_URL="http://127.0.0.1:9614"\n',
        encoding="utf-8",
    )
    env_file.write_text(
        env_file.read_text(encoding="utf-8")
        + 'TOOL_SERVER_CONNECTIONS=\'[{"id":"community-filesystem-local","url":"http://127.0.0.1:9721"}]\'\n'
        + 'TERMINAL_SERVER_CONNECTIONS="[{\\\"id\\\":\\\"open-terminal-local\\\",\\\"url\\\":\\\"${OPEN_TERMINAL_URL}\\\"}]"\n',
        encoding="utf-8",
    )

    parsed = parse_env(Path(env_file))

    assert parsed["TOOL_SERVER_CONNECTIONS"] == '[{"id":"community-filesystem-local","url":"http://127.0.0.1:9721"}]'
    assert parsed["TERMINAL_SERVER_CONNECTIONS"] == '[{"id":"open-terminal-local","url":"http://127.0.0.1:9614"}]'
