"""Example usage of Antigravity/Orca-style tools in Kitty.

This script demonstrates how to use the new task boundary, async feedback,
codebase search, and team protocol features.
"""
import asyncio
from gateway.antigravity_tools import invoke_tool, get_tools


async def demo_task_boundary():
    """Demonstrate task boundary tracking."""
    print("=== Task Boundary Demo ===")
    
    # Open a new task
    result = await invoke_tool("task_boundary", {
        "action": "open",
        "name": "Implement feature X",
        "summary": "Starting implementation of the new feature"
    })
    print(f"Opened task: {result}")
    
    # Update progress
    result = await invoke_tool("task_boundary", {
        "action": "update",
        "task_id": result.get("task_id"),
        "status": "in_progress",
        "summary": "Working on core logic"
    })
    print(f"Updated task: {result}")
    
    # Close task
    result = await invoke_tool("task_boundary", {
        "action": "close",
        "task_id": result.get("task_id"),
        "summary": "Feature complete",
        "success": True
    })
    print(f"Closed task: {result}")


async def demo_notify_user():
    """Demonstrate user notifications."""
    print("\n=== Notification Demo ===")
    
    result = await invoke_tool("notify_user", {
        "message": "Review requested for implementation_plan.md",
        "artifact_path": "/path/to/implementation_plan.md",
        "priority": "warning"
    })
    print(f"Notification sent: {result}")


async def demo_codebase_search():
    """Demonstrate semantic code search."""
    print("\n=== Codebase Search Demo ===")
    
    result = await invoke_tool("codebase_search", {
        "query": "task boundary tracking",
        "top_k": 3
    })
    
    if result.get("success"):
        print(f"Found {result['count']} results:")
        for r in result.get("results", []):
            print(f"  - {r['source']}: {r['content'][:100]}...")
    else:
        print(f"Search failed or unavailable: {result.get('error')}")


async def demo_team_protocol():
    """Demonstrate team coordination."""
    print("\n=== Team Protocol Demo ===")
    
    # Share a discovery
    result = await invoke_tool("share_discovery", {
        "discovery": "Found that task boundaries are stored in task_boundaries.jsonl",
        "tags": ["task-system", "storage"],
        "agent_name": "demo-agent"
    })
    print(f"Discovery shared: {result}")
    
    # Get discoveries
    result = await invoke_tool("get_discoveries", {
        "agent_filter": "demo-agent"
    })
    print(f"Retrieved {result.get('count')} discoveries")


async def main():
    """Run all demos."""
    print("Antigravity/Orca Tools Demo\n")
    print("Available tools:")
    for tool in get_tools():
        print(f"  - {tool['name']}: {tool['description'][:60]}...")
    
    await demo_task_boundary()
    await demo_notify_user()
    await demo_codebase_search()
    await demo_team_protocol()
    
    print("\n=== Demo Complete ===")


if __name__ == "__main__":
    asyncio.run(main())
