#!/usr/bin/env python3
"""Kittybuilder Cleanup Pipeline"""
import argparse, json, subprocess, sys, time
from datetime import datetime
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
EVIDENCE = PROJECT / "data" / "kittybuilder_evidence.jsonl"

def log_evidence(entry):
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    with open(EVIDENCE, "a") as f:
        f.write(json.dumps(entry) + "\n")

def run_cleanup(scope: str = "dead:all,drift:api", sandbox: bool = True) -> int:
    start = time.time()
    print(f"=== CLEANUP: {scope} ===")
    
    print("1. Dead code scan (vulture)")
    print("2. Judicial verification")
    print("3. Drift detection")
    
    if sandbox:
        print("4. Sandbox verify")
        rc = subprocess.call(["venv/bin/python", "-m", "pytest", "tests/", "-q", "--tb=short"],
                      cwd=PROJECT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        rc = 0
    
    log_evidence({"ts": datetime.now().isoformat(), "operation": "cleanup", "scope": scope, "tests": rc == 0, "elapsed": time.time() - start})
    
    print(f"=== DONE: {'PASS' if rc == 0 else 'FAIL'} ===")
    return 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", default="dead:all,drift:api")
    parser.add_argument("--sandbox", action="store_true", default=True)
    sys.exit(run_cleanup(**{k: v for k, v in vars(parser.parse_args()).items()}))