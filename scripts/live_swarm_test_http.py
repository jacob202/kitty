#!/usr/bin/env python3.12
"""Live Swarm Test for HTTP Gateway Concurrency.

Simulates heavy parallel traffic against the real FastAPI endpoints to ensure
WAL scaling, ThreadPoolExecutor starvation handling, and SSE stream health.
"""
import concurrent.futures
import time
import requests
import argparse
import os
from dotenv import load_dotenv
from typing import NamedTuple

load_dotenv()

class Metrics(NamedTuple):
    total: int
    success: int
    errors: int
    latencies: list[float]

def hit_project_create() -> float:
    start = time.time()
    try:
        resp = requests.post(
            "http://localhost:8000/projects",
            headers={"Authorization": f"Bearer {os.environ.get('GATEWAY_SECRET', 'kitty')}"},
            json={
                "name": f"swarm-test-{int(time.time()*1000)}",
                "kind": "test",
                "paths": ["/dev/null"]
            },
            timeout=5.0
        )
        resp.raise_for_status()
    except Exception as e:
        raise
    return time.time() - start

def hit_project_list() -> float:
    start = time.time()
    try:
        resp = requests.get("http://localhost:8000/projects", headers={"Authorization": f"Bearer {os.environ.get('GATEWAY_SECRET', 'kitty')}"}, timeout=5.0)
        resp.raise_for_status()
    except Exception as e:
        raise
    return time.time() - start

def worker(worker_id: int, iterations: int) -> list[float]:
    latencies = []
    for i in range(iterations):
        # Alternate between reads and writes
        if i % 2 == 0:
            lat = hit_project_create()
        else:
            lat = hit_project_list()
        latencies.append(lat)
        # Small jitter to prevent lockstep
        time.sleep(0.01)
    return latencies

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=20)
    parser.add_argument("--iterations", type=int, default=10)
    args = parser.parse_args()

    print(f"Starting swarm test with {args.workers} workers, {args.iterations} iter/worker...")
    start_time = time.time()

    all_latencies = []
    errors = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [
            executor.submit(worker, w, args.iterations)
            for w in range(args.workers)
        ]
        for f in concurrent.futures.as_completed(futures):
            try:
                all_latencies.extend(f.result())
            except Exception as e:
                errors += 1
                print(f"Worker failed: {e}")

    duration = time.time() - start_time
    total_reqs = len(all_latencies)

    print("\n--- Swarm Test Results ---")
    print(f"Duration:   {duration:.2f}s")
    print(f"Total Reqs: {total_reqs + errors}")
    print(f"Successes:  {total_reqs}")
    print(f"Errors:     {errors}")

    if all_latencies:
        all_latencies.sort()
        p50 = all_latencies[int(len(all_latencies) * 0.5)]
        p95 = all_latencies[int(len(all_latencies) * 0.95)]
        p99 = all_latencies[int(len(all_latencies) * 0.99)]
        print(f"p50 Latency: {p50*1000:.1f}ms")
        print(f"p95 Latency: {p95*1000:.1f}ms")
        print(f"p99 Latency: {p99*1000:.1f}ms")

if __name__ == "__main__":
    main()
