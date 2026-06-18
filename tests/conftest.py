import os

# Ensure gateway auth uses test bypass when GATEWAY_SECRET is unset during pytest runs.
os.environ.setdefault("KITTY_ENV", "test")
os.environ["GATEWAY_SECRET"] = ""

# Provide a dummy API key so backend/config.py can import without crashing.
# The Settings validator rejects blank keys at startup; tests that need a real
# key should mock the Anthropic client rather than using a live connection.
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-do-not-use-in-production")
