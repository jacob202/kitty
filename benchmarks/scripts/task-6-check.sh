#!/bin/bash
# Task 6 Check: Verify tests exist and pass
cd /Users/jacobbrizinski/Projects/kitty

if [ ! -f tests/test_fuzzy_matcher.py ]; then
    echo "FAIL: tests/test_fuzzy_matcher.py does not exist"
    exit 1
fi

# Run the tests
python3 -m pytest tests/test_fuzzy_matcher.py -v 2>&1
pytest_exit=$?

if [ $pytest_exit -ne 0 ]; then
    echo "FAIL: Tests did not pass"
    exit 1
fi

echo "PASS: All tests pass"
exit 0
