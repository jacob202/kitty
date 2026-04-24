#!/bin/bash
# Task 2 Check: Verify type annotations were added and file imports cleanly
cd /Users/jacobbrizinski/Projects/kitty

# Check that types were added to at least some function signatures
if ! grep -q "-> str" src/utils/fuzzy_matcher.py && ! grep -q "-> list" src/utils/fuzzy_matcher.py && ! grep -q ": " src/utils/fuzzy_matcher.py | grep -c "def " | grep -q ":"; then
    echo "FAIL: No type annotations found in any function signature"
    exit 1
fi

# Check file still imports cleanly
python3 -c "from src.utils.fuzzy_matcher import fuzzy_match, normalize_component_id, extract_component_ids, fix_typo, tokenize_query, expand_query" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "FAIL: File does not import cleanly"
    exit 1
fi

echo "PASS: Types added and file imports cleanly"
exit 0
