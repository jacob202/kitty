#!/usr/bin/env python3
import subprocess
import sys
import time
from pathlib import Path

TASK = "Create a new file 'src/utils/math_helper.py' with a function 'add(a, b)'. Then create a test 'tests/test_math_helper.py' that verifies 1+1=2 using pytest. Finally, run the test and confirm it passes."

def run_once(i):
    print(f"\n--- STRESS TEST RUN #{i} ---")
    start = time.time()
    # We use a 5-minute timeout per run
    proc = subprocess.run(
        ["python3", "scripts/overnight_retry.py", TASK],
        capture_output=True,
        text=True,
        timeout=300
    )
    end = time.time()
    
    success = proc.returncode == 0
    duration = end - start
    
    print(f"Result: {'✅ SUCCESS' if success else '❌ FAILURE'}")
    print(f"Duration: {duration:.1f}s")
    
    if not success:
        print("\n--- ERROR LOG (Tail) ---")
        print(proc.stdout[-1000:])
        print(proc.stderr[-1000:])
    
    return success

def main():
    runs = 3
    successes = 0
    for i in range(1, runs + 1):
        if run_once(i):
            successes += 1
    
    print(f"\n=== FINAL SCORE: {successes}/{runs} ({successes/runs*100:.0f}%) ===")

if __name__ == "__main__":
    main()
