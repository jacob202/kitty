#!/usr/bin/env python3
"""
Fix pass-only exception handlers to log errors.
"""

import ast
import sys
from pathlib import Path

def fix_pass_handlers(py: Path) -> int:
    try:
        content = py.read_text()
        tree = ast.parse(content)
        
        fixed = False
        new_lines = []
        
        for i, line in enumerate(content.split('\n'), 1):
            # Check if this line is a bare 'pass' in except block
            if 'except' in line and i + 1 < len(content.split('\n')):
                next_line = content.split('\n')[i]
                if next_line.strip() == 'pass':
                    # Replace with logging
                    new_lines.append(line)
                    new_lines.append(f"                logging.getLogger(__name__).warning(f'Error in {py.name}: {{e}}')")
                    fixed = True
                    continue
            new_lines.append(line)
        
        if fixed:
            py.write_text('\n'.join(new_lines))
            return 1
    except Exception as e:
        print(f"Error processing {py}: {e}", file=sys.stderr)
    return 0

def main():
    files_fixed = 0
    for py in Path('src').rglob('*.py'):
        if fix_pass_handlers(py):
            files_fixed += 1
            print(f"Fixed: {py}")
    
    print(f"\nFiles fixed: {files_fixed}")

if __name__ == "__main__":
    main()