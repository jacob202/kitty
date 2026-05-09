#!/usr/bin/env python3
"""
Scaffold new components fast.
Usage: python scripts/scaffold.py <type> <name>
Types: tool, route, test, skill, module
"""

import sys
from pathlib import Path

TEMPLATES = {
    "tool": {
        "path": "src/tools/{name}.py",
        "content": '''"""Custom tool for {name}"""

from src.tools.base import BaseTool, ToolResult


class {Name}Tool(BaseTool):
    """Tool for {name}"""

    name = "{name}"
    description = "Description of {name}"
    
    def execute(self, **kwargs) -> ToolResult:
        # TODO: implement
        return ToolResult(success=False, message="Not implemented")
''',
    },
    "route": {
        "path": "src/api/routes/{name}_routes.py",
        "content": '''"""API routes for {name}"""

from flask import Blueprint, jsonify

{name}_bp = Blueprint("{name}", __name__)


@{name}_bp.route("/api/{name}", methods=["GET"])
def get_{name}():
    return jsonify({{"status": "ok"}})
''',
    },
    "test": {
        "path": "tests/test_{name}.py",
        "content": '''"""Tests for {name}"""

import pytest


def test_{name}_basic():
    """Basic test for {name}"""
    assert True
''',
    },
    "module": {
        "path": "src/{name}/__init__.py",
        "content": '''"""Module: {name}"""

__all__ = []
''',
    },
}

def main():
    if len(sys.argv) < 3:
        print("Usage: python scripts/scaffold.py <tool|route|test|module> <name>")
        print("Examples:")
        print("  python scripts/scaffold.py tool my_tool")
        print("  python scripts/scaffold.py route users")
        print("  python scripts/scaffold.py test users")
        return
    
    ttype = sys.argv[1]
    name = sys.argv[2]
    
    if ttype not in TEMPLATES:
        print(f"Unknown type: {ttype}. Available: {', '.join(TEMPLATES)}")
        return
    
    template = TEMPLATES[ttype]
    path = Path(template["path"].format(name=name))
    content = template["content"].format(name=name, Name=name.title().replace("_", ""))
    
    if path.exists():
        print(f"✗ Already exists: {path}")
        return
    
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    print(f"✓ Created: {path}")

if __name__ == "__main__":
    main()