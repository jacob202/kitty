#!/usr/bin/env python3
"""
Kitty – Persistent multi‑specialist MLX router with streaming, session memory,
model switching, and safety‑first memory management for 16‑24 GB Apple Silicon.
Includes an integrated DuckDuckGo Web Search Tool.
Retrofit: Now uses the robust ModelPreloader for memory and context management.
"""
import json
import sys
import re
from typing import Dict, Tuple, List
from mlx_lm import stream_generate, generate

# Import the new preloader
from model_preloader import preloader

try:
    from duckduckgo_search import DDGS
    HAS_DDGS = True
except ImportError:
    HAS_DDGS = False

# ----------------------------------------------------------------------
# CONFIGURATION
# ----------------------------------------------------------------------
SPECIALISTS = ["code", "conversation", "research", "automotive", "general"]

ROUTER_SYSTEM = """You are a precise message router.
Analyze the last user message and return ONLY a JSON object with these keys:
- "specialist": "code", "conversation", "research", "automotive", or "router"
- "reasoning": short explanation (one sentence max)

Rules:
- "code" for programming, data extraction, technical, math, or science questions.
- "conversation" for casual chat, feelings, stories, or personal topics.
- "research" for looking up current events, news, documentation, or facts you do not know.
- "automotive" for car-related questions.
- "router" for simple greetings, clarifications, or if you can answer directly without a specialist.

Return ONLY the JSON, no markdown, no backticks. Example:
{"specialist":"research","reasoning":"User asked for recent news on Apple Silicon."}

History:
{history}

Latest message:
{user_message}
JSON:"""

# ----------------------------------------------------------------------
# GLOBAL STATE
# ----------------------------------------------------------------------
verbose = False                        # print reasoning & routing details

# ----------------------------------------------------------------------
# WEB SEARCH TOOL
# ----------------------------------------------------------------------
def perform_search(query: str) -> str:
    """Uses DuckDuckGo to perform a web search without an API key."""
    if not HAS_DDGS:
        return "Search Tool Error: 'duckduckgo-search' is not installed. Please run: pip install duckduckgo-search"
    
    try:
        results = DDGS().text(query, max_results=3)
        res_list = list(results) # Convert generator to list
        if not res_list:
            return "Search returned no results."
        
        res_str = "SEARCH RESULTS:\n"
        for r in res_list:
            res_str += f"- {r.get('title', 'No Title')}: {r.get('body', '')} (URL: {r.get('href', '')})\n"
        return res_str
    except Exception as e:
        return f"Search Tool Error: {e}"

# ----------------------------------------------------------------------
# ROUTER LOGIC
# ----------------------------------------------------------------------
def extract_json(text: str) -> dict:
    match = re.search(r'\{(?:[^{}]|{[^{}]*})*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return {}

def decide_specialist(user_msg: str) -> str:
    model, tokenizer, model_id = preloader.load_model_for_task("routing")
    
    history_str = ""
    # Get routing context history
    context = preloader.get_context("routing")
    for msg in context[-8:]: # Last 4 turns
        role_str = "User" if msg["role"] == "user" else "Assistant"
        history_str += f"{role_str}: {msg['content']}\n"

    prompt = ROUTER_SYSTEM.format(history=history_str, user_message=user_msg)
    response = generate(
        model,
        tokenizer,
        prompt=prompt,
        max_tokens=96,
        temp=0.1,
        verbose=False,
    )
    decision = extract_json(response)
    specialist = decision.get("specialist", "router").lower()
    reasoning = decision.get("reasoning", "")
    
    if specialist not in SPECIALISTS and specialist != "router":
        specialist = "router"
        
    if verbose:
        print(f"[Router] Decision: {specialist} – {reasoning}")
        
    # Append the user msg and routing decision to the router context
    preloader.append_to_context("routing", "user", user_msg)
    preloader.append_to_context("routing", "assistant", f"Routed to {specialist}: {reasoning}")
        
    return specialist

# ----------------------------------------------------------------------
# SPECIALIST RESPONSE WITH STREAMING, SESSION MEMORY & TOOLS
# ----------------------------------------------------------------------
def stream_specialist(specialist: str, user_msg: str) -> str:
    model, tokenizer, model_id = preloader.load_model_for_task(specialist)

    system_prompt = {
        "code": "You are an expert software developer. Provide clear, working code with explanations.",
        "conversation": "You are a warm, empathetic companion. Keep answers friendly and concise.",
        "research": "You are a web research assistant. If you need to look something up to answer the user, output EXACTLY the phrase `<search>your query</search>` and wait. The system will run the search and provide you the results to synthesize.",
        "automotive": "You are an automotive expert. Provide helpful mechanical and vehicle advice.",
        "router": "You are a helpful assistant. Answer the user's last message directly.",
    }.get(specialist, "You are a helpful assistant.")

    messages = [{"role": "system", "content": system_prompt}]
    
    # Get the context for this specific specialist
    context = preloader.get_context(specialist)
    messages.extend(context)
    
    # Add the current user message to the active messages list
    messages.append({"role": "user", "content": user_msg})

    def _generate_and_stream(msgs, prefix=""):
        if hasattr(tokenizer, "apply_chat_template"):
            prompt = tokenizer.apply_chat_template(
                msgs,
                tokenize=False,
                add_generation_prompt=True,
            )
        else:
            prompt = ""
            for m in msgs:
                prompt += f"{m['role'].capitalize()}: {m['content']}\n"
            prompt += "Assistant: "

        if prefix:
            print(f"{prefix}", end="", flush=True)

        full_response = ""
        if 'stream_generate' in globals():
            for token in stream_generate(
                model,
                tokenizer,
                prompt=prompt,
                max_tokens=768,
                temp=0.7 if specialist == "conversation" else 0.2,
            ):
                print(token, end="", flush=True)
                full_response += token
        else:
            full_response = generate(
                model,
                tokenizer,
                prompt=prompt,
                max_tokens=768,
                temp=0.7 if specialist == "conversation" else 0.2,
            )
            print(full_response, end="", flush=True)
        print()
        return full_response

    # Generate initial response
    full_response = _generate_and_stream(messages, f"[{specialist}] ")

    # Check if the model wants to search the web
    search_match = re.search(r'<search>(.*?)</search>', full_response, re.IGNORECASE)
    if search_match:
        query = search_match.group(1).strip()
        print(f"\n[System] 🔍 Executing web search for: '{query}'...")
        search_results = perform_search(query)
        if verbose:
            print(f"[System] Search results:\n{search_results}\n")
        
        # Append tool output to context and re-prompt the model
        messages.append({"role": "assistant", "content": full_response})
        tool_prompt = f"Here are the web search results:\n\n{search_results}\n\nPlease synthesize a final, comprehensive answer for the user."
        messages.append({"role": "user", "content": tool_prompt})
        
        print(f"\n[System] 🧠 Synthesizing final answer...")
        final_response = _generate_and_stream(messages, f"[{specialist} (Synthesis)] ")
        
        # Return both so the entire thought process is saved in the session history
        full_response = full_response + "\n\n" + final_response

    # Append to the context manager history
    preloader.append_to_context(specialist, "user", user_msg)
    preloader.append_to_context(specialist, "assistant", full_response)

    return full_response

# ----------------------------------------------------------------------
# COMMAND HANDLING (prefixed with '/')
# ----------------------------------------------------------------------
def handle_command(cmd: str) -> bool:
    global verbose
    parts = cmd.strip().split()
    if not parts:
        return True
    c = parts[0].lower()
    if c == "/exit":
        print("Goodbye!")
        sys.exit(0)
    elif c == "/reset":
        spec = parts[1].lower() if len(parts) > 1 else None
        if spec and spec not in SPECIALISTS and spec != "router":
            print(f"Invalid specialist. Choose: {SPECIALISTS + ['router']}")
        else:
            if spec:
                preloader.clear_context(spec)
            else:
                for s in SPECIALISTS + ["router"]:
                    preloader.clear_context(s)
                print("[System] All sessions cleared.")
        return True
    elif c == "/verbose":
        verbose = not verbose
        print(f"[System] Verbose mode {'ON' if verbose else 'OFF'}.")
        return True
    elif c == "/model":
        if len(parts) < 3:
            print(f"Usage: /model switch <specialist>  (e.g., /model switch code)")
            return True
        if parts[1].lower() == "switch":
            new_spec = parts[2].lower()
            if new_spec not in SPECIALISTS and new_spec != "router":
                print(f"Unknown specialist. Options: {SPECIALISTS + ['router']}")
                return True
            global forced_specialist
            forced_specialist = new_spec
            print(f"[System] Next message will be handled by '{new_spec}' (once).")
            return True
    return False

forced_specialist: str = None

# ----------------------------------------------------------------------
# MAIN INTERACTIVE LOOP
# ----------------------------------------------------------------------
def main():
    print("🐱 Kitty v2 – Multi‑specialist MLX Router (Retrofit with Preloader & Context Manager)")
    print("Specialists: " + ", ".join(SPECIALISTS))
    print("Type /verbose for routing details, /reset [specialist], /model switch <name>, /exit")

    while True:
        try:
            raw = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not raw:
            continue
        if raw.startswith("/"):
            handle_command(raw)
            continue

        global forced_specialist
        if forced_specialist:
            specialist = forced_specialist
            forced_specialist = None
            # Log it in router anyway so history exists
            preloader.append_to_context("routing", "user", raw)
            preloader.append_to_context("routing", "assistant", f"Forced route to {specialist}")
        else:
            specialist = decide_specialist(raw)

        if verbose:
            print(f"[Router] Handing off to '{specialist}'")
            
        stream_specialist(specialist, raw)
        
        # Memory freeing is now handled automatically inside load_model_for_task on the next turn
        # We don't free here so if the user talks to the same specialist twice, we avoid reloading!

if __name__ == "__main__":
    main()