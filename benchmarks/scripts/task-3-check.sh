#!/bin/bash
# Task 3 Check: Verify _resolve_state was renamed to _compute_state
cd /Users/jacobbrizinski/Projects/kitty

if grep -n "_resolve_state" src/utils/circuit_breaker.py; then
    echo "FAIL: _resolve_state still exists in file"
    exit 1
fi

# Count _compute_state occurrences (definition + call sites)
count=$(grep -c "_compute_state" src/utils/circuit_breaker.py)
if [ "$count" -lt 2 ]; then
    echo "FAIL: _compute_state found only $count time(s), expected at least 2"
    exit 1
fi

# Verify file imports cleanly
python3 -c "from src.utils.circuit_breaker import circuit_breaker, CircuitOpenError" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "FAIL: File does not import cleanly"
    exit 1
fi

echo "PASS: _resolve_state renamed to _compute_state ($count occurrences)"
exit 0
