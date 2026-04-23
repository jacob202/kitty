"""
Performance Monitoring Integration Guide for Kitty AI

This file shows how to integrate the performance monitoring system
into the existing Kitty AI codebase.
"""

# =============================================================================
# 1. ADD TO CLI (cli.py)
# =============================================================================

# Add to imports at the top of cli.py:
"""
from src.utils.metrics_cli import (
    handle_metrics_command,
    handle_costs_command,
    handle_budget_command,
    handle_report_command,
    handle_cache_command,
    handle_errors_command,
    METRICS_COMMANDS,
)
"""

# Add to COMMANDS dictionary (around line 16 in cli.py's COMMANDS):
"""
COMMANDS.update(METRICS_COMMANDS)
"""

# Add command handlers in the main loop (after the existing command handlers):
"""
elif inp == "/metrics":
    handle_metrics_command()
    console.print()

elif inp.startswith("/costs"):
    parts = inp.split(maxsplit=1)
    args = parts[1] if len(parts) > 1 else ""
    handle_costs_command(args)
    console.print()

elif inp.startswith("/budget"):
    parts = inp.split(maxsplit=1)
    args = parts[1] if len(parts) > 1 else ""
    handle_budget_command(args)
    console.print()

elif inp.startswith("/report"):
    parts = inp.split(maxsplit=1)
    args = parts[1] if len(parts) > 1 else ""
    handle_report_command(args)
    console.print()

elif inp == "/cache":
    handle_cache_command()
    console.print()

elif inp.startswith("/errors"):
    parts = inp.split(maxsplit=1)
    args = parts[1] if len(parts) > 1 else ""
    handle_errors_command(args)
    console.print()
"""


# =============================================================================
# 2. ADD TO WEB UI (web.py)
# =============================================================================

# Add to imports at the top of web.py:
"""
from src.utils.metrics_web import register_metrics_routes
"""

# After app and socketio initialization, add:
"""
# Register metrics routes
register_metrics_routes(app)
"""


# =============================================================================
# 3. ADD TO SUPERVISOR (scripts/supervisor.py)
# =============================================================================

# Add to imports:
"""
try:
    from src.utils.performance_hooks import (
        PerformanceMonitorMixin,
        integrate_performance_monitoring,
    )
    PERFORMANCE_HOOKS_AVAILABLE = True
except ImportError:
    PERFORMANCE_HOOKS_AVAILABLE = False
"""

# Modify Supervisor class definition:
"""
class Supervisor(PerformanceMonitorMixin if PERFORMANCE_HOOKS_AVAILABLE else object):
    def __init__(self):
        # ... existing init code ...
        
        # Initialize performance monitoring
        if PERFORMANCE_HOOKS_AVAILABLE:
            self._init_performance_monitoring()
            integrate_performance_monitoring(supervisor_instance=self)
"""

# Add budget tracking to existing cost tracking (around session_cost updates):
"""
def _stream_openrouter(self, prompt, system_prompt=None, model=None, use_history=True):
    # ... existing code ...
    
    # Track with performance monitor
    if hasattr(self, '_metrics_collector') and self._metrics_collector:
        self.track_model_call(
            model=model or self.config.get("flash_model"),
            prompt=prompt,
            response=full,
            feature="openrouter",
            latency_ms=latency_ms  # You'll need to track this
        )
"""


# =============================================================================
# 4. ADD TO MIDDLEWARE (src/middleware.py)
# =============================================================================

# Add to imports:
"""
try:
    from src.utils.performance_hooks import middleware_tracker
    PERFORMANCE_HOOKS_AVAILABLE = True
except ImportError:
    PERFORMANCE_HOOKS_AVAILABLE = False
"""

# In the process method, add at the end before returning:
"""
def process(self, prompt: str, history: List[Dict] = None) -> MiddlewareResult:
    # ... existing code ...
    
    result = MiddlewareResult(...)
    
    # Track routing decision
    if PERFORMANCE_HOOKS_AVAILABLE:
        middleware_tracker.track_route(result)
    
    return result
"""


# =============================================================================
# 5. ADD TO MODEL CALLER (src/core/model_caller.py)
# =============================================================================

# Add to imports:
"""
try:
    from src.utils.performance_hooks import model_call_tracker
    PERFORMANCE_HOOKS_AVAILABLE = True
except ImportError:
    PERFORMANCE_HOOKS_AVAILABLE = False
"""

# Modify call_with_fallback to track calls:
"""
def call_with_fallback(self, prompt: str, system_prompt: Optional[str] = None, 
                      model: str = "flash", use_history: bool = True):
    
    if not PERFORMANCE_HOOKS_AVAILABLE:
        return self._do_call(prompt, system_prompt, model, use_history)
    
    # Track with decorator
    @model_call_tracker.track("model_caller", model=model)
    def _tracked_call(p, sp, m, uh):
        return self._do_call(p, sp, m, uh)
    
    return _tracked_call(prompt, system_prompt, model, use_history)

# Rename existing implementation to _do_call
"""


# =============================================================================
# 6. OPTIONAL: ADD TO REQUIREMENTS
# =============================================================================

# Add to requirements.txt:
"""
# Performance monitoring
duckdb>=0.9.0
matplotlib>=3.7.0
pandas>=2.0.0
"""


# =============================================================================
# 7. CREATE DATA DIRECTORY
# =============================================================================

# The performance monitoring system will create a data directory automatically,
# but you can pre-create it:
"""
mkdir -p data/dashboards
"""


# =============================================================================
# 8. ACCESSING THE DASHBOARD
# =============================================================================

# After integration:
# - CLI commands: /metrics, /costs, /budget, /report, /cache, /errors
# - Web dashboard: http://localhost:5001/admin/metrics
# - API endpoints:
#   - GET /api/metrics/summary
#   - GET /api/metrics/daily?days=30
#   - GET /api/metrics/models
#   - GET /api/metrics/features
#   - GET /api/metrics/cache
#   - GET /api/metrics/errors
#   - GET /api/metrics/budget
#   - POST /api/metrics/budget (set limits)


# =============================================================================
# 9. QUICK START
# =============================================================================

# 1. Install dependencies:
#    pip install duckdb matplotlib pandas

# 2. Import the performance monitor in your code:
#    from src.utils.performance_monitor import metrics_collector, cost_tracker

# 3. Track a request:
#    metrics_collector.track_request(
#        model="gpt-4",
#        tokens_in=1000,
#        tokens_out=500,
#        latency_ms=1200,
#        feature="chat"
#    )

# 4. Set budget limits:
#    metrics_collector.set_budget_limits(daily=10.0, monthly=100.0)

# 5. View metrics:
#    summary = metrics_collector.get_performance_summary()
#    print(f"Today's cost: ${summary['today']['cost']:.4f}")
