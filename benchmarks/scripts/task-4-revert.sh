#!/bin/bash
# Task 4 Revert: Restore both files and remove the new file
cd /Users/jacobbrizinski/Projects/kitty
git checkout -- src/core/error_handler.py src/tools/base.py 2>/dev/null
rm -f src/core/error_logger.py
echo "Reverted: error_handler.py, removed error_logger.py"
