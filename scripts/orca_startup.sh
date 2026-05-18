#!/bin/bash
# ===========================================================================
# Kitty Orca/Antigravity Startup Script
# Shows task summary and agent status on Ghostty launch
# ===========================================================================

echo "🔔 Orca Agent Mode Active"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Show active task boundaries
python3 /Users/jacobbrizinski/Projects/kitty/scripts/kitty_task.py summary

echo ""
echo "⚡ Quick Commands:"
echo "  kitty-task open \"Name\"        - Open new task"
echo "  kitty-task update <id>         - Update task"
echo "  kitty-task close <id>          - Close task"
echo "  kitty-task notify \"Message\"    - Send notification"
echo "  kitty-task discover \"Text\"     - Share discovery"
echo "  kitty-task discoveries         - Get discoveries"
echo "  kitty-task search \"Query\"      - Search codebase"
echo ""
echo "🎯 Aliases:"
echo "  kt  - kitty-task"
echo "  kn  - notify"
echo "  kd  - discover"
echo "  ks  - search"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
