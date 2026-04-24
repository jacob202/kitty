#!/bin/bash
# Task 2 Revert: Restore fuzzy_matcher.py to original
cd /Users/jacobbrizinski/Projects/kitty
git checkout -- src/utils/fuzzy_matcher.py
echo "Reverted src/utils/fuzzy_matcher.py"
