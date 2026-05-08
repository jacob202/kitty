#!/opt/homebrew/bin/python3.12
"""Generate a daily reliability summary from eval artifacts."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path
from statistics import mean
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_DIR = ROOT / "evals" / "artifacts"
SUMMARY_DIR = ROOT / "evals" / "summaries"


def _to_epoch_seconds(value: Any, fallback: float) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return fallback
        try:
            return datetime.strptime(text, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC).timestamp()
        except ValueError:
            pass
        try:
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            return datetime.fromisoformat(text).timestamp()
        except ValueError:
            return fallback
    return fallback


def _load_artifact(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def _artifact_day(data: dict[str, Any], path: Path) -> date:
    started = data.get("started_at")
    epoch = _to_epoch_seconds(started, fallback=path.stat().st_mtime)
    return datetime.fromtimestamp(epoch, tz=UTC).date()


def summarize_day(
    *,
    artifact_dir: Path,
    summary_date: date,
) -> dict[str, Any]:
    smoke_rates: list[float] = []
    smoke_passed_total = 0
    smoke_checks_total = 0

    daily_rates: list[float] = []
    daily_passed_total = 0
    daily_checks_total = 0
    daily_fail_counts: Counter[str] = Counter()
    browser_rates: list[float] = []
    browser_passed_total = 0
    browser_checks_total = 0
    browser_fail_counts: Counter[str] = Counter()

    scanned = 0
    matched = 0
    parse_errors = 0

    for path in sorted(Path(artifact_dir).glob("*.json")):
        scanned += 1
        data = _load_artifact(path)
        if data is None:
            parse_errors += 1
            continue
        if _artifact_day(data, path) != summary_date:
            continue
        matched += 1

        suite = str(data.get("suite") or "")
        scores = data.get("scores") or {}

        if suite == "smoke":
            smoke = (scores.get("smoke") or {}) if isinstance(scores, dict) else {}
            rate = smoke.get("rate")
            passed = smoke.get("passed")
            total = smoke.get("total")
            if isinstance(rate, (int, float)):
                smoke_rates.append(float(rate))
            if isinstance(passed, int):
                smoke_passed_total += passed
            if isinstance(total, int):
                smoke_checks_total += total
            continue

        if suite == "daily_flow":
            flow = (scores.get("daily_flow") or {}) if isinstance(scores, dict) else {}
            rate = flow.get("rate")
            passed = flow.get("passed")
            total = flow.get("total")
            if isinstance(rate, (int, float)):
                daily_rates.append(float(rate))
            if isinstance(passed, int):
                daily_passed_total += passed
            if isinstance(total, int):
                daily_checks_total += total

            checks = data.get("checks")
            if isinstance(checks, list):
                for check in checks:
                    if not isinstance(check, dict):
                        continue
                    if check.get("passed") is True:
                        continue
                    name = str(check.get("name") or "unknown_check")
                    daily_fail_counts[name] += 1
            continue

        if suite == "browser_flow":
            browser = (scores.get("browser_flow") or {}) if isinstance(scores, dict) else {}
            rate = browser.get("rate")
            passed = browser.get("passed")
            total = browser.get("total")
            if isinstance(rate, (int, float)):
                browser_rates.append(float(rate))
            if isinstance(passed, int):
                browser_passed_total += passed
            if isinstance(total, int):
                browser_checks_total += total

            checks = data.get("checks")
            if isinstance(checks, list):
                for check in checks:
                    if not isinstance(check, dict):
                        continue
                    if check.get("passed") is True:
                        continue
                    name = str(check.get("name") or "unknown_check")
                    browser_fail_counts[name] += 1

    summary: dict[str, Any] = {
        "date": summary_date.isoformat(),
        "generated_at": datetime.now(UTC).isoformat(),
        "artifact_dir": str(Path(artifact_dir).resolve()),
        "scanned_artifacts": scanned,
        "matched_artifacts": matched,
        "parse_errors": parse_errors,
        "smoke": {
            "runs": len(smoke_rates),
            "avg_rate": round(mean(smoke_rates), 4) if smoke_rates else None,
            "aggregated_rate": round(smoke_passed_total / smoke_checks_total, 4) if smoke_checks_total else None,
            "passed": smoke_passed_total,
            "total": smoke_checks_total,
        },
        "daily_flow": {
            "runs": len(daily_rates),
            "avg_rate": round(mean(daily_rates), 4) if daily_rates else None,
            "aggregated_rate": round(daily_passed_total / daily_checks_total, 4) if daily_checks_total else None,
            "passed": daily_passed_total,
            "total": daily_checks_total,
            "failing_checks": [
                {"name": name, "failures": count}
                for name, count in sorted(daily_fail_counts.items(), key=lambda item: (-item[1], item[0]))
            ],
        },
        "browser_flow": {
            "runs": len(browser_rates),
            "avg_rate": round(mean(browser_rates), 4) if browser_rates else None,
            "aggregated_rate": round(browser_passed_total / browser_checks_total, 4) if browser_checks_total else None,
            "passed": browser_passed_total,
            "total": browser_checks_total,
            "failing_checks": [
                {"name": name, "failures": count}
                for name, count in sorted(browser_fail_counts.items(), key=lambda item: (-item[1], item[0]))
            ],
        },
    }
    return summary


def _render_markdown(summary: dict[str, Any]) -> str:
    smoke = summary["smoke"]
    flow = summary["daily_flow"]
    browser = summary["browser_flow"]
    lines = [
        f"# Daily Eval Summary - {summary['date']}",
        "",
        f"Generated at: {summary['generated_at']}",
        f"Artifacts scanned: {summary['scanned_artifacts']} (matched day: {summary['matched_artifacts']}, parse errors: {summary['parse_errors']})",
        "",
        "## Smoke Suite",
        f"- Runs: {smoke['runs']}",
        f"- Avg rate: {smoke['avg_rate']}",
        f"- Aggregated pass rate: {smoke['aggregated_rate']} ({smoke['passed']}/{smoke['total']})",
        "",
        "## Daily Flow",
        f"- Runs: {flow['runs']}",
        f"- Avg rate: {flow['avg_rate']}",
        f"- Aggregated pass rate: {flow['aggregated_rate']} ({flow['passed']}/{flow['total']})",
        "",
        "## Browser Flow",
        f"- Runs: {browser['runs']}",
        f"- Avg rate: {browser['avg_rate']}",
        f"- Aggregated pass rate: {browser['aggregated_rate']} ({browser['passed']}/{browser['total']})",
        "",
        "## Daily Flow Failing Checks",
    ]
    failing_daily = flow.get("failing_checks") or []
    if not failing_daily:
        lines.append("- none")
    else:
        for row in failing_daily:
            lines.append(f"- {row['name']}: {row['failures']}")

    lines.append("")
    lines.append("## Browser Flow Failing Checks")
    failing_browser = browser.get("failing_checks") or []
    if not failing_browser:
        lines.append("- none")
    else:
        for row in failing_browser:
            lines.append(f"- {row['name']}: {row['failures']}")
    lines.append("")
    return "\n".join(lines)


def write_summary(
    summary: dict[str, Any],
    *,
    output_dir: Path,
) -> tuple[Path, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    date_str = summary["date"]
    json_path = output_dir / f"daily_eval_summary_{date_str}.json"
    md_path = output_dir / f"daily_eval_summary_{date_str}.md"
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(summary), encoding="utf-8")
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a daily eval reliability summary.")
    parser.add_argument("--artifact-dir", default=str(ARTIFACT_DIR), help="Directory containing eval artifacts")
    parser.add_argument("--summary-dir", default=str(SUMMARY_DIR), help="Directory to write summary outputs")
    parser.add_argument(
        "--date",
        default=datetime.now(UTC).date().isoformat(),
        help="UTC date to summarize (YYYY-MM-DD). Defaults to today.",
    )
    args = parser.parse_args(argv)

    try:
        summary_date = date.fromisoformat(args.date)
    except ValueError:
        raise SystemExit(f"Invalid --date value: {args.date}. Expected YYYY-MM-DD.")

    summary = summarize_day(artifact_dir=Path(args.artifact_dir), summary_date=summary_date)
    json_path, md_path = write_summary(summary, output_dir=Path(args.summary_dir))
    print(f"Summary date: {summary['date']}")
    print(f"JSON: {json_path}")
    print(f"Markdown: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
