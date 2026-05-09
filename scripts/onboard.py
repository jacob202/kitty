#!/usr/bin/env python3
"""Kitty onboarding interview — run this once to let Kitty know you.

Usage:
    python scripts/onboard.py              # resume from where you left off
    python scripts/onboard.py --domain identity   # run one specific domain
    python scripts/onboard.py --reset      # clear all state and restart
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from gateway.onboarding import DOMAINS, load_state, save_state, store_answer

SEPARATOR = "─" * 60


def run_domain(domain_key: str, domain_config: dict, state: dict) -> None:
    title = domain_config["title"]
    sensitivity = domain_config["sensitivity"]
    questions = domain_config["questions"]

    print(f"\n{SEPARATOR}")
    print(f"  {title}")
    if sensitivity in ("medical", "financial"):
        print(f"  ⚠  Sensitive domain — answers stay on-device only")
    print(f"{SEPARATOR}\n")

    all_answers = []
    for i, question in enumerate(questions, 1):
        print(f"[{i}/{len(questions)}] {question}")
        print("  (Press Enter twice to skip, type your answer and press Enter when done)")
        try:
            answer = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nInterrupted. Progress saved.")
            return

        if not answer:
            print("  → Skipped.\n")
            continue

        print("  → Storing...", end=" ", flush=True)
        n = store_answer(domain_key, question, answer, sensitivity)
        print(f"stored {n} facts.\n")
        all_answers.append((question, answer))

    state[domain_key] = True
    save_state(state)
    print(f"\n✓ {title} complete — {len(all_answers)} answers stored.\n")


def main():
    parser = argparse.ArgumentParser(description="Kitty onboarding interview")
    parser.add_argument("--domain", choices=list(DOMAINS.keys()), help="Run a specific domain only")
    parser.add_argument("--reset", action="store_true", help="Clear all state and restart")
    parser.add_argument("--status", action="store_true", help="Show which domains are done")
    args = parser.parse_args()

    state = load_state()

    if args.reset:
        state = {d: False for d in DOMAINS}
        save_state(state)
        print("State reset. All domains marked incomplete.")
        return

    if args.status:
        print("\nOnboarding status:")
        for domain, config in DOMAINS.items():
            mark = "✓" if state.get(domain) else "○"
            print(f"  {mark} {config['title']}")
        return

    print("\nKitty Onboarding Interview")
    print("This helps Kitty know you so she can actually be useful.")
    print("Type your answers naturally. She'll extract what matters.\n")

    if args.domain:
        run_domain(args.domain, DOMAINS[args.domain], state)
        print(f"\nDone. Run 'python scripts/onboard.py --status' to see all domains.")
        return

    pending = [d for d in DOMAINS if not state.get(d)]
    if not pending:
        print("All domains complete! Run with --reset to start over.")
        return

    done = len(DOMAINS) - len(pending)
    print(f"Progress: {done}/{len(DOMAINS)} domains complete. Resuming from next pending domain.\n")

    for domain_key in pending:
        run_domain(domain_key, DOMAINS[domain_key], state)
        cont = input("Continue to next domain? [Y/n] ").strip().lower()
        if cont == "n":
            print(f"\nPaused. Run 'python scripts/onboard.py' to resume.")
            break

    remaining = [d for d in DOMAINS if not state.get(d)]
    if not remaining:
        print("\n🎉 Onboarding complete! Kitty now knows you.\n")
        print("Try asking: 'What do you know about me?'")


if __name__ == "__main__":
    main()
