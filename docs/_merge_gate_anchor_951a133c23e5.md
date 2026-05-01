## Focused Route Suite

Command:

```bash
/opt/homebrew/bin/python3.12 -m pytest tests/test_web_chat_phase1.py tests/test_brief_route.py tests/test_commands_route.py -q --tb=short
```

Exit code: 0

```text
......................                                                   [100%]
=============================== warnings summary ===============================
<frozen importlib._bootstrap>:488
  <frozen importlib._bootstrap>:488: DeprecationWarning: builtin type SwigPyPacked has no __module__ attribute

<frozen importlib._bootstrap>:488
  <frozen importlib._bootstrap>:488: DeprecationWarning: builtin type SwigPyObject has no __module__ attribute

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
22 passed, 2 warnings in 17.37s
sys:1: DeprecationWarning: builtin type swigvarlink has no __module__ attribute
```

## Launcher Status

Command:

```bash
./kitty status
```

Exit code: 0

```text
  running  PID 23741
  local    http://localhost:5001
  phone    http://127.0.0.1:5001
```

## Brief Smoke

Command:

```bash
curl -fsS --connect-timeout 5 --max-time 20 http://localhost:59999/api/brief
```

Exit code: 7

```text
curl: (7) Failed to connect to localhost port 59999 after 0 ms: Couldn't connect to server
```

## Command Smoke

Command:

```bash
curl -fsS --connect-timeout 5 --max-time 20 -X POST http://localhost:59999/api/command -H "Content-Type: application/json" -d '{"command":"/stuck"}'
```

Exit code: 7

```text
curl: (7) Failed to connect to localhost port 59999 after 0 ms: Couldn't connect to server
```

## Chat Smoke

Command:

```bash
curl -fsS --connect-timeout 5 --max-time 20 -X POST http://localhost:59999/api/chat -H "Content-Type: application/json" -d '{"message":"phase4 merge gate","domain":"chat"}'
```

Exit code: 7

```text
curl: (7) Failed to connect to localhost port 59999 after 0 ms: Couldn't connect to server
```

## Summary

- Failure count: 3
- Final status: fail

