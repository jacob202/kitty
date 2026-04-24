#!/bin/bash
# Task 3 Revert: Restore circuit_breaker.py to original
cd /Users/jacobbrizinski/Projects/kitty
git checkout -- src/utils/circuit_breaker.py
echo "Reverted src/utils/circuit_breaker.py"
