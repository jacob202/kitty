#!/usr/bin/env python3
"""
Mandatory context brief for any agent entering this project.
Reads STANDUP.md, CURRENT_FOCUS.md, AGENTS.md, latest handoff.
Generates a 2-minute brief that every agent MUST see first.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def read_section(file_path, section_marker):
    """Extract a section from a markdown file."""
    try:
        content = file_path.read_text(encoding="utf-8")
        if section_marker in content:
            lines = content.split('\n')
            in_section = False
            result = []
            for line in lines:
                if section_marker in line:
                    in_section = True
                    continue
                if in_section:
                    if line.startswith('##') and section_marker not in line:
                        break
                    result.append(line)
            return '\n'.join(result).strip()
    except Exception as e:
        return f"[Error reading {file_path}: {e}]"
    return ""

def generate_brief():
    """Generate mandatory context brief."""
    
    standup_file = PROJECT_ROOT / "docs" / "STANDUP.md"
    focus_file = PROJECT_ROOT / "CURRENT_FOCUS.md"
    
    brief = []
    brief.append("=" * 80)
    brief.append("🚨 MANDATORY AGENT CONTEXT BRIEF - READ THIS FIRST 🚨")
    brief.append("=" * 80)
    brief.append("")
    
    # 1. Reality check
    brief.append("1️⃣  LOCATION CHECK")
    brief.append(f"   Working directory: {PROJECT_ROOT}")
    brief.append(f"   Authority: STANDUP.md (§0-§9)")
    brief.append("")
    
    # 2. Current state
    brief.append("2️⃣  CURRENT STATE (from CURRENT_FOCUS.md)")
    focus_content = focus_file.read_text(encoding="utf-8") if focus_file.exists() else ""
    for line in focus_content.split('\n')[:25]:
        if line.strip():
            brief.append(f"   {line}")
        if line.startswith("## Tests"):
            break
    brief.append("")
    
    # 3. What's done
    brief.append("3️⃣  WHAT'S DONE (Last Handoff Summary)")
    standup_content = standup_file.read_text(encoding="utf-8") if standup_file.exists() else ""
    in_handoff = False
    handoff_lines = []
    for line in standup_content.split('\n'):
        if "**Shipped:**" in line:
            in_handoff = True
        if in_handoff:
            if "**Next:**" in line:
                break
            handoff_lines.append(line)
    for line in handoff_lines[:15]:
        brief.append(f"   {line}")
    brief.append("")
    
    # 4. What's next
    brief.append("4️⃣  WHAT'S NEXT (from Handoff)")
    brief.append("   1) Fine-tune 'Stall Guard' logic in chat()")
    brief.append("   2) Validate R1 as default autonomous brain")
    brief.append("   3) Begin Phase 1.1 Autonomy implementation")
    brief.append("")
    
    # 5. Rules
    brief.append("5️⃣  NON-NEGOTIABLE RULES (STANDUP §3)")
    brief.append("   Rule 1: Autonomy is default (solve it, don't ask)")
    brief.append("   Rule 2: Restate task before starting (get go-ahead)")
    brief.append("   Rule 9: Verify pwd == ~/Projects/kitty (not Desktop)")
    brief.append("   Rule 10: Handoff only at session END (not per-message)")
    brief.append("")
    
    # 6. Test before commit
    brief.append("6️⃣  BEFORE COMMIT")
    brief.append("   $ venv/bin/python -m pytest tests/ -q --tb=short")
    brief.append("   Must pass with 530+ tests")
    brief.append("")
    
    brief.append("=" * 80)
    brief.append("NOW: Restate your task in your own words. Wait for 'go'.")
    brief.append("=" * 80)
    brief.append("")
    
    return "\n".join(brief)

if __name__ == "__main__":
    print(generate_brief())
