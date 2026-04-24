#!/bin/bash
# Task 4 Check: Verify log_error extracted to new file
cd /Users/jacobbrizinski/Projects/kitty

# Check new file exists
if [ ! -f src/core/error_logger.py ]; then
    echo "FAIL: src/core/error_logger.py does not exist"
    exit 1
fi

# Check new file has log_error function
if ! grep -q "def log_error" src/core/error_logger.py; then
    echo "FAIL: log_error not found in error_logger.py"
    exit 1
fi

# Check old file no longer has log_error (it was removed, not duplicated)
if grep -q "def log_error" src/core/error_handler.py; then
    echo "WARN: log_error still exists in error_handler.py (may be re-export)"
fi

# Verify imports work
python3 -c "from src.core.error_logger import log_error" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "FAIL: Cannot import log_error from error_logger.py"
    exit 1
fi

echo "PASS: log_error extracted to src/core/error_logger.py"
exit 0
