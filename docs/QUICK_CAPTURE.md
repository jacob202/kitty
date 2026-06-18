# Kitty Quick Capture

Kitty has a tiny capture path that writes directly to `data/inbox.jsonl`. It does
not require chat, LiteLLM, or an AI response to succeed.

## Terminal

```bash
scripts/quick_capture.py "Remember to check the Sansui bias trim"
```

The entry uses the mobile-compatible inbox format and can later resurface through
`memory_graph` and search.

## Raycast

1. In Raycast, open `Extensions` → `Script Commands`.
2. Add this folder as a script command directory:

```text
/Users/jacobbrizinski/Projects/kitty/scripts/raycast
```

3. Run `Kitty Quick Capture`, type the capture text, and submit.

The Raycast wrapper calls:

```bash
scripts/quick_capture.py --source raycast_quick_capture "..."
```

## Testing

```bash
python3.12 -m pytest tests/test_quick_capture_script.py tests/test_raycast_quick_capture.py -q
```
