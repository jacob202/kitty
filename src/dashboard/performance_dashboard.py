"""
Performance Dashboard - CLI Dashboard for Specialist Performance Metrics
Real-time metrics display with time windows, specialist comparison, and cost breakdown.
"""

from typing import Any

# Rich CLI imports
try:
    from rich import box
    from rich.console import Console
    from rich.layout import Layout
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# Tabulate fallback
try:
    from tabulate import tabulate

    TABULATE_AVAILABLE = True
except ImportError:
    TABULATE_AVAILABLE = False


class PerformanceDashboard:
    """
    CLI Dashboard for specialist performance metrics.

    Displays:
    - Real-time metrics (1h, 24h, 7d windows)
    - Specialist comparison view
    - Cost breakdown by domain
    """

    TIME_WINDOWS = ["1h", "24h", "7d"]
    SPECIALISTS = ["Alex", "Kelly", "Mike", "Taylor", "Kitty Coder"]

    def __init__(self, metrics_module=None):
        """
        Initialize dashboard.

        Args:
            metrics_module: SpecialistMetrics instance or None to use global
        """
        self._console = Console() if RICH_AVAILABLE else None
        self._metrics = metrics_module

    @property
    def metrics(self):
        """Get metrics instance."""
        if self._metrics is None:
            from src.dashboard.specialist_metrics import get_specialist_metrics

            self._metrics = get_specialist_metrics()
        return self._metrics

    def display_summary(self, time_window: str | None = None, use_rich: bool = True) -> str:
        """
        Display overall performance summary.

        Args:
            time_window: "1h", "24h", "7d", or None
            use_rich: Use Rich formatting if available

        Returns:
            Formatted string output
        """
        summary = self.metrics.get_performance_summary(time_window)

        if use_rich and RICH_AVAILABLE:
            return self._display_summary_rich(summary)
        else:
            return self._display_summary_text(summary)

    def _display_summary_rich(self, summary: dict[str, Any]) -> str:
        """Display summary with Rich."""
        table = Table(
            title=f"📊 Performance Summary ({summary.get('time_window', 'alltime')})",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Metric", style="white", width=20)
        table.add_column("Value", style="green", justify="right")

        table.add_row("Total Queries", f"{summary['total_queries']}")
        table.add_row("Success Rate", f"{summary['success_rate']:.1%}")
        table.add_row("Avg Latency", f"{summary['avg_latency_ms']:.1f}ms")
        table.add_row("Total Cost", f"${summary['total_cost']:.4f}")
        table.add_row("Active Specialists", f"{summary['specialist_count']}")

        self._console.print(table)
        return ""

    def _display_summary_text(self, summary: dict[str, Any]) -> str:
        """Display summary as plain text."""
        lines = [
            f"Performance Summary ({summary.get('time_window', 'alltime')})",
            "=" * 40,
            f"Total Queries: {summary['total_queries']}",
            f"Success Rate: {summary['success_rate']:.1%}",
            f"Avg Latency: {summary['avg_latency_ms']:.1f}ms",
            f"Total Cost: ${summary['total_cost']:.4f}",
            f"Active Specialists: {summary['specialist_count']}",
        ]
        return "\n".join(lines)

    def display_specialist_comparison(
        self, time_window: str | None = None, use_rich: bool = True
    ) -> str:
        """
        Display specialist comparison table.

        Args:
            time_window: "1h", "24h", "7d", or None
            use_rich: Use Rich formatting if available

        Returns:
            Formatted string output
        """
        stats = self.metrics.get_stats(time_window=time_window)

        if use_rich and RICH_AVAILABLE:
            return self._display_comparison_rich(stats)
        elif TABULATE_AVAILABLE:
            return self._display_comparison_tabulate(stats)
        else:
            return self._display_comparison_text(stats)

    def _display_comparison_rich(self, stats: dict[str, Any]) -> str:
        """Display comparison with Rich."""
        table = Table(
            title="👥 Specialist Comparison",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Specialist", style="cyan", width=12)
        table.add_column("Domain", style="dim", width=18)
        table.add_column("Queries", justify="right", width=8)
        table.add_column("Success", justify="right", width=8)
        table.add_column("Avg Latency", justify="right", width=10)
        table.add_column("Cost", justify="right", width=10)

        for specialist in self.SPECIALISTS:
            if specialist in stats:
                s = stats[specialist]
                rate = s.get("success_rate", 0)
                rate_color = "green" if rate > 0.9 else "yellow" if rate > 0.7 else "red"

                table.add_row(
                    specialist,
                    s.get("domain", ""),
                    f"{s.get('query_count', 0)}",
                    f"[{rate_color}]{rate:.1%}[/{rate_color}]",
                    f"{s.get('avg_latency_ms', 0):.0f}ms",
                    f"${s.get('total_cost', 0):.4f}",
                )

        self._console.print(table)
        return ""

    def _display_comparison_tabulate(self, stats: dict[str, Any]) -> str:
        """Display comparison with tabulate."""
        rows = []
        for specialist in self.SPECIALISTS:
            if specialist in stats:
                s = stats[specialist]
                rows.append(
                    [
                        specialist,
                        s.get("domain", ""),
                        s.get("query_count", 0),
                        f"{s.get('success_rate', 0):.1%}",
                        f"{s.get('avg_latency_ms', 0):.0f}ms",
                        f"${s.get('total_cost', 0):.4f}",
                    ]
                )

        headers = ["Specialist", "Domain", "Queries", "Success", "Latency", "Cost"]
        return tabulate(rows, headers=headers, tablefmt="pretty")

    def _display_comparison_text(self, stats: dict[str, Any]) -> str:
        """Display comparison as plain text."""
        lines = [" Specialist Comparison", "-" * 60]

        for specialist in self.SPECIALISTS:
            if specialist in stats:
                s = stats[specialist]
                lines.append(
                    f"{specialist:10} | {s.get('domain', ''):18} | "
                    f"{s.get('query_count', 0):6} queries | "
                    f"{s.get('success_rate', 0):.1%} success | "
                    f"{s.get('avg_latency_ms', 0):.0f}ms | "
                    f"${s.get('total_cost', 0):.4f}"
                )

        return "\n".join(lines)

    def display_cost_breakdown(
        self, time_window: str | None = None, use_rich: bool = True
    ) -> str:
        """
        Display cost breakdown by domain.

        Args:
            time_window: "1h", "24h", "7d", or None
            use_rich: Use Rich formatting if available

        Returns:
            Formatted string output
        """
        breakdown = self.metrics.get_cost_breakdown(time_window)

        if use_rich and RICH_AVAILABLE:
            return self._display_cost_rich(breakdown)
        elif TABULATE_AVAILABLE:
            return self._display_cost_tabulate(breakdown)
        else:
            return self._display_cost_text(breakdown)

    def _display_cost_rich(self, breakdown: dict[str, dict[str, float]]) -> str:
        """Display cost breakdown with Rich."""
        table = Table(
            title="💰 Cost Breakdown by Domain",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Domain", style="cyan", width=20)
        table.add_column("Total Cost", justify="right", width=12)
        table.add_column("Queries", justify="right", width=10)
        table.add_column("Avg Cost", justify="right", width=12)

        for domain, data in breakdown.items():
            queries = data.get("queries", 0)
            total = data.get("total", 0)
            avg = total / queries if queries > 0 else 0

            table.add_row(domain, f"${total:.4f}", str(queries), f"${avg:.4f}")

        self._console.print(table)
        return ""

    def _display_cost_tabulate(self, breakdown: dict[str, dict[str, float]]) -> str:
        """Display cost breakdown with tabulate."""
        rows = []
        for domain, data in breakdown.items():
            queries = data.get("queries", 0)
            total = data.get("total", 0)
            avg = total / queries if queries > 0 else 0
            rows.append([domain, f"${total:.4f}", queries, f"${avg:.4f}"])

        headers = ["Domain", "Total Cost", "Queries", "Avg Cost"]
        return tabulate(rows, headers=headers, tablefmt="pretty")

    def _display_cost_text(self, breakdown: dict[str, dict[str, float]]) -> str:
        """Display cost breakdown as plain text."""
        lines = [" Cost Breakdown by Domain", "-" * 40]

        total_cost = 0
        total_queries = 0
        for domain, data in breakdown.items():
            queries = data.get("queries", 0)
            total = data.get("total", 0)
            total_cost += total
            total_queries += queries
            lines.append(f"  {domain:20} ${total:.4f} ({queries} queries)")

        lines.append("-" * 40)
        lines.append(f"  {'TOTAL':20} ${total_cost:.4f} ({total_queries} queries)")

        return "\n".join(lines)

    def display_routing_stats(self, use_rich: bool = True) -> str:
        """Display routing decision statistics."""
        routing = self.metrics.get_routing_stats()

        if use_rich and RICH_AVAILABLE:
            table = Table(
                title="🔀 Routing Decisions",
                box=box.ROUNDED,
                show_header=True,
                header_style="bold cyan",
            )
            table.add_column("Specialist", style="cyan", width=12)
            table.add_column("Domain", style="dim", width=20)
            table.add_column("Count", justify="right", width=8)

            for specialist, domains in routing.items():
                for domain, count in domains.items():
                    table.add_row(specialist, domain, str(count))

            self._console.print(table)

        lines = [" Routing Decisions", "-" * 40]
        for specialist, domains in routing.items():
            for domain, count in domains.items():
                lines.append(f"  {specialist} → {domain}: {count}")
        return "\n".join(lines)

    def display_full_dashboard(self, time_window: str | None = None) -> None:
        """
        Display full dashboard with all views.

        Args:
            time_window: "1h", "24h", "7d", or None
        """
        if not RICH_AVAILABLE:
            self._display_text_dashboard(time_window)
            return

        # Summary
        self.display_summary(time_window, use_rich=True)
        self._console.print()

        # Specialist comparison
        self.display_specialist_comparison(time_window, use_rich=True)
        self._console.print()

        # Cost breakdown
        self.display_cost_breakdown(time_window, use_rich=True)
        self._console.print()

        # Routing stats
        self.display_routing_stats(use_rich=True)

    def _display_text_dashboard(self, time_window: str | None) -> None:
        """Display dashboard as text when Rich not available."""
        print(self.display_summary(time_window, use_rich=False))
        print()
        print(self.display_specialist_comparison(time_window, use_rich=False))
        print()
        print(self.display_cost_breakdown(time_window, use_rich=False))
        print()
        print(self.display_routing_stats(use_rich=False))


# ── CLI Command Handlers ─────────────────���────────────────────────────────────


def handle_dashboard_command(args: list[str]) -> str:
    """
    Handle /dashboard CLI command.

    Usage: /dashboard [1h|24h|7d] [--specialists|--costs|--routing]

    Args:
        args: Command arguments

    Returns:
        Formatted output string
    """
    time_window = None
    view = "full"

    # Parse arguments
    for arg in args:
        if arg in ["1h", "24h", "7d"]:
            time_window = arg
        elif arg in ["--specialists", "-s"]:
            view = "specialists"
        elif arg in ["--costs", "-c"]:
            view = "costs"
        elif arg in ["--routing", "-r"]:
            view = "routing"
        elif arg == "--help":
            return DASHBOARD_HELP

    dashboard = PerformanceDashboard()

    if view == "specialists":
        return dashboard.display_specialist_comparison(time_window)
    elif view == "costs":
        return dashboard.display_cost_breakdown(time_window)
    elif view == "routing":
        return dashboard.display_routing_stats()
    else:
        dashboard._display_text_dashboard(time_window)
        return ""


DASHBOARD_HELP = """
/dashboard - Specialist Performance Dashboard

Usage:
  /dashboard           Show full dashboard (alltime)
  /dashboard 1h       Show metrics for last hour
  /dashboard 24h      Show metrics for last 24 hours
  /dashboard 7d       Show metrics for last 7 days
  /dashboard -s       Show specialist comparison only
  /dashboard -c       Show cost breakdown only
  /dashboard -r      Show routing stats only
  /dashboard 24h -c   Cost breakdown for 24h window

Views:
  -s, --specialists   Specialist comparison table
  -c, --costs         Cost breakdown by domain
  -r, --routing       Routing decision statistics
"""

# Command registry
DASHBOARD_COMMANDS = {
    "dashboard": handle_dashboard_command,
}


# Demo
if __name__ == "__main__":
    from src.dashboard.specialist_metrics import SpecialistMetrics

    # Create demo data
    metrics = SpecialistMetrics()

    test_queries = [
        (
            "Alex",
            "audio_electronics",
            "My tube amp is buzzing",
            245.3,
            True,
            120,
            340,
            0.012,
            None,
            "claude-3-5-sonnet-20241022",
        ),
        (
            "Alex",
            "audio_electronics",
            "Capacitor replacement",
            189.2,
            True,
            85,
            210,
            0.008,
            None,
            "claude-3-5-sonnet-20241022",
        ),
        (
            "Kelly",
            "fitness",
            "Squat form check",
            312.5,
            True,
            150,
            420,
            0.015,
            None,
            "claude-3-5-sonnet-20241022",
        ),
        (
            "Kelly",
            "fitness",
            "Deadlift technique",
            298.1,
            True,
            140,
            390,
            0.014,
            None,
            "claude-3-5-sonnet-20241022",
        ),
        (
            "Mike",
            "automotive",
            "Car won't start",
            278.1,
            True,
            130,
            380,
            0.014,
            None,
            "claude-3-5-sonnet-20241022",
        ),
        (
            "Mike",
            "automotive",
            "Check engine light",
            198.4,
            True,
            100,
            290,
            0.010,
            None,
            "claude-3-5-sonnet-20241022",
        ),
        (
            "Taylor",
            "self_help",
            "Feeling anxious",
            198.4,
            True,
            100,
            290,
            0.010,
            None,
            "claude-3-5-sonnet-20241022",
        ),
        (
            "Taylor",
            "self_help",
            "Meditation help",
            156.2,
            True,
            80,
            220,
            0.008,
            None,
            "claude-3-5-sonnet-20241022",
        ),
        (
            "Devin",
            "code",
            "Python bug fix",
            356.2,
            True,
            180,
            510,
            0.018,
            None,
            "claude-3-5-sonnet-20241022",
        ),
        (
            "Devin",
            "code",
            "React component",
            298.4,
            True,
            150,
            420,
            0.015,
            None,
            "claude-3-5-sonnet-20241022",
        ),
        (
            "Alex",
            "audio_electronics",
            "Power supply issue",
            0.0,
            False,
            40,
            0,
            0.0,
            "TimeoutError",
            "claude-3-5-sonnet-20241022",
        ),
    ]

    for spec, domain, query, latency, success, tin, tout, cost, err, model in test_queries:
        metrics.record_query(
            specialist=spec,
            domain=domain,
            query=query,
            latency_ms=latency,
            success=success,
            tokens_in=tin,
            tokens_out=tout,
            cost=cost,
            error_type=err,
            model=model,
        )

    print("=" * 70)
    print("PERFORMANCE DASHBOARD - DEMO")
    print("=" * 70)
    print()

    dashboard = PerformanceDashboard(metrics)

    try:
        dashboard.display_full_dashboard()
    except Exception:
        print("[Rich not available - falling back to text]")
        dashboard._display_text_dashboard("alltime")
