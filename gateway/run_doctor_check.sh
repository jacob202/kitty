#!/bin/bash
set -euo pipefail

ROOT_DIR="/Users/jacobbrizinski/Projects/kitty"
LOG_DIR="${ROOT_DIR}/logs/kitty_gateway"
CHECKS_LOG="${LOG_DIR}/doctor_checks.jsonl"
ALERT_LOG="${LOG_DIR}/doctor_alerts.log"
RUN_DIR="${ROOT_DIR}/kitty_gateway/.run"
FLAG_FILE="${RUN_DIR}/doctor_degraded"

mkdir -p "${LOG_DIR}" "${RUN_DIR}"
cd "${ROOT_DIR}"

json_out="$(bash gateway/doctor.sh --json 2>/dev/null || true)"
if [[ -z "${json_out}" ]]; then
  ts="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo "{\"ts\":\"${ts}\",\"status\":\"error\",\"reason\":\"doctor produced no json\"}" >> "${CHECKS_LOG}"
  echo "[${ts}] ALERT doctor failed: no output" >> "${ALERT_LOG}"
  touch "${FLAG_FILE}"
  exit 1
fi

tmp_json="$(mktemp)"
printf "%s" "${json_out}" > "${tmp_json}"

python3 - <<'PY' "${tmp_json}" "${CHECKS_LOG}" "${ALERT_LOG}" "${FLAG_FILE}" "${DOCTOR_ALERT_ON_WARN:-0}"
import datetime as dt
import json
import pathlib
import sys

src = pathlib.Path(sys.argv[1])
checks_log = pathlib.Path(sys.argv[2])
alert_log = pathlib.Path(sys.argv[3])
flag_file = pathlib.Path(sys.argv[4])
alert_on_warn = str(sys.argv[5]).strip() == "1"

ts = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

try:
    payload = json.loads(src.read_text(encoding="utf-8"))
except Exception as exc:
    checks_log.parent.mkdir(parents=True, exist_ok=True)
    with checks_log.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": ts, "status": "error", "reason": f"json parse failed: {exc}"}) + "\n")
    with alert_log.open("a", encoding="utf-8") as f:
        f.write(f"[{ts}] ALERT doctor json parse failed: {exc}\n")
    flag_file.touch(exist_ok=True)
    raise SystemExit(1)

summary = payload.get("summary", {}) if isinstance(payload, dict) else {}
warn = int(summary.get("warn", 0))
fail = int(summary.get("fail", 0))
degraded = (warn > 0) or (fail > 0)
alert = (fail > 0) or (alert_on_warn and warn > 0)

entry = {"ts": ts, "status": "degraded" if degraded else "ok", "summary": summary}
checks_log.parent.mkdir(parents=True, exist_ok=True)
with checks_log.open("a", encoding="utf-8") as f:
    f.write(json.dumps(entry) + "\n")

if alert:
    with alert_log.open("a", encoding="utf-8") as f:
        f.write(f"[{ts}] ALERT doctor degraded: warn={warn} fail={fail}\n")
    flag_file.touch(exist_ok=True)
    raise SystemExit(1)

if flag_file.exists():
    flag_file.unlink()
PY

rm -f "${tmp_json}"
echo "Doctor check complete."
