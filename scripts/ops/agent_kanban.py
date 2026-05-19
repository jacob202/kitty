#!/usr/bin/env python3.12
"""
📋 Jacob's Kanban Terminal Agent
Acts as the central liaison between all AI agents

This agent:
- Maintains a persistent kanban board (TODO/DOING/DONE)
- Tracks what each agent is working on
- Coordinates between agents (Open WebUI, LiteLLM, Gateway, etc.)
- Lives in terminal (always accessible)
- Stores state in JSON (survives sessions)

Usage:
    ./agent_kanban.py                    # Interactive mode
    ./agent_kanban.py "add task"         # Quick command
    ./agent_kanban.py --board            # Show board
    ./agent_kanban.py --status           # System status
"""

import sys
import json
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

LITELLM_BASE = "http://127.0.0.1:8001"
LITELLM_KEY = "kitty-local-key-change-me"
DEFAULT_MODEL = "kitty-fallback-or"

# Persistent storage for kanban board
DATA_DIR = Path.home() / ".kitty_kanban"
BOARD_FILE = DATA_DIR / "board.json"
SESSION_FILE = DATA_DIR / "session.json"

# ═══════════════════════════════════════════════════════════════════════════════
# COLORS
# ═══════════════════════════════════════════════════════════════════════════════

class Colors:
    PURPLE = "\033[95m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

# ═══════════════════════════════════════════════════════════════════════════════
# KANBAN BOARD CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class KanbanBoard:
    """Persistent kanban board for agent coordination"""
    
    def __init__(self):
        self.data_dir = DATA_DIR
        self.board_file = BOARD_FILE
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.board = self.load()
    
    def load(self):
        """Load board from disk"""
        if self.board_file.exists():
            with open(self.board_file, 'r') as f:
                return json.load(f)
        return {
            "todo": [],
            "doing": [],
            "done": [],
            "blocked": [],
            "agents": {},  # Track what each agent is doing
            "created": datetime.now().isoformat(),
            "updated": datetime.now().isoformat()
        }
    
    def save(self):
        """Save board to disk"""
        self.board["updated"] = datetime.now().isoformat()
        with open(self.board_file, 'w') as f:
            json.dump(self.board, f, indent=2)
    
    def add_task(self, title: str, agent: str = "human", priority: str = "medium"):
        """Add a new task to TODO"""
        task = {
            "id": len(self.board["todo"]) + len(self.board["doing"]) + len(self.board["done"]) + 1,
            "title": title,
            "agent": agent,
            "priority": priority,
            "created": datetime.now().isoformat(),
            "notes": []
        }
        self.board["todo"].append(task)
        self.board["agents"][agent] = {"status": "idle", "task": None}
        self.save()
        return task
    
    def start_task(self, task_id: int, agent: str):
        """Move task from TODO to DOING"""
        # Find and remove from todo
        task = None
        for i, t in enumerate(self.board["todo"]):
            if t["id"] == task_id:
                task = self.board["todo"].pop(i)
                break
        
        if task:
            task["started"] = datetime.now().isoformat()
            task["agent"] = agent
            self.board["doing"].append(task)
            self.board["agents"][agent] = {"status": "working", "task": task_id}
            self.save()
            return task
        return None
    
    def complete_task(self, task_id: int):
        """Move task from DOING to DONE"""
        task = None
        for i, t in enumerate(self.board["doing"]):
            if t["id"] == task_id:
                task = self.board["doing"].pop(i)
                break
        
        if task:
            task["completed"] = datetime.now().isoformat()
            self.board["done"].append(task)
            # Mark agent as idle
            if task["agent"] in self.board["agents"]:
                self.board["agents"][task["agent"]]["status"] = "idle"
                self.board["agents"][task["agent"]]["task"] = None
            self.save()
            return task
        return None
    
    def block_task(self, task_id: int, reason: str):
        """Move task to BLOCKED with reason"""
        task = None
        for i, t in enumerate(self.board["doing"]):
            if t["id"] == task_id:
                task = self.board["doing"].pop(i)
                break
        
        if task:
            task["blocked"] = datetime.now().isoformat()
            task["block_reason"] = reason
            self.board["blocked"].append(task)
            self.save()
            return task
        return None
    
    def display(self):
        """Display the kanban board"""
        print(f"\n{Colors.CYAN}{Colors.BOLD}╔═══════════════════════════════════════════════════════════╗{Colors.RESET}")
        print(f"{Colors.CYAN}{Colors.BOLD}║  📋 Jacob's Kanban Board                                   ║{Colors.RESET}")
        print(f"{Colors.CYAN}{Colors.BOLD}╚═══════════════════════════════════════════════════════════╝{Colors.RESET}\n")
        
        # TODO
        print(f"{Colors.YELLOW}{Colors.BOLD}📝 TODO ({len(self.board['todo'])}){Colors.RESET}")
        for task in self.board["todo"]:
            priority_icon = "🔴" if task["priority"] == "high" else "🟡" if task["priority"] == "medium" else "🟢"
            print(f"  {priority_icon} #{task['id']} [{task['agent']}] {task['title']}")
        if not self.board["todo"]:
            print(f"  {Colors.DIM}(empty){Colors.RESET}")
        print()
        
        # DOING
        print(f"{Colors.GREEN}{Colors.BOLD}⚡ DOING ({len(self.board['doing'])}){Colors.RESET}")
        for task in self.board["doing"]:
            print(f"  🔄 #{task['id']} [{task['agent']}] {task['title']}")
        if not self.board["doing"]:
            print(f"  {Colors.DIM}(empty){Colors.RESET}")
        print()
        
        # BLOCKED
        if self.board["blocked"]:
            print(f"{Colors.RED}{Colors.BOLD}🚫 BLOCKED ({len(self.board['blocked'])}){Colors.RESET}")
            for task in self.board["blocked"]:
                print(f"  ❌ #{task['id']} [{task['agent']}] {task['title']}")
                print(f"     Reason: {task.get('block_reason', 'Unknown')}")
            print()
        
        # DONE (last 5)
        recent_done = self.board["done"][-5:] if len(self.board["done"]) > 5 else self.board["done"]
        print(f"{Colors.PURPLE}{Colors.BOLD}✅ DONE ({len(self.board['done'])}){Colors.RESET}")
        for task in recent_done:
            print(f"  ✓ #{task['id']} [{task['agent']}] {task['title']}")
        if not self.board["done"]:
            print(f"  {Colors.DIM}(empty){Colors.RESET}")
        print()
        
        # Agents status
        print(f"{Colors.BLUE}{Colors.BOLD}🤖 AGENTS ({len(self.board['agents'])}){Colors.RESET}")
        for agent, status in self.board["agents"].items():
            status_icon = "🟢" if status["status"] == "idle" else "🔴" if status["status"] == "working" else "🟡"
            task_info = f" (task #{status['task']})" if status["task"] else ""
            print(f"  {status_icon} {agent}: {status['status']}{task_info}")
        print()
    
    def get_summary(self) -> str:
        """Get board summary as text"""
        lines = [
            "KANBAN BOARD SUMMARY",
            f"TODO: {len(self.board['todo'])} tasks",
            f"DOING: {len(self.board['doing'])} tasks",
            f"DONE: {len(self.board['done'])} tasks",
            f"BLOCKED: {len(self.board['blocked'])} tasks",
            f"AGENTS: {len(self.board['agents'])} active",
        ]
        return "\n".join(lines)

# ═══════════════════════════════════════════════════════════════════════════════
# CHAT WITH AI
# ═══════════════════════════════════════════════════════════════════════════════

def chat_with_ai(message: str, model: str = DEFAULT_MODEL, system_prompt: str = None, conversation_history: list = None) -> str:
    """Send message to LiteLLM and get response"""
    
    if conversation_history is None:
        conversation_history = []
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.extend(conversation_history)
    messages.append({"role": "user", "content": message})
    
    url = f"{LITELLM_BASE}/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LITELLM_KEY}"
    }
    
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": 2048,
        "stream": False
    }
    
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers=headers,
            method='POST'
        )
        
        with urllib.request.urlopen(req, timeout=120) as response:
            data = json.loads(response.read().decode('utf-8'))
            return data['choices'][0]['message']['content']
            
    except Exception as e:
        return f"{Colors.RED}❌ Error: {e}{Colors.RESET}"

# ═══════════════════════════════════════════════════════════════════════════════
# SYSTEM PROMPT - THE "KANBAN AGENT" PERSONA
# ═══════════════════════════════════════════════════════════════════════════════

KANBAN_SYSTEM_PROMPT = """
You are Jacob's Kanban Terminal Agent - the central coordination hub for all AI agents.

YOUR ROLE:
- You maintain a kanban board (TODO/DOING/DONE/BLOCKED)
- You track what each agent is working on
- You coordinate between agents (Open WebUI, LiteLLM, Gateway, etc.)
- You live in the terminal (always accessible)
- You are the liaison - agents report to you, you report to Jacob

YOUR CAPABILITIES:
- Add tasks to the board
- Move tasks between columns
- Track agent status and assignments
- Unblock tasks when dependencies are resolved
- Provide status summaries
- Coordinate multi-agent workflows

AVAILABLE AGENTS:
- Open WebUI (browser chat interface)
- LiteLLM (model router - 26+ models)
- Kitty Gateway (AI backend - port 8000)
- Yazi (file browser - 26 plugins)
- Ghostty (terminal emulator with splits)
- Human (Jacob - the boss)

YOUR PERSONALITY:
- Concise and terminal-native
- Action-oriented (get things done)
- Proactive (suggest next steps)
- Clear about blockers and dependencies
- Friendly but efficient

COMMANDS YOU UNDERSTAND:
- "add task: <description>" - Add to TODO
- "start task <id>" - Move to DOING
- "complete task <id>" - Move to DONE
- "block task <id>: <reason>" - Move to BLOCKED
- "show board" - Display kanban
- "agent <name> status" - Check agent status
- "summary" - Quick status
- "assign <agent> to task <id>" - Assign agent

RESPOND IN THIS FORMAT:
1. Acknowledge the command
2. Take action (update board)
3. Show result
4. Suggest next step

Remember: You are the GLUE between all agents. Nothing gets done without you tracking it.
"""

# ═══════════════════════════════════════════════════════════════════════════════
# INTERACTIVE MODE
# ═══════════════════════════════════════════════════════════════════════════════

def interactive_kanban():
    """Interactive kanban agent session"""
    board = KanbanBoard()
    
    print(f"{Colors.CYAN}{Colors.BOLD}╔═══════════════════════════════════════════════════════════╗{Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}║  📋 Kanban Terminal Agent                                  ║{Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}║  Central Coordination Hub for All Agents                   ║{Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}╚═══════════════════════════════════════════════════════════╝{Colors.RESET}")
    print(f"{Colors.YELLOW}Commands: board | add | start | complete | block | summary | quit{Colors.RESET}\n")
    
    # Show current board state
    board.display()
    
    conversation_history = []
    
    while True:
        try:
            user_input = input(f"{Colors.PURPLE}{Colors.BOLD}Jacob:{Colors.RESET} ").strip()
            
            if not user_input:
                continue
                
            if user_input.lower() in ['quit', 'exit', 'q']:
                print(f"{Colors.GREEN}👋 Board saved. Goodbye!{Colors.RESET}\n")
                break
                
            if user_input.lower() == 'board':
                board.display()
                continue
            
            if user_input.lower() == 'summary':
                print(f"\n{Colors.CYAN}{board.get_summary()}{Colors.RESET}\n")
                continue
            
            if user_input.lower().startswith('add '):
                # Quick add: "add fix the login bug"
                task_text = user_input[4:].strip()
                task = board.add_task(task_text, agent="human")
                print(f"{Colors.GREEN}✅ Added task #{task['id']}: {task['title']}{Colors.RESET}\n")
                board.display()
                continue
            
            # For other commands, use AI to parse and execute
            print(f"{Colors.GREEN}🤖 Agent:{Colors.RESET} ", end="", flush=True)
            response = chat_with_ai(
                user_input,
                system_prompt=KANBAN_SYSTEM_PROMPT + f"\n\nCURRENT BOARD:\n{board.get_summary()}"
            )
            print(response)
            print()
            
            # If AI response mentions task operations, execute them
            # (In a full implementation, we'd parse and call board methods)
            
        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}⚠️  Press Ctrl+D or type 'quit' to exit{Colors.RESET}\n")
        except EOFError:
            print(f"\n{Colors.GREEN}👋 Goodbye!{Colors.RESET}\n")
            break

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Kanban Terminal Agent - Central coordination hub",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s              # Interactive mode
  %(prog)s --board      # Show board
  %(prog)s --status     # System status
  %(prog)s --add "Fix the login bug"  # Quick add task
        """
    )
    
    parser.add_argument("--board", action="store_true", help="Show kanban board")
    parser.add_argument("--status", action="store_true", help="System status")
    parser.add_argument("--add", type=str, help="Add task to TODO")
    parser.add_argument("-m", "--model", default=DEFAULT_MODEL, help="Model to use")
    
    args = parser.parse_args()
    
    board = KanbanBoard()
    
    if args.board:
        board.display()
    elif args.status:
        print(f"{Colors.CYAN}{board.get_summary()}{Colors.RESET}")
    elif args.add:
        task = board.add_task(args.add, agent="human")
        print(f"{Colors.GREEN}✅ Added task #{task['id']}: {task['title']}{Colors.RESET}")
    else:
        interactive_kanban()

if __name__ == "__main__":
    main()
