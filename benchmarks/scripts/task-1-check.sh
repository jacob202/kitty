#!/bin/bash
# Task 1 Check: Verify no files were modified
cd /Users/jacobbrizinski/Projects/kitty
git diff --quiet src/core/domain_router.py
exit $?
