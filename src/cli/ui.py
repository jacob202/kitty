import subprocess
import sys

from rich import box
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.core.aura_loader import get_branding
from src.utils.cli_helpers import load_library_index, p_dim, p_success, p_warn

_branding = get_branding()

try:
    from src.utils.summarizer import summarize_history
except ImportError:

    def summarize_history(history: list, max_tokens: int = 256) -> str:  # type: ignore[misc]
        return ""


console = Console()

_CAT = """\
[cyan]  /\\_/\\  [/cyan]
[cyan] ( o.o ) [/cyan]
[cyan]  > ^ <  [/cyan]"""

# ── Command registry — single source of truth for help + completion ─────────
COMMANDS = {
    "/vibe": ("/vibe", "Tells you how you're doing based on your chat history"),
    "/brief": ("/brief", "Morning context brief — where you left off + one next thing"),
    "/stuck": (
        "/stuck [what you were doing]",
        "ADHD rescue — gives you the ONE next physical step",
    ),
    "/bench": (
        "/bench [mode|off]",
        "Set work mode (e.g. /bench sansui). Auto-injects context every query.",
    ),
    "/prep": (
        "/prep",
        f"Generate prescriber appointment brief → exports to {_branding['exports_dir']}/",
    ),
    "/capture": ("/capture <thought>", "Quick brain dump — saves a thought without friction"),
    "/review": ("/review", "Show all captures, saved facts, and OBD health"),
    "!!": ("!!", "Re-run last query escalated to next model tier"),
    "/repair": (
        "/repair <photo> [context]",
        "Analyse a repair photo → flag issues, list parts, search CA prices",
    ),
    "/image": ("/image <photo> [question]", "Ask Claude vision anything about an image"),
    "/ingest": ("/ingest [path]", "Ingest PDFs, EPUBs or images into the library"),
    "/process-pdf": ("/process-pdf <path>", "Process all pages of a PDF schematic in parallel"),
    "/deepsearch": (
        "/deepsearch [--depth N] [--pages N] <query>",
        "Web search + optional recursive crawl + Claude synthesis (uses Tavily)",
    ),
    "/remember": (
        "/remember <fact>",
        f"Save a persistent fact {_branding['assistant_name'].lower()} always knows",
    ),
    "/forget": ("/forget <key>", "Remove a saved fact by its key"),
    "/memories": ("/memories", "List all saved facts"),
    "/paste": ("/paste", "Enter multi-line mode — paste a block of text, end with blank line"),
    "/export": ("/export", f"Save this session to {_branding['exports_dir']}/ as markdown"),
    "/clip": ("/clip", "Load clipboard as context for your next message"),
    "/library": ("/library", "List all indexed documents"),
    "/history": ("/history", "Show conversation turns this session"),
    "/status": ("/status", "Show model tiers, tools, cost, memory"),
    "/clear": ("/clear", "Clear conversation history (keeps library)"),
    "/new": ("/new", "Create a new specialist agent interactively"),
    "/code": (
        "/code [path]",
        f"Set coding mode for a project. All queries → {_branding['coder_name']} (Fast·Flash).",
    ),
    "/screen": ("/screen [question]", "Take a screenshot → ask Claude vision what's on screen"),
    "/watch": (
        "/watch [on|off|30]",
        "Continuous screen watcher — notifies you when screen changes",
    ),
    "/cal": ("/cal [days]", "List upcoming calendar events (default: 7 days)"),
    "/cal add": ("/cal add 'Title' 2025-01-15 09:00", "Create a calendar event"),
    "/msg": ("/msg <contact> <text>", "Send an iMessage (asks for confirmation first)"),
    "/obsidian": ("/obsidian <cmd> ...", "Obsidian: note, append, read, search, list"),
    "/voice": (
        "/voice",
        f"Toggle MacWhisper voice input (auto-submits via {_branding['voice_file']})",
    ),
    "/permissions": (
        "/permissions",
        "Trigger macOS permission dialogs for screen, contacts, calendar, messages",
    ),
    "/mode": (
        "/mode [unhinged|helpful|focus|calm|briefing]",
        f"Switch {_branding['assistant_name']}'s personality mode — auto-detected if omitted",
    ),
    "/debug": ("/debug", "Toggle debug mode — shows routing JSON + tier before each response"),
    "/errors": ("/errors", "Show recent system errors and suggested fixes"),
    "/sansui": ("/sansui", "Enter Sansui 9090 repair mode"),
    "/tutor": (
        "/tutor [chat|quiz|deep_solve] [topic]",
        "Multi-mode learning workspace (chat, quiz, research, deep_solve, math)",
    ),
    "/help": ("/help [command]", "Show all commands, or details for one command"),
    "/exit": ("/exit", "Save session and quit"),
    "/summarize": (
        "/summarize",
        "Condense conversation history into a 256-token summary and save it",
    ),
    "/debate": (
        "/debate <topic> [--mode debate|consensus]",
        "Multi-model debate with synthesis and agreement analysis",
    ),
    "/expert": (
        "/expert <topic> [--experts electronics,coding,research]",
        "Expert panel with specialized domain roles",
    ),
    "/synthesize": (
        "/synthesize <query>",
        "Quick council query showing agreements and dissenting views",
    ),
    "/bom": (
        "/bom <export|pricing|compare|summary|shopping> [args]",
        "BOM export, pricing, comparison and procurement tools",
    ),
    "/skill": (
        "/skill <name>",
        "Load a superpower skill's instructions (use /skills to list)",
    ),
    "/skills": (
        "/skills",
        "List all available superpower skills",
    ),
}


def print_banner(sup):
    library = load_library_index()
    console.print()
    console.print(_CAT)
    console.print(
        f"[bold cyan]  {_branding['name'].lower()}[/bold cyan] [dim]— your personal AI[/dim]\n"
    )

    # ── Model tiers ──────────────────────────────────────────────────────────
    sup.config.get("flash_model", "—")
    mt = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    mt.add_column("cost", style="dim", width=6)
    mt.add_column("tier", style="dim", width=4)
    mt.add_column("model", style="white", width=34)
    mt.add_column("note", style="dim", width=16)
    mt.add_row(
        "$0.10/M",
        "T2",
        f"[green]{sup.config.get('flash_model', 'gemini-flash')}[/green]",
        "default · smart",
    )
    mt.add_row("$0.55/M", "T3", f"[blue]{sup.config['cheap_model']}[/blue]", "reasoning · code")
    mt.add_row(
        "PAID",
        "T4",
        f"[magenta]{sup.config.get('supervisor_model', 'claude')}[/magenta]",
        "health · vision",
    )
    console.print(mt)

    # ── System status ─────────────────────────────────────────────────────────
    specs = "  ".join(f"[green]{s['name']}[/green]" for s in sup.specialists) or "[dim]none[/dim]"
    console.print(f"  [dim]Specialists:[/dim] {specs}")
    console.print(
        f"  [dim]Library:[/dim] [white]{len(library)}[/white][dim] docs  ·  Tools:[/dim] [white]{len(sup.tools)}[/white][dim] loaded[/dim]"
    )
    if sup.history:
        console.print(
            f"  [dim]Session:[/dim] [white]{len(sup.history) // 2}[/white][dim] prior turns restored[/dim]"
        )

    # ── Quick start ───────────────────────────────────────────────────────────
    console.print()
    qs = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    qs.add_column("cmd", style="bold green", width=24)
    qs.add_column("desc", style="white")
    qs.add_row("/bench sansui", "focused repair mode (Sansui context auto-injected)")
    qs.add_row("/bench ridgeline", "diagnostics mode (Ridgeline context auto-injected)")
    qs.add_row("/prep", "generate prescriber appointment doc")
    qs.add_row("/capture", "quick brain dump (timestamped)")
    qs.add_row("/stuck", "can't start? → one physical next step")
    qs.add_row("/brief", "run this first — context anchor + one next thing")
    console.print(
        Panel(
            qs, title="[bold cyan]Quick Start[/bold cyan]", border_style="dim cyan", padding=(0, 0)
        )
    )

    # ── Contextual nudges ─────────────────────────────────────────────────────
    nudges = []
    facts = sup.memory.get_facts()
    caps = [v for k, v in facts.items() if k.startswith("capture_")]
    obd = sup.memory.data.get("obd_health", "")
    if caps:
        nudges.append(f"[yellow]·[/yellow] {len(caps)} capture(s) pending — [dim]/review[/dim]")
    if obd:
        nudges.append(f"[yellow]·[/yellow] OBD: {obd} — [dim]/bench ridgeline then ask[/dim]")
    if sup._active_mode:
        nudges.append(
            f"[cyan]·[/cyan] Bench mode: [bold]{sup._active_mode['name']}[/bold] — [dim]/bench off to clear[/dim]"
        )
    if nudges:
        console.print()
        for n in nudges:
            console.print(f"  {n}")
    console.print()


_CMD_DETAILS = {
    "/brief": {
        "what": "Reads your memory and last session, generates a morning context brief — where you left off and ONE next thing.",
        "examples": ["/brief", "(run every morning as first command)"],
    },
    "/stuck": {
        "what": "ADHD rescue. Gives you exactly ONE physical next step — not a list, not options. One action verb.",
        "examples": [
            "/stuck",
            "/stuck I was trying to fix the Bank 2 lean",
            "/stuck I need to prep for my NP appointment",
        ],
    },
    "/bench": {
        "what": "Sets a work mode — injects context into every query until cleared. Shows in toolbar.",
        "examples": ["/bench sansui", "/bench ridgeline", "/bench heathkit", "/bench off"],
    },
    "/prep": {
        "what": f"Generates a full prescriber appointment brief using your health context. Exports to {_branding['exports_dir']}/.",
        "examples": ["/prep", "(then print or show it to your NP)"],
    },
    "/capture": {
        "what": "Brain dump without friction. Saves a thought instantly with a timestamp. No categorization needed.",
        "examples": [
            "/capture check LTFT after spark plugs installed",
            "/capture NP appointment — ask about TRT workup",
            "/capture pick up Vitamin D from Shoppers",
        ],
    },
    "/review": {
        "what": "Shows all captures, saved facts, and OBD health in one view.",
        "examples": ["/review"],
    },
    "!!": {
        "what": "Re-runs your last message but sends it to a higher model tier for a more detailed answer.",
        "examples": ["!! (after any response that wasn't good enough)"],
    },
    "/pattern": {
        "what": "Applies a named prompt to text you pass or your clipboard. Reusable prompt shortcuts.",
        "examples": [
            "/pattern              (list all patterns)",
            "/pattern summarize    (summarize clipboard)",
            "/pattern obd-explain  (plain-English OBD data)",
            "/pattern parts-search (format parts list for Digi-Key CA)",
            "/pattern med-check venlafaxine",
            "/pattern prescriber-explain  (clinical note for NP)",
        ],
    },
    "/code": {
        "what": f"Sets coding mode for a project directory. Every query auto-routes to {_branding['coder_name']} (Fast·Flash). {_branding['assistant_name'].lower()} reads files, makes edits, runs tests. /code off to exit.",
        "examples": [
            "/code ~/myproject",
            "/code ~/AgentCompany",
            "/code  (uses current directory)",
            "/code off  (exit code mode)",
        ],
    },
    "/screen": {
        "what": "Takes a screenshot of your screen and asks Claude vision what's on it. Good for debugging, UI help, reading anything.",
        "examples": [
            "/screen",
            "/screen what is this error?",
            "/screen how do I fix this setting?",
        ],
    },
    "/repair": {
        "what": "Vision analysis of a repair photo — identifies issues, lists parts needed, searches Canadian prices.",
        "examples": [
            "/repair ~/Desktop/board.jpg",
            "/repair ~/Desktop/amp.jpg left channel output stage",
        ],
    },
    "/image": {
        "what": "Ask Claude vision anything about any image.",
        "examples": [
            "/image ~/Desktop/photo.jpg what is this component?",
            "/image ~/Desktop/schematic.png explain this circuit",
        ],
    },
    "/deepsearch": {
        "what": "Full web research: searches Tavily, optionally crawls linked pages recursively, synthesizes with Claude. Results stored in vector DB for RAG. Takes 30s-2min depending on depth.",
        "examples": [
            "/deepsearch best electrolytic recap kit Canada 2025",
            "/deepsearch exhaust manifold gasket J35A9 repair procedure",
            "/deepsearch --depth 2 --pages 30 latest quantum computing breakthroughs",
            "/deepsearch --depth 1 open source llm fine tuning 2025",
        ],
    },
    "/clip": {
        "what": "Loads your clipboard as context for your NEXT message. Useful for long text you want to ask about.",
        "examples": [
            "/clip  then: what does this mean?",
            "/clip  then: translate this to plain English",
        ],
    },
    "/paste": {
        "what": "Multi-line paste mode — paste a block of text (error log, code, etc.), end with a blank line.",
        "examples": ["/paste  (paste OBD log, submit with blank line)"],
    },
    "/remember": {
        "what": f"Saves a fact persistently — {_branding['assistant_name'].lower()} always knows it from now on.",
        "examples": [
            "/remember I take Vyvanse 50mg in the morning",
            "/remember my truck is a 2007 Honda Ridgeline RTL",
        ],
    },
    "/export": {
        "what": f"Saves the full session as a markdown file to {_branding['exports_dir']}/.",
        "examples": ["/export"],
    },
    "/debate": {
        "what": "Runs a multi-model debate on a topic with automatic synthesis. Models argue different perspectives (debate mode) or collaborate toward consensus (consensus mode). Shows agreements, disagreements, and confidence scores.",
        "examples": [
            "/debate 'Should AI development be regulated?'",
            "/debate 'Best approach to microservices architecture' --mode consensus",
            "/debate 'Climate change mitigation strategies' --mode debate",
        ],
    },
    "/expert": {
        "what": "Assembles an expert panel with specialized roles. Each model takes on a domain expertise (electronics, coding, research) to provide targeted analysis from multiple professional perspectives.",
        "examples": [
            "/expert 'Design a low-power IoT sensor'",
            "/expert 'Debug this intermittent hardware issue' --experts electronics",
            "/expert 'Evaluate this research methodology' --experts research,coding",
        ],
    },
    "/synthesize": {
        "what": "Quickly queries the council and synthesizes responses, highlighting points of agreement and disagreement. Faster than /debate for getting a balanced view without full deliberation.",
        "examples": [
            "/synthesize 'What are the tradeoffs of REST vs GraphQL?'",
            "/synthesize 'Explain quantum computing in simple terms'",
        ],
    },
    "/skill": {
        "what": "Loads a skill's full instructions into the conversation. Skills are structured methodologies for coding, debugging, research, and more. Use /skills to see what's available.",
        "examples": [
            "/skill test-driven-development",
            "/skill systematic-debugging",
            "/skill surgical-coding",
            "/skill brainstorming",
        ],
    },
    "/skills": {
        "what": "Lists all available skills with their descriptions. Skills are loaded via /skill <name>.",
        "examples": ["/skills"],
    },
    "/bom": {
        "what": "Bill of Materials (BOM) management tools for hardware projects. Export to CSV/Excel, get pricing from suppliers (DigiKey, Mouser, LCSC), compare revisions, and generate shopping lists.",
        "examples": [
            "/bom export sansui_rev1 --format excel --supplier digikey --pricing",
            "/bom pricing sansui_rev1 --supplier mouser",
            "/bom compare sansui_rev1 sansui_rev2",
            "/bom summary sansui_rev1",
            "/bom shopping sansui_rev1 --supplier digikey --output shopping.csv",
        ],
    },
}


def _greedy_columns(panels, console, padding=(0, 1)):
    """Pack panels into rows using greedy width-fitting algorithm."""
    rows = []
    current_row = []
    current_w = 0
    gap = padding[1] if len(padding) > 1 else 0
    for p in panels:
        w = getattr(p, "width", None)
        if w is None:
            w = console.measure(p).maximum
        needed = w + (gap if current_row else 0)
        if current_row and current_w + needed > console.width:
            rows.append(Columns(current_row, equal=False, padding=padding))
            current_row = [p]
            current_w = w
        else:
            current_row.append(p)
            current_w += needed
    if current_row:
        rows.append(Columns(current_row, equal=False, padding=padding))
    return rows


def print_help(target: str = ""):
    if target:
        key = target.strip().lstrip("/")
        cmd = "/" + key.split()[0] if key != "!!" else "!!"
        details = _CMD_DETAILS.get(cmd)
        entry = COMMANDS.get(cmd)
        if entry:
            usage, desc = entry
            console.print(f"\n[bold green]{usage}[/bold green]")
            console.print(f"  {desc}\n")
            if details:
                console.print(f"  [white]{details['what']}[/white]\n")
                console.print("  [dim]Examples:[/dim]")
                for ex in details["examples"]:
                    console.print(f"    [dim cyan]{ex}[/dim cyan]")
            console.print()
            return
        p_warn(f"Unknown command: {cmd}  — try /help with no arguments")
        return

    # ── Grouped help columns ──────────────────────────────────────────────────
    def _section(title: str, rows: list, color: str = "cyan"):
        cmd_w = max(len(c) for c, d, *_ in rows)
        desc_w = max(len(d) for c, d, *_ in rows)
        t = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
        t.add_column("cmd", style=color, width=cmd_w, no_wrap=True)
        t.add_column("desc", style="white", width=desc_w)
        for cmd, desc, *_ in rows:
            t.add_row(cmd, desc)
        return Panel(
            t,
            title=f"[bold {color}]{title}[/bold {color}]",
            border_style=f"dim {color}",
            padding=(0, 1),
            width=cmd_w + desc_w + 8,
        )

    sections = [
        _section(
            "DAILY USE",
            [
                ("/brief", "Morning context anchor"),
                ("/stuck [context]", "ADHD rescue — next step"),
                ("/capture <thought>", "Quick brain dump"),
                ("/review", "See all captures + facts"),
            ],
            "orange1",
        ),
        _section(
            "WORK MODES",
            [
                ("/bench <anything>", "Set work mode (sansui, etc)"),
                ("/bench off", "Clear active mode"),
                ("/code [path]", "Set project/coding root"),
                ("/code off", "Exit coding mode"),
            ],
            "cyan",
        ),
        _section(
            "HEALTH",
            [
                ("/prep", "Prescriber appointment brief"),
                ("/pattern med-check", "Drug interaction check"),
                ("/pattern clinical", "Rewrite for NP clinical note"),
            ],
            "magenta",
        ),
        _section(
            "CODING",
            [
                ("/code [path]", "Set project/coding root"),
                ("/code off", "Exit coding mode"),
                ("/sansui", "Enter Sansui 9090 repair mode"),
                ("/process-pdf <path>", "Process PDF schematic in parallel"),
            ],
            "green",
        ),
        _section(
            "VISION & REPAIR",
            [
                ("/repair <photo>", "Repair photo analysis"),
                ("/image <photo> [q]", "Ask vision anything"),
                ("/ingest [path]", "Add to kitty library"),
                ("/watch [on|off|30]", "Continuous screen watcher"),
            ],
            "yellow",
        ),
        _section(
            "RESEARCH",
            [
                ("/deepsearch <query>", "Deep web research"),
                ("/debate <topic>", "Multi-model debate + synthesis"),
                ("/expert <topic>", "Specialized expert panel"),
                ("/synthesize <query>", "Quick council consensus"),
                ("/pattern summarize", "Bullet-point summary"),
                ("/pattern obd-explain", "Plain-English OBD data"),
                ("!!", "Escalate to higher model tier"),
            ],
            "blue",
        ),
        _section(
            "MEMORY",
            [
                ("/remember <fact>", "Save a persistent fact"),
                ("/forget <key>", "Remove a saved fact"),
                ("/memories", "List all saved facts"),
                ("/export", "Save session as markdown"),
            ],
            "gold1",
        ),
        _section(
            "SKILLS",
            [
                ("/skills", "List all available skills"),
                ("/skill <name>", "Load a skill's instructions"),
            ],
            "magenta",
        ),
        _section(
            "SYSTEM",
            [
                ("/voice", "Toggle Superwhisper input"),
                ("/status", "Tiers, tools, cost"),
                ("/clear", "Clear session history"),
                ("/help [command]", "This menu"),
            ],
            "white",
        ),
    ]

    for row in _greedy_columns(sections, console):
        console.print(row)

    console.print(
        "\n  [dim]Tab autocompletes commands. Drag any image from Finder — auto-detects repair vs general.[/dim]"
    )
    console.print(
        "  [dim]Type [bold]kitty ref[/bold] for the terminal commands reference.[/dim]\n"
    )


def print_library():
    index = load_library_index()
    if not index:
        p_dim("Library empty. Drop PDFs/EPUBs into ./data/manuals/ — they auto-ingest.")
        return
    t = Table(box=box.SIMPLE, show_header=True, header_style="bold cyan")
    t.add_column("Name", style="white", width=36)
    t.add_column("Type", style="yellow", width=6)
    t.add_column("Size", style="dim", width=12)
    t.add_column("Ingested", style="dim", width=18)
    for e in index.values():
        t.add_row(e["name"], e["type"], f"{e['chars']:,} chars", e["date"])
    console.print(t)
    console.print(f"[dim]{len(index)} document(s)[/dim]")


def run_ingest(path_arg: str):
    args = [sys.executable, "ingest_manuals.py"]
    if path_arg:
        args.append(path_arg)
    p_dim("Ingesting...")
    r = subprocess.run(args, capture_output=False)
    if r.returncode != 0:
        console.print("[red]✗ Ingest failed.[/red]")
    else:
        p_success("Library updated. Use /library to see indexed documents.")


def get_clipboard() -> str:
    try:
        r = subprocess.run(["pbpaste"], capture_output=True, text=True)
        return r.stdout.strip()
    except Exception:
        return ""


# ── Main loop ──────────────────────────────────────────────────────────────────
