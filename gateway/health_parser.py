"""Apple Health XML parser — extract key metrics from export.xml.

Apple Health exports are single XML files (often 500MB+). This parser
extracts only the metrics we care about: sleep, resting heart rate, weight,
steps, HRV, and workouts — aggregated into weekly summaries.

Public API:
  parse_export(xml_path) -> list[dict]   Parse health export XML
  get_weekly_summary() -> dict           Latest week summary
  ingest_to_knowledge(xml_path) -> int   Parse and ingest into ChromaDB
"""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from gateway.paths import DATA_DIR

logger = logging.getLogger("kitty.health_parser")

HEALTH_CACHE = DATA_DIR / "health_weekly.json"

METRICS_OF_INTEREST = {
    "HKCategoryTypeIdentifierSleepAnalysis": "sleep",
    "HKQuantityTypeIdentifierHeartRate": "heart_rate",
    "HKQuantityTypeIdentifierRestingHeartRate": "resting_heart_rate",
    "HKQuantityTypeIdentifierBodyMass": "weight",
    "HKQuantityTypeIdentifierStepCount": "steps",
    "HKQuantityTypeIdentifierHeartRateVariabilitySDNN": "hrv",
    "HKQuantityTypeIdentifierActiveEnergyBurned": "active_energy",
    "HKQuantityTypeIdentifierDistanceWalkingRunning": "distance_walking",
    "HKWorkoutTypeIdentifier": "workout",
}


def parse_export(xml_path: str | Path) -> list[dict]:
    """Parse an Apple Health export.xml file. Returns list of metric records."""
    path = Path(xml_path)
    if not path.exists():
        logger.error("Health export not found: %s", path)
        return []

    logger.info("Parsing health export: %s (%.1f MB)", path.name, path.stat().st_size / 1e6)

    records: list[dict] = []
    try:
        context = ET.iterparse(str(path), events=("end",))
        for event, elem in context:
            if elem.tag == "Record":
                rec_type = elem.get("type", "")
                if rec_type in METRICS_OF_INTEREST:
                    try:
                        value = float(elem.get("value", 0))
                    except (ValueError, TypeError):
                        value = 0

                    records.append({
                        "metric": METRICS_OF_INTEREST.get(rec_type, rec_type),
                        "value": value,
                        "unit": elem.get("unit", ""),
                        "date": elem.get("startDate", ""),
                        "source": (elem.get("sourceName") or "")[:100],
                    })
                elem.clear()

            elif elem.tag == "Workout":
                records.append({
                    "metric": "workout",
                    "type": elem.get("workoutActivityType", ""),
                    "duration": float(elem.get("duration", 0) or 0),
                    "energy": float(elem.get("totalEnergyBurned", 0) or 0),
                    "distance": float(elem.get("totalDistance", 0) or 0),
                    "date": elem.get("startDate", ""),
                    "source": (elem.get("sourceName") or "")[:100],
                })
                elem.clear()

        logger.info("Parsed %d health records", len(records))
    except Exception as e:
        logger.error("Health XML parse failed: %s", e)
        return []

    return records


def get_weekly_summary(records: Optional[list[dict]] = None) -> dict:
    """Aggregate records into a weekly summary."""
    if records is None:
        try:
            import json
            if HEALTH_CACHE.exists():
                return json.loads(HEALTH_CACHE.read_text())
        except Exception:
            pass
        return {}

    now = datetime.now()
    week_ago = now - timedelta(days=7)

    summary: dict[str, Any] = {
        "period": f"{week_ago.date()} to {now.date()}",
        "generated_at": now.isoformat(),
        "sleep": {"avg_hours": 0, "count": 0},
        "resting_heart_rate": {"avg": 0, "count": 0},
        "weight": {"latest": None, "unit": "kg"},
        "steps": {"total": 0, "avg_daily": 0},
        "workouts": [],
        "hrv": {"avg": 0, "count": 0},
    }

    for r in records:
        try:
            rdate = datetime.fromisoformat(r.get("date", "").replace("Z", "+00:00").replace(" +", "+"))
        except (ValueError, TypeError):
            rdate = datetime.min

        if rdate.replace(tzinfo=None) < week_ago:
            continue

        metric = r.get("metric", "")
        value = r.get("value", 0)

        if metric == "sleep" and value > 0:
            summary["sleep"]["avg_hours"] += value
            summary["sleep"]["count"] += 1
        elif metric == "resting_heart_rate" and value > 0:
            summary["resting_heart_rate"]["avg"] += value
            summary["resting_heart_rate"]["count"] += 1
        elif metric == "weight" and value > 0:
            summary["weight"]["latest"] = value
        elif metric == "steps":
            summary["steps"]["total"] += int(value)
        elif metric == "hrv" and value > 0:
            summary["hrv"]["avg"] += value
            summary["hrv"]["count"] += 1
        elif metric == "workout":
            summary["workouts"].append({
                "type": r.get("type", ""),
                "duration_min": round(r.get("duration", 0) or 0, 1),
                "date": r.get("date", ""),
            })

    # Compute averages
    if summary["sleep"]["count"]:
        summary["sleep"]["avg_hours"] = round(summary["sleep"]["avg_hours"] / summary["sleep"]["count"], 1)
    if summary["resting_heart_rate"]["count"]:
        summary["resting_heart_rate"]["avg"] = round(summary["resting_heart_rate"]["avg"] / summary["resting_heart_rate"]["count"], 1)
    if summary["hrv"]["count"]:
        summary["hrv"]["avg"] = round(summary["hrv"]["avg"] / summary["hrv"]["count"], 1)
    summary["steps"]["avg_daily"] = round(summary["steps"]["total"] / 7)

    # Cache
    import json
    HEALTH_CACHE.parent.mkdir(parents=True, exist_ok=True)
    HEALTH_CACHE.write_text(json.dumps(summary, indent=2, default=str))

    return summary


def ingest_to_knowledge(xml_path: str | Path) -> int:
    """Parse health export and ingest the weekly summary into the knowledge base."""
    records = parse_export(xml_path)
    if not records:
        return 0

    summary = get_weekly_summary(records)
    text = _format_summary_for_ingestion(summary)

    try:
        import asyncio
        import tempfile

        from gateway.knowledge import ingest
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(text)
            tmp_path = f.name
        result = asyncio.run(ingest(tmp_path, sensitivity="medical", source_label="apple_health_weekly"))
        Path(tmp_path).unlink(missing_ok=True)
        return result.chunks_count
    except Exception as e:
        logger.error("Health ingestion failed: %s", e)
        return 0


def get_health_text() -> str:
    """Return a brief health summary for context injection. Empty if no data."""
    summary = get_weekly_summary()
    if not summary:
        return ""
    return _format_summary_for_ingestion(summary)


def _format_summary_for_ingestion(summary: dict) -> str:
    lines = [f"Apple Health Weekly Summary: {summary.get('period', '')}"]
    sleep = summary.get("sleep", {})
    if sleep.get("count"):
        lines.append(f"Sleep: avg {sleep['avg_hours']}h/night ({sleep['count']} nights)")
    hr = summary.get("resting_heart_rate", {})
    if hr.get("count"):
        lines.append(f"Resting HR: avg {hr['avg']} bpm")
    weight = summary.get("weight", {})
    if weight.get("latest"):
        lines.append(f"Weight: {weight['latest']} {weight.get('unit', 'kg')}")
    steps = summary.get("steps", {})
    lines.append(f"Steps: {steps.get('total', 0)} total, {steps.get('avg_daily', 0)}/day")
    workouts = summary.get("workouts", [])
    if workouts:
        lines.append(f"Workouts: {len(workouts)} this week")
        for w in workouts[:5]:
            lines.append(f"  - {w.get('type', '')}: {w.get('duration_min', 0)}min")
    return "\n".join(lines)
