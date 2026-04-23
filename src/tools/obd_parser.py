"""OBD Fusion CSV log parser for kitty automotive expert."""

import csv
from datetime import datetime
from pathlib import Path

RIDGELINE_VIN = "2HJYK16437H005059"
OBD_APP_PATH = Path.home() / "Library/Mobile Documents/iCloud~net~obdsoftware~obdfusion/Documents/CsvLogs"
ICLOUD_PATH = Path.home() / "Library/Mobile Documents/com~apple~CloudDocs/Automotive"

# Columns we care about for diagnostics
KEY_COLS = {
    "Time (sec)": "time",
    "Engine RPM (RPM)": "rpm",
    "Engine coolant temperature (°C)": "coolant_c",
    "Intake manifold absolute pressure (kPa)": "map_kpa",
    "Short term fuel % trim - Bank 1 (%)": "stft_b1",
    "Long term fuel % trim - Bank 1 (%)": "ltft_b1",
    "Short term fuel % trim - Bank 2 (%)": "stft_b2",
    "Long term fuel % trim - Bank 2 (%)": "ltft_b2",
    "Vehicle speed (km/h)": "speed",
    "Throttle position (%)": "throttle",
    "O2 voltage (Bank 1  Sensor 2) (V)": "o2_b1s2",
    "O2 voltage (Bank 2  Sensor 2) (V)": "o2_b2s2",
}


def _parse_timestamp(filename: str) -> datetime | None:
    """Extract datetime from CSVLog_YYYYMMDD_HHMMSS.csv"""
    stem = Path(filename).stem
    parts = stem.split("_")
    if len(parts) >= 3:
        try:
            return datetime.strptime(f"{parts[1]}_{parts[2]}", "%Y%m%d_%H%M%S")
        except ValueError:
            pass
    return None


def _read_csv(path: Path, sample_every: int = 1) -> list[dict]:
    """Read a single OBD CSV, returning rows with mapped key names.
    sample_every > 1 skips rows for fast trend analysis."""
    rows = []
    try:
        with open(path, encoding="utf-8-sig") as f:
            lines = f.readlines()
        # Strip comment header lines starting with #
        data_lines = [line for line in lines if not line.startswith("#")]
        reader = csv.DictReader(data_lines)
        # Map raw fieldname (may have leading spaces) -> short key
        col_map = {}  # raw_header -> short_name
        for raw_h in (reader.fieldnames or []):
            stripped = raw_h.strip()
            if stripped in KEY_COLS:
                col_map[raw_h] = KEY_COLS[stripped]
        for i, row in enumerate(reader):
            if sample_every > 1 and i % sample_every != 0:
                continue
            mapped = {}
            for raw_h, short in col_map.items():
                val = row.get(raw_h, "").strip()
                try:
                    mapped[short] = float(val) if val else None
                except ValueError:
                    mapped[short] = None
            if mapped.get("rpm") and mapped["rpm"] > 0:
                rows.append(mapped)
    except Exception:
        pass
    return rows


def list_logs(vin: str = RIDGELINE_VIN, limit: int = 10) -> list[dict]:
    """Return metadata for the most recent OBD logs for a VIN."""
    vin_path = OBD_APP_PATH / vin
    results = []
    if vin_path.exists():
        for f in sorted(vin_path.glob("*.csv"), reverse=True)[:limit]:
            ts = _parse_timestamp(f.name)
            results.append({
                "file": f.name,
                "path": str(f),
                "date": ts.strftime("%Y-%m-%d %H:%M") if ts else "unknown",
                "size_kb": round(f.stat().st_size / 1024, 1),
            })
    # Also check iCloud folder
    if ICLOUD_PATH.exists():
        for f in sorted(ICLOUD_PATH.glob("CSVLog_*.csv"), reverse=True)[:5]:
            ts = _parse_timestamp(f.name)
            results.append({
                "file": f.name,
                "path": str(f),
                "date": ts.strftime("%Y-%m-%d %H:%M") if ts else "unknown",
                "size_kb": round(f.stat().st_size / 1024, 1),
            })
    return results[:limit]


def analyze_log(path: str, fast: bool = False) -> dict:
    """
    Parse a CSV log and return a diagnostic summary.
    Returns LTFT/STFT averages at idle vs cruise, coolant stats, etc.
    fast=True samples every 5th row for trend analysis.
    """
    rows = _read_csv(Path(path), sample_every=5 if fast else 1)
    if not rows:
        return {"error": f"No data rows found in {path}"}

    idle = [r for r in rows if r.get("rpm") and 400 < r["rpm"] < 900 and r.get("speed", 0) == 0]
    cruise = [r for r in rows if r.get("rpm") and r["rpm"] > 1200 and r.get("speed", 0) and r["speed"] > 20]

    def avg(lst, key):
        vals = [r[key] for r in lst if r.get(key) is not None]
        return round(sum(vals) / len(vals), 2) if vals else None

    def mx(lst, key):
        vals = [r[key] for r in lst if r.get(key) is not None]
        return round(max(vals), 1) if vals else None

    ts = _parse_timestamp(path)
    summary = {
        "file": Path(path).name,
        "date": ts.strftime("%Y-%m-%d %H:%M") if ts else "unknown",
        "total_rows": len(rows),
        "idle_rows": len(idle),
        "cruise_rows": len(cruise),
        "idle": {
            "ltft_b1": avg(idle, "ltft_b1"),
            "ltft_b2": avg(idle, "ltft_b2"),
            "stft_b1": avg(idle, "stft_b1"),
            "stft_b2": avg(idle, "stft_b2"),
            "map_kpa": avg(idle, "map_kpa"),
            "rpm": avg(idle, "rpm"),
        },
        "cruise": {
            "ltft_b1": avg(cruise, "ltft_b1"),
            "ltft_b2": avg(cruise, "ltft_b2"),
            "stft_b1": avg(cruise, "stft_b1"),
            "stft_b2": avg(cruise, "stft_b2"),
        },
        "max_coolant_c": mx(rows, "coolant_c"),
        "notes": [],
    }

    # Diagnostic flags
    lb1 = summary["idle"]["ltft_b1"]
    lb2 = summary["idle"]["ltft_b2"]
    summary["idle"]["stft_b1"]
    sb2 = summary["idle"]["stft_b2"]

    if lb2 is not None and lb2 > 5:
        summary["notes"].append(f"WARN: Bank 2 LTFT at idle is {lb2}% (lean — typical >5% = concern)")
    if lb2 is not None and lb2 > 3:
        summary["notes"].append(f"INFO: Bank 2 LTFT {lb2}% — consistent with known exhaust leak / gasket issue")
    if lb1 is not None and abs(lb1 - (lb2 or 0)) > 3:
        summary["notes"].append(f"Bank imbalance: B1={lb1}% vs B2={lb2}% — {abs(lb1-(lb2 or 0)):.1f}% delta")
    if sb2 is not None and sb2 > 7:
        summary["notes"].append(f"WARN: Bank 2 STFT {sb2}% — active lean correction at idle")

    return summary


def analyze_latest(vin: str = RIDGELINE_VIN) -> dict:
    """Analyze the most recent log for a VIN."""
    logs = list_logs(vin, limit=1)
    if not logs:
        return {"error": f"No logs found for VIN {vin}"}
    return analyze_log(logs[0]["path"])


def analyze_range(vin: str = RIDGELINE_VIN, last_n: int = 5) -> list[dict]:
    """Analyze last N logs and return trend data (fast sampled mode)."""
    logs = list_logs(vin, limit=last_n)
    return [analyze_log(log_entry["path"], fast=True) for log_entry in logs]


def trend_summary(vin: str = RIDGELINE_VIN, last_n: int = 10) -> str:
    """Return a human-readable trend report for LTFT Bank 2."""
    analyses = analyze_range(vin, last_n)
    lines = ["OBD Fuel Trim Trend — Bank 2 (Ridgeline)", "=" * 45]
    for a in analyses:
        if "error" in a:
            continue
        ltft2 = a["idle"].get("ltft_b2")
        stft2 = a["idle"].get("stft_b2")
        date = a["date"]
        flag = " ⚠" if ltft2 and ltft2 > 5 else ""
        lines.append(f"{date}  LTFT B2: {ltft2:+.1f}%  STFT B2: {stft2:+.1f}%{flag}" if ltft2 is not None else f"{date}  (no idle data)")
    return "\n".join(lines)


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "list":
            print(json.dumps(list_logs(), indent=2))
        elif cmd == "latest":
            print(json.dumps(analyze_latest(), indent=2))
        elif cmd == "trend":
            print(trend_summary())
        elif cmd == "analyze" and len(sys.argv) > 2:
            print(json.dumps(analyze_log(sys.argv[2]), indent=2))
        else:
            print("Usage: obd_parser.py [list|latest|trend|analyze <path>]")
    else:
        print(trend_summary())
