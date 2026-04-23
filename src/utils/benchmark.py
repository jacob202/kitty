#!/usr/bin/env python3
"""
Performance Benchmarking for Kitty
Measure and track system performance
"""

import json
import statistics
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import psutil


@dataclass
class BenchmarkResult:
    """Result of a benchmark"""

    name: str
    duration_ms: float
    memory_mb: float
    cpu_percent: float
    timestamp: str
    details: dict = None


class PerformanceBenchmark:
    """Benchmark system performance"""

    def __init__(self, results_dir: str = "data/benchmarks"):
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.results: list[BenchmarkResult] = []

    def benchmark(self, name: str, func, *args, **kwargs) -> BenchmarkResult:
        """Run a benchmark"""
        # Get baseline
        process = psutil.Process()
        start_mem = process.memory_info().rss / (1024 * 1024)
        process.cpu_percent()

        # Run function
        start_time = time.time()
        result = func(*args, **kwargs)
        duration = (time.time() - start_time) * 1000  # ms

        # Get metrics
        end_mem = process.memory_info().rss / (1024 * 1024)
        cpu_percent = process.cpu_percent()

        benchmark = BenchmarkResult(
            name=name,
            duration_ms=duration,
            memory_mb=end_mem - start_mem,
            cpu_percent=cpu_percent,
            timestamp=datetime.now().isoformat(),
            details={"result": str(result)[:100]},
        )

        self.results.append(benchmark)
        return benchmark

    def save_results(self):
        """Save benchmark results"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = self.results_dir / f"benchmark_{timestamp}.json"

        data = {
            "timestamp": datetime.now().isoformat(),
            "results": [asdict(r) for r in self.results],
        }

        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)

        return file_path

    def get_summary(self) -> dict:
        """Get summary of all benchmarks"""
        if not self.results:
            return {"status": "no_results"}

        durations = [r.duration_ms for r in self.results]
        memories = [r.memory_mb for r in self.results]

        return {
            "total_benchmarks": len(self.results),
            "avg_duration_ms": statistics.mean(durations),
            "max_duration_ms": max(durations),
            "min_duration_ms": min(durations),
            "avg_memory_mb": statistics.mean(memories),
            "total_memory_mb": sum(memories),
        }


# Predefined benchmarks
def run_all_benchmarks():
    """Run all system benchmarks"""
    benchmark = PerformanceBenchmark()

    print("=" * 60)
    print("🚀 KITTY PERFORMANCE BENCHMARKS")
    print("=" * 60)

    # Benchmark 1: Cache operations
    print("\n[Benchmark: Cache Operations]")
    try:
        from src.utils.cache import get_cache

        cache = get_cache()

        def cache_test():
            for i in range(100):
                cache.set(f"key_{i}", f"value_{i}")
                cache.get(f"key_{i}")

        result = benchmark.benchmark("cache_ops", cache_test)
        print(f"  Duration: {result.duration_ms:.2f}ms")
        print(f"  Memory: {result.memory_mb:.2f}MB")
    except Exception as e:
        print(f"  Error: {e}")

    # Benchmark 2: Session memory
    print("\n[Benchmark: Session Memory]")
    try:
        from src.core.session_memory import get_session_memory

        memory = get_session_memory()

        def session_test():
            for i in range(50):
                sid = memory.save_session(f"bench_{i}", {"data": i})
                memory.load_session(sid)

        result = benchmark.benchmark("session_memory", session_test)
        print(f"  Duration: {result.duration_ms:.2f}ms")
        print(f"  Memory: {result.memory_mb:.2f}MB")
    except Exception as e:
        print(f"  Error: {e}")

    # Benchmark 3: Agent types
    print("\n[Benchmark: Agent Types]")
    try:
        from src.agents.agent_types import get_agent_registry

        registry = get_agent_registry()

        def agent_test():
            for _ in range(100):
                registry.list_agents()
                registry.get_prompt("tester")

        result = benchmark.benchmark("agent_types", agent_test)
        print(f"  Duration: {result.duration_ms:.2f}ms")
        print(f"  Memory: {result.memory_mb:.2f}MB")
    except Exception as e:
        print(f"  Error: {e}")

    # Benchmark 4: Long-term memory
    print("\n[Benchmark: Long-term Memory]")
    try:
        from src.core.longterm_memory import get_longterm_memory

        ltm = get_longterm_memory()

        def ltm_test():
            for i in range(50):
                ltm.record_outcome(f"bench_{i}", f"task_{i}", True)
            ltm.generate_summary()

        result = benchmark.benchmark("longterm_memory", ltm_test)
        print(f"  Duration: {result.duration_ms:.2f}ms")
        print(f"  Memory: {result.memory_mb:.2f}MB")
    except Exception as e:
        print(f"  Error: {e}")

    # Summary
    print("\n" + "=" * 60)
    print("BENCHMARK SUMMARY")
    print("=" * 60)

    summary = benchmark.get_summary()
    print(f"Total benchmarks: {summary['total_benchmarks']}")
    print(f"Avg duration: {summary['avg_duration_ms']:.2f}ms")
    print(f"Total memory: {summary['total_memory_mb']:.2f}MB")

    # Save results
    file_path = benchmark.save_results()
    print(f"\nResults saved to: {file_path}")

    return benchmark


# CLI
def main():
    """Benchmark CLI"""
    import typer

    app = typer.Typer(help="Performance Benchmarking")

    @app.command("run")
    def run():
        """Run all benchmarks"""
        run_all_benchmarks()

    @app.command("list")
    def list_benchmarks():
        """List saved benchmarks"""
        bench_dir = Path("data/benchmarks")
        if bench_dir.exists():
            files = sorted(bench_dir.glob("*.json"), reverse=True)
            for f in files[:5]:
                typer.echo(f"  {f.name}")

    app()


if __name__ == "__main__":
    main()
