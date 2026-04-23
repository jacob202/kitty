# Performance Monitoring & Cost Tracking System

A comprehensive cost visibility and performance tracking system for Kitty AI that monitors LLM API usage, tracks costs, analyzes latency, and provides real-time budget alerts.

## Overview

This system provides:
- **Cost Tracking**: Track costs per model, feature, and time period
- **Performance Metrics**: Monitor latency, error rates, and throughput
- **Budget Alerts**: Set and monitor daily/monthly spending limits
- **Dashboards**: Interactive web dashboards and CLI reports
- **Cache Statistics**: Track cache hit/miss rates
- **Integration Hooks**: Automatic tracking of all LLM calls

## Files Created

### Core Components

1. **`src/utils/performance_monitor.py`** (1,100+ lines)
   - `MetricsCollector` - Singleton for tracking all metrics
   - `CostTracker` - High-level cost tracking interface
   - `DashboardGenerator` - Creates reports and visualizations
   - Database storage (DuckDB) with JSON fallback
   - 30+ models pricing data included

2. **`src/utils/metrics_cli.py`** (400+ lines)
   - CLI command handlers: `/metrics`, `/costs`, `/budget`, `/report`, `/cache`, `/errors`
   - Rich terminal output with tables and formatting
   - Budget alert display

3. **`src/utils/metrics_web.py`** (600+ lines)
   - Flask routes for `/admin/metrics` dashboard
   - REST API endpoints for metrics data
   - Real-time Chart.js visualizations
   - Responsive HTML dashboard

4. **`src/utils/performance_hooks.py`** (400+ lines)
   - `ModelCallTracker` - Decorator for tracking model calls
   - `MiddlewareTracker` - Track routing decisions
   - `PerformanceMonitorMixin` - Mixin for Supervisor class
   - Auto-integration functions

5. **`src/utils/PERFORMANCE_MONITORING_INTEGRATION.md`**
   - Step-by-step integration guide
   - Code snippets for each component
   - Quick start instructions

### Testing

6. **`tests/test_performance_monitor.py`** (250+ lines)
   - Comprehensive test suite
   - Tests all major components
   - Verifies integration points

## CLI Commands

Add these commands to your CLI (see integration guide):

```bash
/metrics              # Show performance summary
/costs --days 7       # Show cost breakdown
/budget --limit 100   # Set budget alert
/report --days 30     # Generate report
/cache                # Show cache statistics
/errors --days 7      # Show error statistics
```

## Web Dashboard

Access the dashboard at: `http://localhost:5001/admin/metrics`

### API Endpoints

```
GET  /api/metrics/summary      # Performance summary
GET  /api/metrics/daily        # Daily cost breakdown
GET  /api/metrics/models       # Cost by model
GET  /api/metrics/features     # Cost by feature
GET  /api/metrics/cache        # Cache statistics
GET  /api/metrics/errors       # Error statistics
GET  /api/metrics/budget       # Budget configuration
POST /api/metrics/budget       # Set budget limits
POST /api/metrics/report       # Generate report
```

## Database Schema

The system uses DuckDB (with JSON fallback) with these tables:

### requests
- `id`, `timestamp`, `model`, `feature`
- `tokens_in`, `tokens_out`, `cost`, `latency_ms`
- `success`, `error_type`, `metadata`

### errors
- `id`, `timestamp`, `error_type`, `model`, `feature`
- `context`, `stack_trace`

### cache_stats
- `cache_type`, `hits`, `misses`
- `last_hit_at`, `last_miss_at`

### budget_config
- `daily_limit`, `monthly_limit`
- `alert_threshold_percent`

## Pricing Data

30+ models pre-configured including:
- **OpenAI**: GPT-4o, GPT-4, GPT-3.5-turbo
- **Anthropic**: Claude 3.5 Sonnet, Claude 3 Opus, Claude 3 Haiku
- **Google**: Gemini 2.0 Flash, Gemini 1.5 Pro/Flash
- **OpenRouter**: DeepSeek, Qwen, Llama, Mistral
- **Local**: Ollama models (free)

## Quick Start

### 1. Install Dependencies

```bash
pip install duckdb matplotlib pandas
```

### 2. Track a Request

```python
from src.utils.performance_monitor import metrics_collector

# Track an LLM request
metrics_collector.track_request(
    model="gpt-4",
    tokens_in=1000,
    tokens_out=500,
    latency_ms=1200,
    feature="chat"
)
```

### 3. Set Budget Alerts

```python
# Set daily limit to $10
metrics_collector.set_budget_limits(daily=10.0, monthly=100.0)
```

### 4. View Metrics

```python
# Get summary
summary = metrics_collector.get_performance_summary()
print(f"Today's cost: ${summary['today']['cost']:.4f}")

# Get daily breakdown
daily = metrics_collector.get_daily_costs(days=7)
```

### 5. Generate Report

```python
from src.utils.performance_monitor import dashboard_generator

# Generate JSON/CSV report
report_path = dashboard_generator.generate_daily_report(days=7, format="json")

# Generate HTML dashboard
html_path = dashboard_generator.generate_html_dashboard()

# Generate plot (requires matplotlib)
plot_path = dashboard_generator.plot_cost_trend(days=30)
```

## Integration

### With Supervisor

```python
from src.utils.performance_hooks import (
    PerformanceMonitorMixin,
    integrate_performance_monitoring
)

class Supervisor(PerformanceMonitorMixin):
    def __init__(self):
        super().__init__()
        self._init_performance_monitoring()
        integrate_performance_monitoring(supervisor_instance=self)
```

### With Model Calls

```python
from src.utils.performance_hooks import model_call_tracker

@model_call_tracker.track("feature_name", model="gpt-4")
def my_llm_call(prompt):
    return call_openai(prompt)
```

### With Middleware

```python
from src.utils.performance_hooks import middleware_tracker

# In middleware process method:
result = middleware_tracker.track_route(middleware_result)
```

## Configuration

### Environment Variables

```bash
# Optional: Custom database path
export KITTY_METRICS_DB=/path/to/metrics.db
```

### Budget Alerts

Budget alerts trigger when:
- Daily cost exceeds threshold (default: 80% of limit)
- Alerts have 1-hour cooldown to prevent spam

### Database Location

Default: `./data/performance_metrics.db`

If DuckDB is not available, falls back to: `./data/performance_metrics.json`

## Performance Impact

- **Minimal overhead**: <1ms per tracked request
- **Async storage**: Non-blocking writes
- **Singleton pattern**: Shared collector instance
- **Optional components**: Graceful degradation if dependencies missing

## Troubleshooting

### Import Errors

If imports fail, the system degrades gracefully:
```python
if PERFORMANCE_MONITOR_AVAILABLE:
    # Use monitoring
else:
    # Continue without monitoring
```

### Database Locked

If you get "database locked" errors:
1. Check no other process is using the database
2. Restart the application
3. Delete the `.db` file to reset (data will be lost)

### Missing Visualizations

If plots don't generate:
```bash
pip install matplotlib pandas
```

## Example Output

### CLI /metrics

```
Performance Metrics
═══════════════════════════════════════════════════════════

Today's Activity
  Cost: $0.0234
  Requests: 12
  Errors: 0

This Week:
  Cost: $0.1567
  Requests: 84
  Avg Latency: 1456ms
  Error Rate: 0.00%

Budget Status:
  Daily: 23.4% used
  Monthly Estimate: $6.72

Top Models by Cost:
  Model                           Requests    Cost       Avg Latency
  ─────────────────────────────────────────────────────────────────
  gemini-2.0-flash-001            45          $0.0892    890ms
  claude-3-5-sonnet               23          $0.0675    2341ms
  gpt-4                           16          $0.0234    1876ms
```

## Testing

Run the test suite:

```bash
python tests/test_performance_monitor.py
```

Expected output:
```
============================================================
Performance Monitoring System Test Suite
============================================================
Testing imports...
✓ performance_monitor imports successful
✓ metrics_cli imports successful
✓ metrics_web imports successful
✓ performance_hooks imports successful

Testing MetricsCollector...
✓ Cost calculation works: $0.0125
✓ Request tracking works: 1000 tokens in
...

Test Results: 7 passed, 0 failed
============================================================

✓ All tests passed! Performance monitoring system is ready.
```

## Future Enhancements

- [ ] WebSocket real-time updates
- [ ] Export to Google Sheets
- [ ] Cost forecasting with ML
- [ ] Team/organization support
- [ ] Slack/email alerts
- [ ] A/B testing metrics

## License

Same as Kitty AI project.
