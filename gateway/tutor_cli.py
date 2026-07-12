"""CLI for Kitty Tutor — invoked by `kitty tutor ...`.

Three commands, no flags to remember:
  kitty tutor learn <path>        ingest a doc (pdf/md/txt)
  kitty tutor ask "<question>"   vocab-first answer + one check-in question
  kitty tutor review              show terms you struggled with, due now
  kitty tutor rate "<term>" <1-3> log how well you got it (drives review)
"""

from __future__ import annotations

import argparse
import asyncio
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="kitty tutor", description="Kitty Tutor — learn from your own docs"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    learn = sub.add_parser("learn", help="ingest a document")
    learn.add_argument("path", help="path to a pdf / markdown / text file")

    ask = sub.add_parser("ask", help="ask a learning question")
    ask.add_argument("topic", help="the concept or question")

    sub.add_parser("review", help="list terms due for review")

    rate = sub.add_parser("rate", help="log your confidence on a term")
    rate.add_argument("term", help="the vocab term")
    rate.add_argument("score", type=int, choices=[1, 2, 3], help="1 got it, 2 need example, 3 lost")

    args = parser.parse_args(argv)

    from gateway import tutor

    if args.cmd == "learn":
        asyncio.run(tutor.ingest(args.path))
        print(f"Ingested {args.path}. Ask away: kitty tutor ask \"<your question>\"")
        return 0

    if args.cmd == "ask":
        try:
            ans = asyncio.run(tutor.ask(args.topic))
        except tutor.TutorError as exc:
            print(str(exc))
            return 0
        except Exception as exc:  # surface the cause, not a raw traceback
            print(f"Tutor hit a problem: {exc}")
            print("Is the gateway up? Try: kitty up")
            return 1
        print(f"Vocab: {', '.join(ans['vocab'])}")
        print(f"\n{ans['explain']}")
        print(f"\nCheck-in: {ans['question']}")
        print('\nRate it:  kitty tutor rate "<term>" <1-3>')
        return 0

    if args.cmd == "review":
        due = tutor.due_review()
        if not due:
            print("Nothing due for review. You're clear.")
            return 0
        print(f"{len(due)} term(s) queued for review:")
        for d in due:
            print(f"  - {d['term']}  (last score {d['last_score']})")
        return 0

    if args.cmd == "rate":
        tutor.log_confidence(args.term, args.score)
        print(f"Logged {args.score} for '{args.term}'.")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
