"""
Web UI routes for performance monitoring dashboard.
Add these routes to the Flask application (web.py).
"""


from flask import jsonify, render_template_string, request

# Import performance monitor
try:
    from src.utils.performance_monitor import (
        DashboardGenerator,
        MetricsCollector,
        dashboard_generator,
        metrics_collector,
    )

    PERFORMANCE_MONITOR_AVAILABLE = True
except ImportError:
    PERFORMANCE_MONITOR_AVAILABLE = False


# HTML template for metrics dashboard
METRICS_DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kitty AI - Performance Metrics</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #fff;
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
        }

        header {
            text-align: center;
            padding: 30px 0;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            margin-bottom: 30px;
        }

        h1 {
            font-size: 2.5em;
            background: linear-gradient(135deg, #00d4ff, #7b2cbf);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }

        .subtitle {
            color: rgba(255,255,255,0.6);
        }

        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .metric-card {
            background: rgba(255,255,255,0.05);
            border-radius: 16px;
            padding: 25px;
            border: 1px solid rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            transition: transform 0.3s, box-shadow 0.3s;
        }

        .metric-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 40px rgba(0,0,0,0.3);
        }

        .metric-card.warning {
            border-color: #ffc107;
            background: rgba(255,193,7,0.1);
        }

        .metric-card.danger {
            border-color: #dc3545;
            background: rgba(220,53,69,0.1);
        }

        .metric-value {
            font-size: 2.5em;
            font-weight: bold;
            margin: 10px 0;
        }

        .metric-value.success { color: #4CAF50; }
        .metric-value.warning { color: #ffc107; }
        .metric-value.danger { color: #dc3545; }
        .metric-value.info { color: #00d4ff; }

        .metric-label {
            color: rgba(255,255,255,0.6);
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .metric-change {
            font-size: 0.85em;
            margin-top: 5px;
        }

        .chart-container {
            background: rgba(255,255,255,0.05);
            border-radius: 16px;
            padding: 25px;
            margin-bottom: 20px;
            border: 1px solid rgba(255,255,255,0.1);
        }

        .chart-title {
            font-size: 1.2em;
            margin-bottom: 20px;
            color: rgba(255,255,255,0.9);
        }

        .tables-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }

        .data-table {
            background: rgba(255,255,255,0.05);
            border-radius: 16px;
            padding: 20px;
            border: 1px solid rgba(255,255,255,0.1);
            overflow-x: auto;
        }

        .data-table h3 {
            margin-bottom: 15px;
            color: rgba(255,255,255,0.9);
        }

        table {
            width: 100%;
            border-collapse: collapse;
        }

        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }

        th {
            color: rgba(255,255,255,0.6);
            font-weight: 500;
            text-transform: uppercase;
            font-size: 0.8em;
            letter-spacing: 0.5px;
        }

        td {
            color: rgba(255,255,255,0.9);
        }

        tr:hover {
            background: rgba(255,255,255,0.05);
        }

        .badge {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.75em;
            font-weight: bold;
        }

        .badge-success { background: rgba(76,175,80,0.3); color: #4CAF50; }
        .badge-warning { background: rgba(255,193,7,0.3); color: #ffc107; }
        .badge-danger { background: rgba(220,53,69,0.3); color: #dc3545; }

        .refresh-btn {
            position: fixed;
            bottom: 30px;
            right: 30px;
            background: linear-gradient(135deg, #00d4ff, #7b2cbf);
            color: white;
            border: none;
            padding: 15px 30px;
            border-radius: 50px;
            cursor: pointer;
            font-size: 1em;
            box-shadow: 0 4px 20px rgba(0,212,255,0.3);
            transition: transform 0.3s, box-shadow 0.3s;
        }

        .refresh-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 30px rgba(0,212,255,0.4);
        }

        .alert {
            padding: 15px 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .alert-warning {
            background: rgba(255,193,7,0.2);
            border: 1px solid #ffc107;
            color: #ffc107;
        }

        .alert-danger {
            background: rgba(220,53,69,0.2);
            border: 1px solid #dc3545;
            color: #dc3545;
        }

        .loading {
            text-align: center;
            padding: 40px;
            color: rgba(255,255,255,0.5);
        }

        .error {
            text-align: center;
            padding: 40px;
            color: #dc3545;
        }

        @media (max-width: 768px) {
            .metrics-grid {
                grid-template-columns: 1fr;
            }
            .tables-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Performance Metrics</h1>
            <p class="subtitle">Real-time API usage and cost monitoring</p>
        </header>

        <div id="alerts"></div>

        <div class="metrics-grid" id="metrics-grid">
            <div class="loading">Loading metrics...</div>
        </div>

        <div class="chart-container">
            <h3 class="chart-title">Cost Trend (Last 30 Days)</h3>
            <canvas id="costChart"></canvas>
        </div>

        <div class="chart-container">
            <h3 class="chart-title">Cost by Model</h3>
            <canvas id="modelChart"></canvas>
        </div>

        <div class="tables-grid">
            <div class="data-table">
                <h3>Top Models</h3>
                <table id="models-table">
                    <thead>
                        <tr>
                            <th>Model</th>
                            <th>Requests</th>
                            <th>Cost</th>
                        </tr>
                    </thead>
                    <tbody></tbody>
                </table>
            </div>

            <div class="data-table">
                <h3>Top Features</h3>
                <table id="features-table">
                    <thead>
                        <tr>
                            <th>Feature</th>
                            <th>Requests</th>
                            <th>Cost</th>
                        </tr>
                    </thead>
                    <tbody></tbody>
                </table>
            </div>
        </div>
    </div>

    <button class="refresh-btn" onclick="loadMetrics()">Refresh</button>

    <script>
        let costChart = null;
        let modelChart = null;

        function formatCurrency(value) {
            return '$' + value.toFixed(4);
        }

        function getBudgetClass(percent) {
            if (percent >= 90) return 'danger';
            if (percent >= 75) return 'warning';
            return '';
        }

        async function loadMetrics() {
            try {
                const response = await fetch('/api/metrics/summary');
                const data = await response.json();

                if (data.error) {
                    document.getElementById('metrics-grid').innerHTML =
                        `<div class="error">Error: ${data.error}</div>`;
                    return;
                }

                // Update metrics cards
                const metricsGrid = document.getElementById('metrics-grid');
                const budgetClass = getBudgetClass(data.budget_status.daily_used_percent);

                metricsGrid.innerHTML = `
                    <div class="metric-card">
                        <div class="metric-label">Today's Cost</div>
                        <div class="metric-value info">${formatCurrency(data.today.cost)}</div>
                        <div class="metric-change">${data.today.requests} requests</div>
                    </div>

                    <div class="metric-card">
                        <div class="metric-label">This Week</div>
                        <div class="metric-value success">${formatCurrency(data.this_week.cost)}</div>
                        <div class="metric-change">${data.this_week.requests} requests</div>
                    </div>

                    <div class="metric-card ${budgetClass}">
                        <div class="metric-label">Budget Used</div>
                        <div class="metric-value ${budgetClass || 'info'}">${data.budget_status.daily_used_percent.toFixed(1)}%</div>
                        <div class="metric-change">$${data.budget_status.daily_limit.toFixed(2)} daily limit</div>
                    </div>

                    <div class="metric-card">
                        <div class="metric-label">Projected Monthly</div>
                        <div class="metric-value warning">${formatCurrency(data.monthly_estimate.projected_month)}</div>
                        <div class="metric-change">$${data.monthly_estimate.daily_average.toFixed(4)}/day avg</div>
                    </div>

                    <div class="metric-card">
                        <div class="metric-label">Avg Latency</div>
                        <div class="metric-value info">${data.avg_latency_ms.toFixed(0)}ms</div>
                        <div class="metric-change">Response time</div>
                    </div>

                    <div class="metric-card ${data.error_rate > 5 ? 'danger' : ''}">
                        <div class="metric-label">Error Rate</div>
                        <div class="metric-value ${data.error_rate > 5 ? 'danger' : 'success'}">${data.error_rate.toFixed(2)}%</div>
                        <div class="metric-change">${data.this_week.errors} errors this week</div>
                    </div>
                `;

                // Update alerts
                const alertsDiv = document.getElementById('alerts');
                alertsDiv.innerHTML = '';

                if (data.budget_status.daily_used_percent >= 90) {
                    alertsDiv.innerHTML += `
                        <div class="alert alert-danger">
                            <span>⚠️</span>
                            <span>Budget Alert: Daily limit ${data.budget_status.daily_used_percent.toFixed(1)}% consumed!</span>
                        </div>
                    `;
                } else if (data.budget_status.daily_used_percent >= 75) {
                    alertsDiv.innerHTML += `
                        <div class="alert alert-warning">
                            <span>⚠️</span>
                            <span>Warning: Daily limit ${data.budget_status.daily_used_percent.toFixed(1)}% consumed</span>
                        </div>
                    `;
                }

                // Update charts
                updateCharts(data);

                // Update tables
                updateTables(data);

            } catch (error) {
                document.getElementById('metrics-grid').innerHTML =
                    `<div class="error">Failed to load metrics: ${error.message}</div>`;
            }
        }

        function updateCharts(data) {
            // Fetch daily costs for trend chart
            fetch('/api/metrics/daily?days=30')
                .then(r => r.json())
                .then(dailyData => {
                    const labels = dailyData.map(d => d.date).reverse();
                    const costs = dailyData.map(d => d.cost).reverse();

                    const ctx = document.getElementById('costChart').getContext('2d');

                    if (costChart) costChart.destroy();

                    costChart = new Chart(ctx, {
                        type: 'line',
                        data: {
                            labels: labels,
                            datasets: [{
                                label: 'Daily Cost',
                                data: costs,
                                borderColor: '#00d4ff',
                                backgroundColor: 'rgba(0,212,255,0.1)',
                                fill: true,
                                tension: 0.4
                            }]
                        },
                        options: {
                            responsive: true,
                            plugins: {
                                legend: { display: false }
                            },
                            scales: {
                                y: {
                                    beginAtZero: true,
                                    ticks: {
                                        color: 'rgba(255,255,255,0.6)',
                                        callback: function(value) {
                                            return '$' + value.toFixed(2);
                                        }
                                    },
                                    grid: { color: 'rgba(255,255,255,0.1)' }
                                },
                                x: {
                                    ticks: { color: 'rgba(255,255,255,0.6)' },
                                    grid: { color: 'rgba(255,255,255,0.1)' }
                                }
                            }
                        }
                    });
                });

            // Model breakdown pie chart
            const modelCtx = document.getElementById('modelChart').getContext('2d');

            if (modelChart) modelChart.destroy();

            const modelLabels = data.model_breakdown.map(m => m.model.split('/').pop());
            const modelCosts = data.model_breakdown.map(m => m.cost);

            modelChart = new Chart(modelCtx, {
                type: 'doughnut',
                data: {
                    labels: modelLabels,
                    datasets: [{
                        data: modelCosts,
                        backgroundColor: [
                            '#00d4ff', '#7b2cbf', '#4CAF50', '#ffc107', '#dc3545',
                            '#ff6b6b', '#4ecdc4', '#45b7d1'
                        ]
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: {
                            position: 'right',
                            labels: { color: 'rgba(255,255,255,0.8)' }
                        }
                    }
                }
            });
        }

        function updateTables(data) {
            // Models table
            const modelsBody = document.querySelector('#models-table tbody');
            modelsBody.innerHTML = data.model_breakdown.map(m => `
                <tr>
                    <td>${m.model.split('/').pop()}</td>
                    <td>${m.requests}</td>
                    <td>${formatCurrency(m.cost)}</td>
                </tr>
            `).join('');

            // Features table
            const featuresBody = document.querySelector('#features-table tbody');
            featuresBody.innerHTML = data.feature_breakdown.map(f => `
                <tr>
                    <td>${f.feature}</td>
                    <td>${f.requests}</td>
                    <td>${formatCurrency(f.cost)}</td>
                </tr>
            `).join('');
        }

        // Load on page load
        loadMetrics();

        // Auto-refresh every 30 seconds
        setInterval(loadMetrics, 30000);
    </script>
</body>
</html>
"""


def register_metrics_routes(app):
    """Register metrics routes with the Flask app."""

    @app.route("/admin/metrics")
    def admin_metrics():
        """Serve the metrics dashboard HTML page."""
        return render_template_string(METRICS_DASHBOARD_TEMPLATE)

    @app.route("/api/metrics/summary")
    def api_metrics_summary():
        """Get performance summary as JSON."""
        if not PERFORMANCE_MONITOR_AVAILABLE:
            return jsonify({"error": "Performance monitoring not available"}), 503

        try:
            summary = metrics_collector.get_performance_summary()
            return jsonify(summary)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/metrics/daily")
    def api_metrics_daily():
        """Get daily cost breakdown."""
        if not PERFORMANCE_MONITOR_AVAILABLE:
            return jsonify({"error": "Performance monitoring not available"}), 503

        try:
            days = request.args.get("days", 30, type=int)
            daily_costs = metrics_collector.get_daily_costs(days)
            return jsonify(daily_costs)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/metrics/models")
    def api_metrics_models():
        """Get cost breakdown by model."""
        if not PERFORMANCE_MONITOR_AVAILABLE:
            return jsonify({"error": "Performance monitoring not available"}), 503

        try:
            days = request.args.get("days", 7, type=int)
            model_costs = metrics_collector.get_cost_by_model(days)
            return jsonify(model_costs)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/metrics/features")
    def api_metrics_features():
        """Get cost breakdown by feature."""
        if not PERFORMANCE_MONITOR_AVAILABLE:
            return jsonify({"error": "Performance monitoring not available"}), 503

        try:
            days = request.args.get("days", 7, type=int)
            feature_costs = metrics_collector.get_cost_by_feature(days)
            return jsonify(feature_costs)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/metrics/cache")
    def api_metrics_cache():
        """Get cache statistics."""
        if not PERFORMANCE_MONITOR_AVAILABLE:
            return jsonify({"error": "Performance monitoring not available"}), 503

        try:
            cache_stats = metrics_collector.get_cache_stats()
            return jsonify(cache_stats)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/metrics/errors")
    def api_metrics_errors():
        """Get error statistics."""
        if not PERFORMANCE_MONITOR_AVAILABLE:
            return jsonify({"error": "Performance monitoring not available"}), 503

        try:
            days = request.args.get("days", 7, type=int)
            error_stats = metrics_collector.get_error_stats(days)
            return jsonify(error_stats)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/metrics/budget", methods=["GET", "POST"])
    def api_metrics_budget():
        """Get or set budget limits."""
        if not PERFORMANCE_MONITOR_AVAILABLE:
            return jsonify({"error": "Performance monitoring not available"}), 503

        if request.method == "GET":
            try:
                summary = metrics_collector.get_performance_summary()
                return jsonify(
                    {
                        "daily_limit": summary["budget_status"]["daily_limit"],
                        "monthly_limit": summary["budget_status"]["monthly_limit"],
                        "daily_used": summary["today"]["cost"],
                        "daily_used_percent": summary["budget_status"]["daily_used_percent"],
                    }
                )
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        elif request.method == "POST":
            try:
                data = request.json or {}
                daily = data.get("daily")
                monthly = data.get("monthly")

                metrics_collector.set_budget_limits(
                    daily=float(daily) if daily is not None else None,
                    monthly=float(monthly) if monthly is not None else None,
                )

                return jsonify({"status": "success"})
            except Exception as e:
                return jsonify({"error": str(e)}), 500

    @app.route("/api/metrics/report", methods=["POST"])
    def api_generate_report():
        """Generate a performance report."""
        if not PERFORMANCE_MONITOR_AVAILABLE:
            return jsonify({"error": "Performance monitoring not available"}), 503

        try:
            data = request.json or {}
            days = data.get("days", 7)
            format = data.get("format", "json")

            report_path = dashboard_generator.generate_daily_report(days, format)

            # Also generate HTML dashboard
            html_path = dashboard_generator.generate_html_dashboard()

            return jsonify(
                {"status": "success", "report_path": report_path, "dashboard_path": html_path}
            )
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return app


# For testing
if __name__ == "__main__":
    from flask import Flask

    app = Flask(__name__)
    register_metrics_routes(app)

    print("Metrics routes registered. Run with:")
    print("  python -m flask --app src.utils.metrics_web run")
