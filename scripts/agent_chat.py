#!/usr/bin/env python3.12
"""
Jacob's Terminal Agent 🤖
Chat with AI directly in terminal - no browser needed!

Usage:
    ./agent_chat.py                    # Interactive chat
    ./agent_chat.py "What's 2+2?"      # Quick question
    ./agent_chat.py -m kitty-smart     # Use specific model
"""

import sys
import json
import urllib.request
import urllib.error
from pathlib import Path

# Configuration
LITELLM_BASE = "http://127.0.0.1:8001"
LITELLM_KEY = "kitty-local-key-change-me"

# Free/cheap LiteLLM aliases from kitty_gateway/litellm_config.yaml.
DEFAULT_MODEL = "kitty-fallback-or"
FREE_MODELS = [
    "kitty-fallback-or",
    "kitty-default",
    "kitty-agent",
    "kitty-smart",
]

# Colors for pretty output
class Colors:
    PURPLE = "\033[95m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    RESET = "\033[0m"
    BOLD = "\033[1m"

def chat_with_ai(message: str, model: str = DEFAULT_MODEL, conversation_history: list = None) -> str:
    """Send message to LiteLLM and get response"""
    
    if conversation_history is None:
        conversation_history = []
    
    messages = conversation_history + [{"role": "user", "content": message}]
    
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
            
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else str(e)
        return f"{Colors.RED}❌ Error {e.code}: {error_body}{Colors.RESET}"
    except urllib.error.URLError as e:
        return f"{Colors.RED}❌ Connection error: {e.reason}{Colors.RESET}\n{Colors.YELLOW}💡 Is LiteLLM running? Try: litellm-start{Colors.RESET}"
    except Exception as e:
        return f"{Colors.RED}❌ Unexpected error: {e}{Colors.RESET}"

def quick_question(question: str, model: str = DEFAULT_MODEL):
    """One-shot question and answer"""
    print(f"{Colors.CYAN}{Colors.BOLD}🤖 Agent ({model}){Colors.RESET}")
    print(f"{Colors.PURPLE}You:{Colors.RESET} {question}\n")
    
    response = chat_with_ai(question, model)
    
    print(f"{Colors.GREEN}Agent:{Colors.RESET} {response}\n")

def interactive_chat(model: str = DEFAULT_MODEL):
    """Interactive chat session with conversation history"""
    print(f"{Colors.CYAN}{Colors.BOLD}╔═══════════════════════════════════════════════════════════╗{Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}║  🤖 Jacob's Terminal Agent                               ║{Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}║  Model: {model:<48}║{Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}╚═══════════════════════════════════════════════════════════╝{Colors.RESET}")
    print(f"{Colors.YELLOW}Type 'quit' or 'exit' to end | 'clear' to reset conversation{Colors.RESET}\n")
    
    conversation_history = []
    
    while True:
        try:
            user_input = input(f"{Colors.PURPLE}{Colors.BOLD}You:{Colors.RESET} ").strip()
            
            if not user_input:
                continue
                
            if user_input.lower() in ['quit', 'exit', 'q']:
                print(f"{Colors.GREEN}👋 Goodbye!{Colors.RESET}\n")
                break
                
            if user_input.lower() == 'clear':
                conversation_history = []
                print(f"{Colors.GREEN}💬 Conversation cleared!{Colors.RESET}\n")
                continue
            
            if user_input.lower() == 'models':
                print(f"{Colors.CYAN}Available LiteLLM aliases:{Colors.RESET}")
                print(f"  {Colors.GREEN}✅ kitty-fallback-or ← RECOMMENDED fallback{Colors.RESET}")
                print("  - kitty-default")
                print("  - kitty-agent")
                print("  - kitty-smart")
                print(f"\n{Colors.YELLOW}Use -m flag: ./agent_chat.py -m kitty-fallback-or{Colors.RESET}")
                print(f"{Colors.YELLOW}Or just: agent \"your question\"{Colors.RESET}\n")
                continue
            
            # Get response
            print(f"{Colors.GREEN}Agent:{Colors.RESET} ", end="", flush=True)
            response = chat_with_ai(user_input, model, conversation_history)
            print(response)
            print()  # Empty line for readability
            
            # Add to history
            conversation_history.append({"role": "user", "content": user_input})
            conversation_history.append({"role": "assistant", "content": response})
            
        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}⚠️  Interrupted. Type 'quit' to exit.{Colors.RESET}\n")
        except EOFError:
            print(f"\n{Colors.GREEN}👋 Goodbye!{Colors.RESET}\n")
            break

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Jacob's Terminal Agent - Chat with AI in terminal",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Interactive chat
  %(prog)s "What's 2+2?"            # Quick question
  %(prog)s -m kitty-smart           # Use smart model
  %(prog)s -m kitty-default "Help"  # Model + question
        """
    )
    
    parser.add_argument(
        "-m", "--model",
        default=DEFAULT_MODEL,
        help=f"Model to use (default: {DEFAULT_MODEL})"
    )
    
    parser.add_argument(
        "question",
        nargs="?",
        help="Quick question (if omitted, starts interactive chat)"
    )
    
    args = parser.parse_args()
    
    if args.question:
        quick_question(args.question, args.model)
    else:
        interactive_chat(args.model)

if __name__ == "__main__":
    main()
