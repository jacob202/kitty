#!/bin/bash
# Task 5 Revert: Restore domain_router.py to original
cd /Users/jacobbrizinski/Projects/kitty
git checkout -- src/core/domain_router.py
echo "Reverted src/core/domain_router.py"
