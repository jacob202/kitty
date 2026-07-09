#!/usr/bin/env python3
"""
Live Swarm Test for MemoryWeave.

Spins up multiple concurrent workers to aggressively read and write from the
SQLite-backed MemoryWeave database to validate that WAL mode is functioning
correctly under load and that no "database is locked" errors occur.
"""

import argparse
import logging
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add the project root to sys.path so we can import gateway
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gateway.memory_weave import get_weave

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(threadName)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("swarm_test")


def worker_task(worker_id: int, iterations: int, pacing_ms: int) -> dict:
    """A single worker running through read/write loops against MemoryWeave."""
    weave = get_weave()
    stats = {"reads": 0, "writes": 0, "errors": 0}

    entities = [f"System-{i}" for i in range(10)]
    relations = ["status", "version", "config", "owner"]

    for i in range(iterations):
        try:
            action = random.choices(["read", "write", "correct", "event"], weights=[40, 40, 10, 10])[0]
            entity = random.choice(entities)
            relation = random.choice(relations)

            if action == "read":
                weave.query(entity, relation)
                stats["reads"] += 1

            elif action == "write":
                val = f"val-{random.randint(100, 999)}"
                weave.fact(
                    entity=entity,
                    relation=relation,
                    value=val,
                    source=f"worker-{worker_id}-{random.randint(10000, 99999)}",
                    confidence=random.uniform(0.5, 0.9)
                )
                stats["writes"] += 1

            elif action == "correct":
                val = f"corrected-{random.randint(100, 999)}"
                weave.correct(
                    entity=entity,
                    relation=relation,
                    new_value=val,
                    source=f"worker-{worker_id}-{random.randint(10000, 99999)}",
                    reason="Random correction"
                )
                stats["writes"] += 1

            elif action == "event":
                weave.event(
                    event_type="test_event",
                    entity=entity,
                    description=f"Swarm test event from worker {worker_id}",
                    severity="info"
                )
                stats["writes"] += 1

        except Exception as e:
            logger.error("Worker %s encountered error: %s", worker_id, e)
            stats["errors"] += 1

        if pacing_ms > 0:
            time.sleep(random.randint(0, pacing_ms) / 1000.0)

    return stats


def run_swarm(workers: int, iterations: int, pacing_ms: int) -> None:
    logger.info("Starting swarm test: %s workers, %s iterations each.", workers, iterations)
    start_time = time.time()

    total_stats = {"reads": 0, "writes": 0, "errors": 0}

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(worker_task, i, iterations, pacing_ms): i
            for i in range(workers)
        }

        for future in as_completed(futures):
            worker_id = futures[future]
            try:
                stats = future.result()
                total_stats["reads"] += stats["reads"]
                total_stats["writes"] += stats["writes"]
                total_stats["errors"] += stats["errors"]
                logger.info("Worker %s finished: %s", worker_id, stats)
            except Exception as e:
                logger.error("Worker %s failed fatally: %s", worker_id, e)
                total_stats["errors"] += 1

    duration = time.time() - start_time
    logger.info("=== Swarm Test Complete ===")
    logger.info("Duration: %.2f seconds", duration)
    logger.info("Total Reads: %s", total_stats["reads"])
    logger.info("Total Writes: %s", total_stats["writes"])
    logger.info("Total Errors: %s", total_stats["errors"])

    if total_stats["errors"] > 0:
        logger.error("TEST FAILED: Encountered %s errors (likely SQLite locks).", total_stats["errors"])
        sys.exit(1)
    else:
        logger.info("TEST PASSED: SQLite WAL mode handled the concurrency successfully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Live Swarm Test for MemoryWeave")
    parser.add_argument("--workers", type=int, default=10, help="Number of concurrent workers")
    parser.add_argument("--iterations", type=int, default=100, help="Operations per worker")
    parser.add_argument("--pacing-ms", type=int, default=10, help="Max random sleep between ops in ms")

    args = parser.parse_args()
    run_swarm(args.workers, args.iterations, args.pacing_ms)
