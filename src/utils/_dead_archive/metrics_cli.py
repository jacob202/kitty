"""
CLI commands for performance monitoring and cost tracking.
Add these commands to the main CLI.
"""


from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

# Import performance monitor
try:
    from src.utils.performance_monitor import (
        CostTracker,
        DashboardGenerator,
        MetricsCollector,
        cost_tracker,
        dashboard_generator,
        metrics_collector,
    )

    PERFORMANCE_MONITOR_AVAILABLE = True
except ImportError:
    PERFORMANCE_MONITOR_AVAILABLE = False
    print("[WARN] Performance monitor not available")


def show_metrics_summary():
    """Show performance metrics summary."""
    if not PERFORMANCE_MONITOR_AVAILABLE:
        console.print("[yellow]Performance monitoring not available[/yellow]")
        return

    try:
        summary = metrics_collector.get_performance_summary()

        # Main metrics panel
        console.print(
            Panel(
                f"[bold cyan]Today's Activity[/bold cyan]\n"
                f"  Cost: [green]${summary['today']['cost']:.4f}[/green]\n"
                f"  Requests: {summary['today']['requests']}\n"
                f"  Errors: {summary['today']['errors']}",
                title="Performance Metrics",
                border_style="cyan",
            )
        )

        # Weekly summary
        console.print("\n[bold]This Week:[/bold]")
        console.print(f"  Cost: ${summary['this_week']['cost']:.4f}")
        console.print(f"  Requests: {summary['this_week']['requests']}")
        console.print(f"  Avg Latency: {summary['avg_latency_ms']:.0f}ms")
        console.print(f"  Error Rate: {summary['error_rate']:.2f}%")

        # Budget status
        budget = summary["budget_status"]
        budget_color = (
            "green"
            if budget["daily_used_percent"] < 50
            else "yellow"
            if budget["daily_used_percent"] < 80
            else "red"
        )
        console.print("\n[bold]Budget Status:[/bold]")
        console.print(
            f"  Daily: [bold {budget_color}]{budget['daily_used_percent']:.1f}%[/bold {budget_color}] used"
        )
        console.print(f"  Monthly Estimate: ${summary['monthly_estimate']['projected_month']:.2f}")

        # Model breakdown
        if summary["model_breakdown"]:
            console.print("\n[bold]Top Models by Cost:[/bold]")
            table = Table(box=box.SIMPLE, show_header=True, header_style="bold")
            table.add_column("Model", style="cyan")
            table.add_column("Requests", justify="right")
            table.add_column("Cost", justify="right")
            table.add_column("Avg Latency", justify="right")

            for model in summary["model_breakdown"][:5]:
                table.add_row(
                    model["model"].split("/")[-1][:30],
                    str(model["requests"]),
                    f"${model['cost']:.4f}",
                    f"{model['avg_latency']:.0f}ms",
                )
            console.print(table)

        # Feature breakdown
        if summary["feature_breakdown"]:
            console.print("\n[bold]Top Features by Cost:[/bold]")
            table = Table(box=box.SIMPLE, show_header=True, header_style="bold")
            table.add_column("Feature", style="cyan")
            table.add_column("Requests", justify="right")
            table.add_column("Cost", justify="right")

            for feature in summary["feature_breakdown"][:5]:
                table.add_row(
                    feature["feature"], str(feature["requests"]), f"${feature['cost']:.4f}"
                )
            console.print(table)

        # Alerts
        if budget["daily_used_percent"] > 80:
            console.print(
                f"\n[bold red]⚠ Budget Alert: Daily limit {budget['daily_used_percent']:.1f}% consumed![/bold red]"
            )

        console.print()

    except Exception as e:
        console.print(f"[red]Error loading metrics: {e}[/red]")


def show_cost_breakdown(days: int = 7):
    """Show detailed cost breakdown."""
    if not PERFORMANCE_MONITOR_AVAILABLE:
        console.print("[yellow]Performance monitoring not available[/yellow]")
        return

    try:
        daily_costs = metrics_collector.get_daily_costs(days)

        if not daily_costs:
            console.print("[dim]No cost data available.[/dim]")
            return

        console.print(
            Panel(f"[bold cyan]Cost Breakdown (Last {days} Days)[/bold cyan]", border_style="cyan")
        )

        # Daily breakdown table
        table = Table(box=box.SIMPLE, show_header=True, header_style="bold")
        table.add_column("Date", style="cyan")
        table.add_column("Requests", justify="right")
        table.add_column("Tokens In", justify="right")
        table.add_column("Tokens Out", justify="right")
        table.add_column("Cost", justify="right")
        table.add_column("Avg Latency", justify="right")
        table.add_column("Errors", justify="right")

        total_cost = 0
        for day in daily_costs:
            total_cost += day["cost"]
            error_style = "red" if day.get("errors", 0) > 0 else "dim"
            table.add_row(
                day["date"],
                str(day["requests"]),
                f"{day['tokens_in']:,}",
                f"{day['tokens_out']:,}",
                f"${day['cost']:.4f}",
                f"{day['avg_latency']:.0f}ms",
                f"[{error_style}]{day.get('errors', 0)}[/{error_style}]",
            )

        console.print(table)
        console.print(f"\n[bold]Total Cost: ${total_cost:.4f}[/bold]")

        # Cost by model
        model_costs = metrics_collector.get_cost_by_model(days)
        if model_costs:
            console.print("\n[bold]Cost by Model:[/bold]")
            table = Table(box=box.SIMPLE, show_header=True, header_style="bold")
            table.add_column("Model", style="cyan")
            table.add_column("Requests", justify="right")
            table.add_column("Cost", justify="right")
            table.add_column("% of Total", justify="right")

            for model in model_costs:
                pct = (model["cost"] / total_cost * 100) if total_cost > 0 else 0
                table.add_row(
                    model["model"].split("/")[-1][:40],
                    str(model["requests"]),
                    f"${model['cost']:.4f}",
                    f"{pct:.1f}%",
                )
            console.print(table)

        console.print()

    except Exception as e:
        console.print(f"[red]Error loading cost breakdown: {e}[/red]")


def show_budget_settings():
    """Show current budget settings."""
    if not PERFORMANCE_MONITOR_AVAILABLE:
        console.print("[yellow]Performance monitoring not available[/yellow]")
        return

    try:
        summary = metrics_collector.get_performance_summary()
        budget = summary["budget_status"]

        console.print(
            Panel(
                f"[bold cyan]Budget Configuration[/bold cyan]\n\n"
                f"Daily Limit: ${budget['daily_limit']:.2f}\n"
                f"Monthly Limit: ${summary['monthly_estimate']['projected_month']:.2f} (projected)\n\n"
                f"Today's Usage:\n"
                f"  Cost: ${summary['today']['cost']:.4f}\n"
                f"  Remaining: ${max(0, budget['daily_limit'] - summary['today']['cost']):.4f}\n"
                f"  Used: {budget['daily_used_percent']:.1f}%",
                border_style="cyan",
            )
        )

    except Exception as e:
        console.print(f"[red]Error loading budget settings: {e}[/red]")


def set_budget_limit(daily: float | None = None, monthly: float | None = None):
    """Set budget limits."""
    if not PERFORMANCE_MONITOR_AVAILABLE:
        console.print("[yellow]Performance monitoring not available[/yellow]")
        return

    try:
        metrics_collector.set_budget_limits(daily, monthly)

        console.print("[green]✓ Budget limits updated:[/green]")
        if daily is not None:
            console.print(f"  Daily: ${daily:.2f}")
        if monthly is not None:
            console.print(f"  Monthly: ${monthly:.2f}")
        console.print()

    except Exception as e:
        console.print(f"[red]Error setting budget: {e}[/red]")


def generate_report(days: int = 7, format: str = "json"):
    """Generate a performance report."""
    if not PERFORMANCE_MONITOR_AVAILABLE:
        console.print("[yellow]Performance monitoring not available[/yellow]")
        return

    try:
        report_path = dashboard_generator.generate_daily_report(days, format)
        console.print(f"[green]✓ Report generated:[/green] {report_path}")

        # Also generate HTML dashboard
        html_path = dashboard_generator.generate_html_dashboard()
        console.print(f"[green]✓ Dashboard generated:[/green] {html_path}")

        # Generate plots if matplotlib available
        try:
            plot_path = dashboard_generator.plot_cost_trend(days)
            if plot_path:
                console.print(f"[green]✓ Cost trend plot:[/green] {plot_path}")

            pie_path = dashboard_generator.plot_model_breakdown(days)
            if pie_path:
                console.print(f"[green]✓ Model breakdown plot:[/green] {pie_path}")
        except Exception as e:
            console.print(f"[dim]Plot generation skipped: {e}[/dim]")

        console.print()

    except Exception as e:
        console.print(f"[red]Error generating report: {e}[/red]")


def show_cache_stats():
    """Show cache statistics."""
    if not PERFORMANCE_MONITOR_AVAILABLE:
        console.print("[yellow]Performance monitoring not available[/yellow]")
        return

    try:
        stats = metrics_collector.get_cache_stats()

        if not stats:
            console.print("[dim]No cache data available.[/dim]")
            return

        console.print(Panel("[bold cyan]Cache Statistics[/bold cyan]", border_style="cyan"))

        table = Table(box=box.SIMPLE, show_header=True, header_style="bold")
        table.add_column("Cache Type", style="cyan")
        table.add_column("Hits", justify="right")
        table.add_column("Misses", justify="right")
        table.add_column("Hit Rate", justify="right")
        table.add_column("Total", justify="right")

        for stat in stats:
            total = stat["hits"] + stat["misses"]
            hit_rate_color = (
                "green" if stat["hit_rate"] > 70 else "yellow" if stat["hit_rate"] > 40 else "red"
            )
            table.add_row(
                stat["cache_type"],
                str(stat["hits"]),
                str(stat["misses"]),
                f"[{hit_rate_color}]{stat['hit_rate']:.1f}%[/{hit_rate_color}]",
                str(total),
            )

        console.print(table)
        console.print()

    except Exception as e:
        console.print(f"[red]Error loading cache stats: {e}[/red]")


def show_error_stats(days: int = 7):
    """Show error statistics."""
    if not PERFORMANCE_MONITOR_AVAILABLE:
        console.print("[yellow]Performance monitoring not available[/yellow]")
        return

    try:
        stats = metrics_collector.get_error_stats(days)

        if not stats:
            console.print("[dim]No errors recorded.[/dim]")
            return

        console.print(
            Panel(
                f"[bold cyan]Error Statistics (Last {days} Days)[/bold cyan]", border_style="cyan"
            )
        )

        table = Table(box=box.SIMPLE, show_header=True, header_style="bold")
        table.add_column("Error Type", style="red")
        table.add_column("Model")
        table.add_column("Count", justify="right")
        table.add_column("Last Occurrence")

        for stat in stats:
            table.add_row(
                stat["error_type"],
                stat["model"] or "N/A",
                str(stat["count"]),
                str(stat["last_occurrence"])[:19] if stat["last_occurrence"] else "N/A",
            )

        console.print(table)
        console.print()

    except Exception as e:
        console.print(f"[red]Error loading error stats: {e}[/red]")


# Command handlers for CLI integration
def handle_metrics_command(args: str = ""):
    """Handle /metrics command."""
    show_metrics_summary()


def handle_costs_command(args: str = ""):
    """Handle /costs command with optional --days argument."""
    days = 7

    # Parse --days argument
    if "--days" in args:
        parts = args.split("--days")
        if len(parts) > 1:
            try:
                days = int(parts[1].split()[0])
            except (ValueError, IndexError):
                pass

    show_cost_breakdown(days)


def handle_budget_command(args: str = ""):
    """Handle /budget command with optional --limit argument."""
    # Parse --limit argument
    if "--limit" in args or "--daily" in args:
        limit = None
        for prefix in ["--limit", "--daily"]:
            if prefix in args:
                parts = args.split(prefix)
                if len(parts) > 1:
                    try:
                        limit = float(parts[1].split()[0])
                        break
                    except (ValueError, IndexError):
                        pass

        if limit is not None:
            set_budget_limit(daily=limit)
        else:
            show_budget_settings()
    else:
        show_budget_settings()


def handle_report_command(args: str = ""):
    """Handle /report command."""
    days = 7
    format = "json"

    if "--days" in args:
        parts = args.split("--days")
        if len(parts) > 1:
            try:
                days = int(parts[1].split()[0])
            except (ValueError, IndexError):
                pass

    if "--csv" in args:
        format = "csv"
    elif "--html" in args:
        format = "html"

    generate_report(days, format)


def handle_cache_command(args: str = ""):
    """Handle /cache command."""
    show_cache_stats()


def handle_errors_command(args: str = ""):
    """Handle /errors command."""
    days = 7

    if "--days" in args:
        parts = args.split("--days")
        if len(parts) > 1:
            try:
                days = int(parts[1].split()[0])
            except (ValueError, IndexError):
                pass

    show_error_stats(days)


# Export command definitions for CLI
METRICS_COMMANDS = {
    "/metrics": ("/metrics", "Show performance summary"),
    "/costs": ("/costs [--days N]", "Show cost breakdown (default: 7 days)"),
    "/budget": ("/budget [--limit N]", "Show or set budget limits"),
    "/report": ("/report [--days N] [--csv|--html]", "Generate performance report"),
    "/cache": ("/cache", "Show cache statistics"),
    "/errors": ("/errors [--days N]", "Show error statistics"),
}


if __name__ == "__main__":
    # Demo/test
    print("Performance Monitor CLI Commands Demo")
    print("=" * 50)
    show_metrics_summary()
