#!/bin/bash
set -e
cd /Users/jacobbrizinski/Projects/kitty
set -a && source /Users/jacobbrizinski/Projects/kitty/.env && set +a
source venv/bin/activate
pip install fastapi uvicorn httpx -q 2>/dev/null

echo "Starting Kitty Gateway on port 8000..."
uvicorn gateway.app:app --host 127.0.0.1 --port 8000 --reload
