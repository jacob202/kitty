#!/bin/bash
# Task 6 Revert: Remove test file
cd /Users/jacobbrizinski/Projects/kitty
rm -f tests/test_fuzzy_matcher.py
# Also clean __pycache__ if it was created
rm -rf tests/__pycache__
echo "Removed tests/test_fuzzy_matcher.py"
