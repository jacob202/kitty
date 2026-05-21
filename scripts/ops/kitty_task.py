#!/usr/bin/env python3
"""
Kitty Orca/Antigravity CLI - Ghostty Integration

This script provides command-line access to the Orca/Antigravity features
for integration with Ghostty terminal.

Usage:
    kitty-task summary                  - Show all task boundaries
    kitty-task open "Task Name"         - Open new task
    kitty-task update <id> "status"     - Update task
    kitty-task close <id>               - Close task
    kitty-notify "Message"              - Send notification
    kitty-discover "Discovery text"     - Share discovery
    kitty-discoveries                   - Get all discoveries
    kitty-search "query"                - Search codebase
"""

import sys
import os
sys.path.insert(0, '/Users/jacobbrizinski/Projects/kitty')

from gateway.antigravity_tools import invoke_tool
from gateway.task_boundary import task_boundary
import asyncio


def task_summary():
    """Show all task boundaries."""
    print("📋 Task Boundaries")
    print("━" * 50)
    print(task_boundary.current_summary())
    print()


def task_open(name, summary=""):
    """Open a new task boundary."""
    result = asyncio.run(invoke_tool("task_boundary", {
        "action": "open",
        "name": name,
        "summary": summary
    }))
    if result.get("success"):
        print(f"✅ Task opened: {result.get('task_id')}")
        print(f"   Name: {name}")
        if summary:
            print(f"   Summary: {summary}")
    else:
        print(f"❌ Error: {result.get('error')}")
    return result.get("task_id")


def task_update(task_id, status="in_progress", summary=""):
    """Update a task."""
    result = asyncio.run(invoke_tool("task_boundary", {
        "action": "update",
        "task_id": task_id,
        "status": status,
        "summary": summary
    }))
    if result.get("success"):
        print(f"📝 Task {task_id} updated to {status}")
        if summary:
            print(f"   {summary}")
    else:
        print(f"❌ Error: {result.get('error')}")
    return result


def task_close(task_id, summary="Complete"):
    """Close a task."""
    result = asyncio.run(invoke_tool("task_boundary", {
        "action": "close",
        "task_id": task_id,
        "summary": summary,
        "success": True
    }))
    if result.get("success"):
        print(f"✅ Task {task_id} closed")
        print(f"   Summary: {summary}")
    else:
        print(f"❌ Error: {result.get('error')}")
    return result


def notify(message, priority="info"):
    """Send a notification."""
    result = asyncio.run(invoke_tool("notify_user", {
        "message": message,
        "priority": priority
    }))
    if result.get("success"):
        print(f"🔔 Notification sent: {message}")
    else:
        print(f"❌ Error: {result.get('error')}")
    return result


def share_discovery(discovery, tags=None):
    """Share a discovery."""
    result = asyncio.run(invoke_tool("share_discovery", {
        "discovery": discovery,
        "tags": tags or ["general"],
        "agent_name": "ghostty-user"
    }))
    if result.get("success"):
        print(f"🔍 Discovery shared: {discovery[:50]}...")
    else:
        print(f"❌ Error: {result.get('error')}")
    return result


def get_discoveries():
    """Get all discoveries."""
    result = asyncio.run(invoke_tool("get_discoveries", {}))
    if result.get("success"):
        print("🔍 Shared Discoveries")
        print("━" * 50)
        for d in result.get("discoveries", []):
            print(f"  [{d.get('agent', 'unknown')}] {d.get('discovery')}")
            print(f"    Tags: {', '.join(d.get('tags', []))}")
            print(f"    Time: {d.get('timestamp', 'unknown')}")
            print()
        print(f"Total: {result.get('count', 0)} discoveries")
    else:
        print(f"❌ Error: {result.get('error')}")
    return result


def check_feedback(artifact_path):
    """Check feedback for an artifact."""
    result = asyncio.run(invoke_tool("check_feedback", {
        "artifact_path": artifact_path
    }))
    if result.get("success"):
        print(f"📝 Feedback for {artifact_path}")
        print("━" * 50)
        comments = result.get("comments", [])
        if comments:
            for comment in comments:
                print(f"  - {comment}")
        else:
            print("  No feedback yet")
        print(f"\nTotal: {result.get('feedback_count', 0)} comments")
    else:
        print(f"❌ Error: {result.get('error')}")
    return result


def search_codebase(query, top_k=5):
    """Search the codebase."""
    result = asyncio.run(invoke_tool("codebase_search", {
        "query": query,
        "top_k": top_k
    }))
    if result.get("success"):
        print(f"🔍 Search results for '{query}'")
        print("━" * 50)
        for r in result.get("results", []):
            print(f"  📄 {r.get('source')}")
            content = r.get('content', '').replace('\n', ' ')[:200]
            print(f"     {content}...")
            print()
        print(f"Found: {result.get('count', 0)} results")
    else:
        print(f"❌ {result.get('error', 'Search failed')}")
    return result


def main():
    """Main CLI entry point."""
    if len(sys.argv) < 2:
        print(__doc__)
        return
    
    command = sys.argv[1]
    
    if command == "summary":
        task_summary()
    
    elif command == "open":
        name = sys.argv[2] if len(sys.argv) > 2 else "Unnamed Task"
        summary = " ".join(sys.argv[3:]) if len(sys.argv) > 3 else ""
        task_open(name, summary)
    
    elif command == "update":
        if len(sys.argv) < 3:
            print("❌ Task ID required")
            return
        task_id = sys.argv[2]
        status = sys.argv[3] if len(sys.argv) > 3 else "in_progress"
        summary = " ".join(sys.argv[4:]) if len(sys.argv) > 4 else ""
        task_update(task_id, status, summary)
    
    elif command == "close":
        if len(sys.argv) < 3:
            print("❌ Task ID required")
            return
        task_id = sys.argv[2]
        summary = " ".join(sys.argv[3:]) if len(sys.argv) > 3 else "Complete"
        task_close(task_id, summary)
    
    elif command == "notify":
        message = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "Notification"
        notify(message)
    
    elif command == "discover":
        discovery = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else None
        if not discovery:
            print("❌ Discovery text required")
            return
        share_discovery(discovery)
    
    elif command == "discoveries":
        get_discoveries()
    
    elif command == "feedback":
        artifact = sys.argv[2] if len(sys.argv) > 2 else None
        if not artifact:
            print("❌ Artifact path required")
            return
        check_feedback(artifact)
    
    elif command == "search":
        query = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else None
        if not query:
            print("❌ Search query required")
            return
        search_codebase(query)
    
    else:
        print(f"❌ Unknown command: {command}")
        print(__doc__)


if __name__ == "__main__":
    main()
