#!/usr/bin/env bash
set -e

if [ ! -f .env ]; then
  echo "No .env found. Copying .env.example..."
  cp .env.example .env
  echo "Fill in your ANTHROPIC_API_KEY in .env, then run this script again."
  exit 1
fi

if [ ! -d .venv ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

source .venv/bin/activate

echo "Installing dependencies..."
pip install -q -r requirements.txt

echo ""
echo "Starting Kitty on http://localhost:8000"
echo "Point Open WebUI at: http://localhost:8000/v1"
echo "API key: anything (not validated)"
echo ""

uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
