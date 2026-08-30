"""Antigravity/Orca-style tools integration.

This module provides tool definitions and handlers for:
- task_boundary: Declare and track high-level task boundaries
- notify_user: Async notifications to users
- check_feedback: Poll for user feedback on artifacts
- codebase_search: Semantic code search
- agentic_mode: Three-phase mode switching
- team_protocol: Multi-agent coordination

Usage:
    from gateway.antigravity_tools import get_tools, invoke_tool

    tools = get_tools()
    result = await invoke_tool("task_boundary", {"action": "open", "name": "My Task"})
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List

logger = logging.getLogger("kitty.antigravity_tools")

# Lazy imports to avoid circular dependencies
_task_boundary = None
_async_feedback = None
_codebase_search = None
_web_tracker = None
_team_protocol = None


def get_task_boundary():
    """Lazy load task_boundary module."""
    global _task_boundary
    if _task_boundary is None:
        from gateway import task_boundary

        _task_boundary = task_boundary.task_boundary
    return _task_boundary


def get_async_feedback():
    """Lazy load async_feedback module."""
    global _async_feedback
    if _async_feedback is None:
        from gateway import async_feedback

        _async_feedback = async_feedback.async_feedback
    return _async_feedback


def get_codebase_search():
    """Lazy load codebase_search module."""
    global _codebase_search
    if _codebase_search is None:
        from gateway import codebase_search

        _codebase_search = codebase_search.codebase_search
    return _codebase_search


def get_web_tracker():
    """Lazy load web_tracker module."""
    global _web_tracker
    if _web_tracker is None:
        from gateway import web_tracker

        _web_tracker = web_tracker.web_tracker
    return _web_tracker


def get_team_protocol(task_list=None):
    """Lazy load team_protocol module."""
    global _team_protocol
    if _team_protocol is None:
        from gateway import team_protocol

        _team_protocol = team_protocol.get_team_protocol(task_list)
    return _team_protocol


# Tool definitions
ANTIGRAVITY_TOOLS = [
    {
        "name": "task_boundary",
        "description": "Declare a high-level task boundary to group actions and report progress. Use 'open' to start, 'update' to report progress, 'close' to finish.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["open", "update", "close"],
                    "description": "Action to perform",
                },
                "task_id": {
                    "type": "string",
                    "description": "Task ID (auto-generated if not provided)",
                },
                "name": {
                    "type": "string",
                    "description": "Task name (required for 'open' action)",
                },
                "status": {
                    "type": "string",
                    "enum": ["planning", "in_progress", "reviewing", "completed", "blocked"],
                    "description": "Task status",
                },
                "summary": {
                    "type": "string",
                    "description": "Progress summary or final summary",
                },
            },
            "required": ["action"],
        },
    },
    {
        "name": "notify_user",
        "description": "Notify the user of important updates, review requests, or status changes.",
        "parameters": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Notification message",
                },
                "artifact_path": {
                    "type": "string",
                    "description": "Optional path to related artifact",
                },
                "priority": {
                    "type": "string",
                    "enum": ["info", "warning", "critical"],
                    "default": "info",
                },
            },
            "required": ["message"],
        },
    },
    {
        "name": "check_feedback",
        "description": "Check if the user has left feedback on a specific artifact.",
        "parameters": {
            "type": "object",
            "properties": {
                "artifact_path": {
                    "type": "string",
                    "description": "Path to the artifact to check for feedback",
                },
            },
            "required": ["artifact_path"],
        },
    },
    {
        "name": "codebase_search",
        "description": "Semantically search the codebase for relevant code snippets, functions, or patterns.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query",
                },
                "top_k": {
                    "type": "integer",
                    "default": 5,
                    "description": "Number of results to return",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "web_capture",
        "description": "Capture a snapshot of a web page for change tracking.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to capture",
                },
                "content": {
                    "type": "string",
                    "description": "Page content to store",
                },
            },
            "required": ["url", "content"],
        },
    },
    {
        "name": "web_compare",
        "description": "Compare current web page snapshot with previous one.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to compare",
                },
            },
            "required": ["url"],
        },
    },
    {
        "name": "share_discovery",
        "description": "Share a discovery with other agents in the team.",
        "parameters": {
            "type": "object",
            "properties": {
                "discovery": {
                    "type": "string",
                    "description": "The discovery to share",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional tags for categorization",
                },
            },
            "required": ["discovery"],
        },
    },
    {
        "name": "get_discoveries",
        "description": "Get discoveries shared by other agents.",
        "parameters": {
            "type": "object",
            "properties": {
                "agent_filter": {
                    "type": "string",
                    "description": "Filter by specific agent",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter by tags",
                },
            },
        },
    },
]


async def invoke_tool(tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Invoke an antigravity tool by name with arguments."""
    try:
        if tool_name == "task_boundary":
            return await _handle_task_boundary(args)
        elif tool_name == "notify_user":
            return await _handle_notify_user(args)
        elif tool_name == "check_feedback":
            return await _handle_check_feedback(args)
        elif tool_name == "codebase_search":
            return await _handle_codebase_search(args)
        elif tool_name == "web_capture":
            return await _handle_web_capture(args)
        elif tool_name == "web_compare":
            return await _handle_web_compare(args)
        elif tool_name == "share_discovery":
            return await _handle_share_discovery(args)
        elif tool_name == "get_discoveries":
            return await _handle_get_discoveries(args)
        else:
            return {
                "success": False,
                "error": f"Unknown tool: {tool_name}",
                "message": f"Available tools: {[t['name'] for t in ANTIGRAVITY_TOOLS]}",
            }
    except Exception as e:
        logger.exception("Tool invocation failed: %s", tool_name)
        return {
            "success": False,
            "error": str(e),
            "message": f"Tool {tool_name} failed",
        }


async def _handle_task_boundary(args: Dict[str, Any]) -> Dict[str, Any]:
    """Handle task_boundary tool calls."""
    tb = get_task_boundary()
    action = args.get("action", "update")
    task_id = args.get("task_id", str(uuid.uuid4().hex[:8]))

    if action == "open":
        name = args.get("name", "Unnamed")
        description = args.get("summary", "")
        tb.open(task_id, name, description)
        return {
            "success": True,
            "task_id": task_id,
            "message": f"Task boundary opened: {name}",
        }

    elif action == "update":
        status = args.get("status", "in_progress")
        summary = args.get("summary", "")
        tb.update(task_id, status, summary)
        return {
            "success": True,
            "task_id": task_id,
            "message": f"Task {task_id} updated to {status}",
        }

    elif action == "close":
        summary = args.get("summary", "")
        success = args.get("success", True)
        tb.close(task_id, summary, success)
        return {
            "success": True,
            "task_id": task_id,
            "message": f"Task {task_id} closed",
        }

    return {
        "success": False,
        "error": f"Unknown action: {action}",
    }


async def _handle_notify_user(args: Dict[str, Any]) -> Dict[str, Any]:
    """Handle notify_user tool calls."""
    feedback = get_async_feedback()
    message = args.get("message", "")
    artifact_path = args.get("artifact_path", "")
    priority = args.get("priority", "info")

    if not message:
        return {"success": False, "error": "Message is required"}

    feedback.notify(message, artifact_path, priority)
    return {
        "success": True,
        "message": f"Notification sent: {message[:50]}...",
    }


async def _handle_check_feedback(args: Dict[str, Any]) -> Dict[str, Any]:
    """Handle check_feedback tool calls."""
    feedback = get_async_feedback()
    artifact_path = args.get("artifact_path", "")

    if not artifact_path:
        return {"success": False, "error": "artifact_path is required"}

    comments = feedback.check_feedback(artifact_path)
    return {
        "success": True,
        "artifact": artifact_path,
        "feedback_count": len(comments),
        "comments": comments,
    }


async def _handle_codebase_search(args: Dict[str, Any]) -> Dict[str, Any]:
    """Handle codebase_search tool calls."""
    query = args.get("query", "")
    top_k = args.get("top_k", 5)

    if not query:
        return {"success": False, "error": "Query is required"}

    search = get_codebase_search()

    if not search.is_available():
        return {
            "success": False,
            "error": "Codebase search not available (missing dependencies)",
        }

    results = search.search(query, top_k)
    return {
        "success": True,
        "query": query,
        "results": results,
        "count": len(results),
    }


async def _handle_web_capture(args: Dict[str, Any]) -> Dict[str, Any]:
    """Handle web_capture tool calls."""
    tracker = get_web_tracker()
    url = args.get("url", "")
    content = args.get("content", "")

    if not url or not content:
        return {"success": False, "error": "url and content are required"}

    snapshot_path = tracker.capture(url, content)
    return {
        "success": True,
        "url": url,
        "snapshot_path": snapshot_path,
        "message": f"Captured snapshot of {url}",
    }


async def _handle_web_compare(args: Dict[str, Any]) -> Dict[str, Any]:
    """Handle web_compare tool calls."""
    tracker = get_web_tracker()
    url = args.get("url", "")

    if not url:
        return {"success": False, "error": "url is required"}

    comparison = tracker.compare(url)
    return {
        "success": True,
        "url": url,
        "comparison": comparison,
    }


async def _handle_share_discovery(args: Dict[str, Any]) -> Dict[str, Any]:
    """Handle share_discovery tool calls."""
    tp = get_team_protocol()
    discovery = args.get("discovery", "")
    tags = args.get("tags", [])
    agent_name = args.get("agent_name", "unknown")

    if not discovery:
        return {"success": False, "error": "discovery is required"}

    tp.share_discovery(agent_name, discovery, tags)
    return {
        "success": True,
        "message": "Discovery shared",
    }


async def _handle_get_discoveries(args: Dict[str, Any]) -> Dict[str, Any]:
    """Handle get_discoveries tool calls."""
    tp = get_team_protocol()
    agent_filter = args.get("agent_filter")
    tags = args.get("tags")

    discoveries = tp.get_discoveries(agent_filter, tags)
    return {
        "success": True,
        "discoveries": discoveries,
        "count": len(discoveries),
    }


def get_tools() -> List[Dict[str, Any]]:
    """Return the list of antigravity tools."""
    return ANTIGRAVITY_TOOLS
